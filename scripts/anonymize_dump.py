#!/usr/bin/env python3
"""
Create an anonymized copy of a skolSköld PostgreSQL dump.

Parses all COPY blocks, applies PII anonymization to relevant columns,
scrubs free-text fields for real names, blocks secrets, and writes
a clean dump file that is safe to share/commit.

Usage:
    python -m scripts.anonymize_dump \
        --dump carlssons_dump.sql \
        --output carlssons_anon.sql \
        --seed 42
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_from_dump import extract_tables, COPY_PATTERN, parse_value
from scripts.person_registry import PersonRegistry, NameScrubber


# Static password hash for all anonymized users (password: "demo123")
STATIC_PASSWORD = (
    "pbkdf2_sha256$600000$demosalt$"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)

# Columns that should be NULLed out entirely (secrets, tokens, etc.)
NULL_COLUMNS = {
    "core_schoolsettings": {
        "google_client_id", "google_client_secret",
        "microsoft_tenant_id", "microsoft_client_id", "microsoft_client_secret",
        "google_secret_created", "google_secret_expires",
        "microsoft_secret_created", "microsoft_secret_expires",
        "oauth_notification_emails", "oauth_notification_schedule",
        "storage_client_id", "storage_client_secret", "storage_tenant_id",
        "storage_root_folder", "storage_test_date", "storage_test_status",
        "email_client_id", "email_client_secret", "email_tenant_id",
        "email_secret_created", "email_secret_expires",
        "email_shared_mailbox", "email_group_id",
        "bankid_client_id", "bankid_client_secret",
        "allowed_domains", "custom_email_pattern",
        "header_background_image",
        "ss12000_api_url", "ss12000_client_id", "ss12000_client_secret",
        "billing_address", "economist_email", "economist_name",
        "economist_phone", "invoice_email", "organisation_number",
        "school_trusted_ip", "school_ip_addresses",
        "sharepoint_site_url", "sharepoint_library_incidents",
        "sharepoint_site_id", "sharepoint_site_name",
        "calendar_shared_mailbox", "m365_group_email",
        "app_access_policy_created", "app_access_policy_tested",
    },
    "core_smssettings": {
        "api_username", "api_password",
    },
    "bankid_bankidcertificate": {
        "certificate_file", "passphrase",
    },
    "bankid_bankidsession": {
        "personal_number", "completion_data",
        "auto_start_token", "qr_start_token", "qr_start_secret",
    },
    "setup_wizard_setupsession": {
        "access_token_encrypted", "refresh_token_encrypted",
        "app_client_secret_encrypted", "app_registration_id",
        "app_client_id",
    },
    "documents_cloudstorageconfig": {
        "microsoft_client_id", "microsoft_client_secret",
        "microsoft_tenant_id", "google_credentials_json",
        "root_folder_id",
    },
    "imports_schoolsoftconfig": {
        "api_key", "api_secret", "api_url",
        "integration_password", "schoolsoft_password_encrypted",
        "schoolsoft_username", "schoolsoft_domain",
    },
    "notifications_pushsubscription": {
        "endpoint", "p256dh", "auth",
    },
}

# Text columns to scrub with NameScrubber (table -> [columns])
SCRUB_COLUMNS = {
    "incidents_incident": [
        "title", "description", "witnesses", "immediate_action",
        "follow_up_notes",
    ],
    "incidents_historicalincident": [
        "title", "description", "witnesses", "immediate_action",
        "follow_up_notes",
    ],
    "incidents_historicalincidentcomment": ["comment"],
    "incidents_studentinvolvement": ["description"],
    "referrals_referral": [
        "reason", "description", "outcome", "recommendations",
        "additional_information", "current_situation", "goals",
        "measures_taken", "other_measures", "student_strengths",
        "support_sought",
    ],
    "referrals_referralcomment": ["text"],
    "referrals_referraldelegation": ["delegation_note", "response_note"],
    "comments_comment": ["text"],
    "comments_historicalcomment": ["text"],
    "meetings_meeting": [
        "title", "agenda", "preparation_notes", "minutes",
        "action_items", "cancelled_reason",
    ],
    "meetings_meetingcomment": ["text"],
    "meetings_meetingpoint": [
        "subject", "description", "documentation", "notes",
        "decision", "action_items", "resolution",
    ],
    "meetings_meetingstudent": [
        "discussion_topics", "decisions", "action_items",
    ],
    "customizations_customization": [
        "title", "description", "course_or_subject", "background_notes",
    ],
    "customizations_customizationrevision": [
        "description", "background_notes", "revision_notes",
    ],
    "notifications_notification": ["title", "message"],
    "auditlog_auditlog": ["username", "target_str", "details", "message"],
    "auditlog_securityalert": [
        "title", "description", "details", "investigation_notes",
    ],
    "students_studentwatch": ["notes"],
    "watchlist_watchlist": ["reason"],
    "watchlist_watchlistactivity": ["description"],
    "core_dataaccessoverride": ["reason"],
    "core_ownershiptransferlog": ["reason"],
    "emails_emailrecord": [
        "subject", "sender_name", "body_text", "body_html",
        "recipients_to", "recipients_cc", "assignment_note",
    ],
    "emails_emailthread": ["subject", "participants"],
    "documents_filestorage": ["name", "description"],
    "documents_fileaccessrequest": ["reason", "response_note"],
    "meetings_meetingattendee": ["notes"],
    "django_admin_log": ["object_repr", "change_message"],
    "referrals_referralstatushistory": ["reason"],
    "imports_importlog": [
        "processing_log", "error_message", "error_details", "record_details",
    ],
}


def format_pg_value(val):
    """Format a Python value back to pg_dump TAB-delimited format."""
    if val is None:
        return "\\N"
    val = str(val)
    val = val.replace("\\", "\\\\")
    val = val.replace("\n", "\\n")
    val = val.replace("\r", "\\r")
    val = val.replace("\t", "\\t")
    return val


def build_registry(dump_path: str, seed: int) -> PersonRegistry:
    """Parse person tables from dump, build and compute anonymized registry."""
    print("Pass 1: Building person registry...")
    data = extract_tables(dump_path)
    registry = PersonRegistry()
    registry.build_from_dump_data(data)
    registry.compute_anonymized_identities(seed)
    print(f"  Registry: {len(registry.persons)} persons")
    print(f"    PNR index: {len(registry._pnr_index)} entries")
    print(f"    Email index: {len(registry._email_index)} entries")
    print(f"    Comvius index: {len(registry._comvius_index)} entries")
    return registry


def anonymize_row(
    table: str,
    columns: list[str],
    raw_values: list[str],
    registry: PersonRegistry,
    scrubber: NameScrubber,
) -> list[str]:
    """Anonymize a single row. Returns list of pg_dump-formatted values."""
    # Parse values
    values = [parse_value(v) for v in raw_values]
    col_map = dict(zip(columns, values))

    def get(col):
        return col_map.get(col)

    def set_val(col, val):
        col_map[col] = val

    # --- Person tables: direct field replacement ---

    if table == "auth_user":
        user_id = get("id")
        p = registry.by_user_id(user_id) if user_id else None
        if p:
            set_val("first_name", p.anon_first)
            set_val("last_name", p.anon_last)
            set_val("email", p.anon_email)
            set_val("username", p.anon_username)
        set_val("password", STATIC_PASSWORD)

    elif table == "users_staff":
        staff_id = get("id")
        p = registry.by_key("staff", staff_id) if staff_id else None
        if p:
            set_val("socialnumber", p.anon_pnr)
            set_val("email", p.anon_email)
            set_val("mobile", p.anon_phone if get("mobile") else None)
            set_val("workphone", p.anon_phone if get("workphone") else None)
            set_val("homephone", None)
            if get("address1"):
                set_val("address1", p.anon_street)
                set_val("address2", None)
                set_val("pocode", p.anon_postal)
                set_val("city", p.anon_city)
            set_val("signature", p.anon_signature)
        set_val("data_hash", "anonymized")

    elif table == "students_student":
        student_id = get("id")
        p = registry.by_key("student", student_id) if student_id else None
        if p:
            set_val("first_name", p.anon_first)
            set_val("last_name", p.anon_last)
            set_val("socialnumber", p.anon_pnr)
            set_val("email", p.anon_email)
            set_val("username", p.anon_username)
            if get("phone"):
                set_val("phone", p.anon_phone)
            if get("address"):
                set_val("address", p.anon_street)
                set_val("postal_code", p.anon_postal)
                set_val("city", p.anon_city)
            # Clear sensitive alias/protection fields
            set_val("alias_first_name", None)
            set_val("alias_last_name", None)
            set_val("protection_notes", None)
            set_val("gdpr_notes", None)
        set_val("data_hash", "anonymized")

    elif table == "parents_parent":
        parent_id = get("id")
        p = registry.by_key("parent", parent_id) if parent_id else None
        if p:
            set_val("first_name", p.anon_first)
            set_val("last_name", p.anon_last)
            set_val("personnummer", p.anon_pnr)
            set_val("email", p.anon_email)
            if get("mobile"):
                set_val("mobile", p.anon_phone)
            set_val("work_phone", None)
            set_val("home_phone", None)
            if get("address1"):
                set_val("address1", p.anon_street)
                set_val("address2", None)
                set_val("postcode", p.anon_postal)
                set_val("city", p.anon_city)
        set_val("data_hash", "anonymized")

    elif table == "parents_parentemail":
        # Map email via parent_id
        parent_id = get("parent_id")
        p = registry.by_key("parent", parent_id) if parent_id else None
        if p and p.anon_email:
            set_val("email", p.anon_email)

    elif table == "bankid_bankiduser":
        user_id = get("user_id")
        p = registry.by_user_id(user_id) if user_id else None
        if p:
            set_val("name", f"{p.anon_first} {p.anon_last}")
            set_val("given_name", p.anon_first)
            set_val("surname", p.anon_last)
        set_val("personal_number_hash", "anonymized")

    elif table == "auditlog_loginattempttracker":
        # Scrub username
        username = get("username")
        if username:
            set_val("username", scrubber.scrub(username))

    elif table == "documents_fileaccesslog":
        set_val("microsoft_user_email", None)
        set_val("microsoft_user_name", None)

    elif table == "users_userprofile":
        set_val("microsoft_photo_url", None)
        set_val("microsoft_upn", None)
        set_val("email_aliases", None)
        set_val("last_known_ip", None)
        set_val("last_location_city", None)
        set_val("last_location_country", None)
        set_val("trusted_ips", None)

    elif table == "auditlog_userconnectionlog":
        set_val("ip_address", "127.0.0.1")
        set_val("city", None)
        set_val("region", None)

    elif table == "django_session":
        set_val("session_data", "")

    elif table == "emails_emailrecord":
        # Anonymize sender email
        sender = get("sender_email")
        if sender:
            p = registry.by_email(sender)
            if p:
                set_val("sender_email", p.anon_email)
            else:
                set_val("sender_email", scrubber.scrub(sender))

    elif table == "core_secretexpirationnotification":
        set_val("sent_to", None)

    # --- School name replacement in settings ---
    if table == "core_schoolsettings":
        set_val("school_name", "Demoskolan")
        set_val("school_code", "DEMO")
        set_val("contact_email", "info@demoskolan.se")
        set_val("contact_phone", "08-123 00 00")
        set_val("address", "Storgatan 1, 111 22 Stockholm")
        set_val("email_domain", "demoskolan.se")
        set_val("email_pattern", "{first}.{last}@demoskolan.se")
        set_val("is_demo", "t")

    elif table == "imports_datamapping":
        # external_ref may contain personnummer
        ext_ref = get("external_ref")
        if ext_ref:
            set_val("external_ref", scrubber.scrub(ext_ref))

    # --- NULL out secret columns ---
    if table in NULL_COLUMNS:
        for col in NULL_COLUMNS[table]:
            if col in col_map:
                set_val(col, None)

    # --- Scrub free-text columns ---
    if table in SCRUB_COLUMNS:
        for col in SCRUB_COLUMNS[table]:
            val = get(col)
            if val:
                set_val(col, scrubber.scrub(val))

    # Rebuild values in column order
    return [format_pg_value(col_map[c]) for c in columns]


def rewrite_dump(
    input_path: str,
    output_path: str,
    registry: PersonRegistry,
    scrubber: NameScrubber,
) -> dict:
    """Stream-rewrite the dump file with anonymized data."""
    print("Pass 2: Rewriting dump...")
    stats = {"tables_processed": 0, "rows_processed": 0}
    current_table = None
    current_columns = None

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for line in fin:
            raw = line.rstrip("\n")

            # Check for COPY statement
            match = COPY_PATTERN.match(raw)
            if match:
                table_name = match.group(1)
                columns_str = match.group(2)
                current_table = table_name
                current_columns = [
                    c.strip().strip('"') for c in columns_str.split(",")
                ]
                fout.write(line)
                stats["tables_processed"] += 1
                continue

            # Check for end of COPY block
            if raw == "\\.":
                current_table = None
                current_columns = None
                fout.write(line)
                continue

            # Process data row inside a COPY block
            if current_table and current_columns:
                raw_values = raw.split("\t")
                if len(raw_values) == len(current_columns):
                    new_values = anonymize_row(
                        current_table, current_columns, raw_values,
                        registry, scrubber,
                    )
                    fout.write("\t".join(new_values) + "\n")
                    stats["rows_processed"] += 1
                else:
                    # Malformed row — pass through
                    fout.write(line)
                continue

            # Non-COPY line — pass through verbatim
            fout.write(line)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Create an anonymized copy of a skolSköld PostgreSQL dump"
    )
    parser.add_argument("--dump", required=True, help="Path to raw pg_dump SQL file")
    parser.add_argument("--output", required=True, help="Output anonymized SQL file")
    parser.add_argument("--mapping", default=None, help="Output mapping JSON (default: <output>.mapping.json)")
    parser.add_argument("--seed", type=int, default=42, help="Anonymization seed (default: 42)")

    args = parser.parse_args()

    if not os.path.exists(args.dump):
        print(f"Error: dump file not found: {args.dump}")
        sys.exit(1)

    mapping_path = args.mapping or args.output.replace(".sql", "_mapping.json")

    # Pass 1: Build person registry
    registry = build_registry(args.dump, args.seed)

    # Build name scrubber from registry
    scrubber = NameScrubber(registry)

    # Pass 2: Stream-rewrite the dump
    stats = rewrite_dump(args.dump, args.output, registry, scrubber)

    # Save mapping for Comvius anonymization
    registry.save_mapping(mapping_path)

    print(f"\nDone!")
    print(f"  Tables processed: {stats['tables_processed']}")
    print(f"  Rows processed: {stats['rows_processed']}")
    print(f"  Anonymized dump: {args.output}")
    print(f"  Mapping file: {mapping_path}")


if __name__ == "__main__":
    main()
