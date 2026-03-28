"""
Parse pg_dump SQL COPY blocks into Python dicts.
No PostgreSQL installation required - works directly on the .sql file.
"""
import re
from typing import Optional


# Tables we need to extract
TABLES_TO_EXTRACT = [
    "students_student",
    "auth_user",
    "auth_group",
    "auth_user_groups",
    "users_staff",
    "parents_parent",
    "parents_parent_students",
    "groups_group",
    "groups_group_students",
    "groups_group_teachers",
    "lessons_lesson",
    "lessons_lesson_additional_teachers",
    "lessons_lesson_groups",
    "lessons_lesson_teachers",
    "core_schoolsettings",
]

# Columns to NEVER extract from core_schoolsettings (secrets/OAuth)
SCHOOLSETTINGS_BLOCKED_COLUMNS = {
    "google_client_id", "google_client_secret",
    "microsoft_tenant_id", "microsoft_client_id", "microsoft_client_secret",
    "google_secret_created", "google_secret_expires",
    "microsoft_secret_created", "microsoft_secret_expires",
    "oauth_notification_emails", "oauth_notification_schedule",
    "storage_client_id", "storage_client_secret", "storage_tenant_id",
    "email_client_id", "email_client_secret", "email_tenant_id",
    "email_secret_created", "email_secret_expires",
    "bankid_client_id", "bankid_client_secret",
    "allowed_domains", "custom_email_pattern", "email_domain", "email_pattern",
    "oauth_provider", "sis_provider",
    "header_background_image",
    "app_access_policy_created", "app_access_policy_tested",
}

# Pattern to match COPY statements
COPY_PATTERN = re.compile(
    r'^COPY public\.(\w+)\s+\(([^)]+)\)\s+FROM stdin;$'
)


def parse_value(val: str) -> Optional[str]:
    """Parse a single tab-delimited value from pg_dump COPY output."""
    if val == "\\N":
        return None
    # Unescape pg_dump escape sequences
    val = val.replace("\\\\", "\x00")  # temp placeholder
    val = val.replace("\\n", "\n")
    val = val.replace("\\r", "\r")
    val = val.replace("\\t", "\t")
    val = val.replace("\x00", "\\")
    # Fix UTF-8 → cp437 → UTF-8 mojibake (common with pg_dump on Windows).
    # Swedish chars like ä ö å get double-encoded: "Lärare" → "L├ñrare".
    try:
        val = val.encode("cp437").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return val


def extract_tables(dump_path: str) -> dict[str, list[dict]]:
    """
    Parse a pg_dump SQL file and extract specified tables.

    Returns: {table_name: [{"col1": val1, "col2": val2, ...}, ...]}
    """
    results = {}
    current_table = None
    current_columns = None

    with open(dump_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # Check for COPY statement
            match = COPY_PATTERN.match(line)
            if match:
                table_name = match.group(1)
                if table_name in TABLES_TO_EXTRACT:
                    columns_str = match.group(2)
                    current_table = table_name
                    current_columns = [
                        c.strip().strip('"') for c in columns_str.split(",")
                    ]
                    results[table_name] = []
                continue

            # Check for end of COPY block
            if line == "\\.":
                current_table = None
                current_columns = None
                continue

            # Parse data row
            if current_table and current_columns:
                values = line.split("\t")
                if len(values) != len(current_columns):
                    # Skip malformed rows
                    continue

                row = {}
                for col, val in zip(current_columns, values):
                    # Strip secrets from schoolsettings
                    if (current_table == "core_schoolsettings"
                            and col in SCHOOLSETTINGS_BLOCKED_COLUMNS):
                        row[col] = None
                        continue
                    row[col] = parse_value(val)

                results[current_table].append(row)

    return results


def get_active_students(data: dict) -> list[dict]:
    """Filter to only active students."""
    return [s for s in data.get("students_student", []) if s.get("active") == "t"]


def get_active_staff(data: dict) -> list[dict]:
    """Get active staff by joining auth_user + users_staff."""
    staff_by_user_id = {}
    for s in data.get("users_staff", []):
        if s.get("active") == "t":
            staff_by_user_id[s["user_id"]] = s

    users = {}
    for u in data.get("auth_user", []):
        if u.get("is_active") == "t" and u["id"] in staff_by_user_id:
            users[u["id"]] = u

    result = []
    for user_id, user in users.items():
        staff = staff_by_user_id[user_id]
        result.append({
            "staff_id": staff["id"],
            "user_id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"] or staff["email"],
            "username": user["username"],
            "socialnumber": staff.get("socialnumber"),
            "birthday": staff.get("birthday"),
            "signature": staff.get("signature"),
            "address1": staff.get("address1"),
            "pocode": staff.get("pocode"),
            "city": staff.get("city"),
            "mobile": staff.get("mobile"),
            "workphone": staff.get("workphone"),
            "external_id": staff.get("external_id"),
        })
    return result


def get_active_parents(data: dict) -> list[dict]:
    """Filter to only active parents."""
    return [p for p in data.get("parents_parent", []) if p.get("active") == "t"]


def get_active_groups(data: dict) -> list[dict]:
    """Filter to only active groups."""
    return [g for g in data.get("groups_group", []) if g.get("active") == "t"]


def get_staff_roles(data: dict) -> dict[str, list[str]]:
    """
    Map user_id → list of auth_group names.
    Returns {user_id: [role_name, ...]}
    """
    group_names = {g["id"]: g["name"] for g in data.get("auth_group", [])}
    user_roles = {}
    for ug in data.get("auth_user_groups", []):
        uid = ug["user_id"]
        gid = ug["group_id"]
        if uid not in user_roles:
            user_roles[uid] = []
        if gid in group_names:
            user_roles[uid].append(group_names[gid])
    return user_roles


def get_school_settings(data: dict) -> dict:
    """Get the (sanitized) school settings row."""
    rows = data.get("core_schoolsettings", [])
    if rows:
        return rows[0]
    return {}


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python extract_from_dump.py <dump.sql>")
        sys.exit(1)

    data = extract_tables(sys.argv[1])
    for table, rows in data.items():
        print(f"{table}: {len(rows)} rows")
