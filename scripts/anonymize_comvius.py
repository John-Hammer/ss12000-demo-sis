#!/usr/bin/env python3
"""
Anonymize Comvius CSV exports using the mapping from anonymize_dump.py.

Reads mapping.json (produced by anonymize_dump.py) and applies the same
anonymized identities to Comvius People.csv, Incidents.csv, Referrals.csv,
and related files.

Usage:
    python -m scripts.anonymize_comvius \
        --csv-dir comvius_csv/ \
        --mapping carlssons_anon_mapping.json \
        --output-dir comvius_anon/ \
        --seed 42
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.person_registry import PersonRegistry, NameScrubber
from scripts.anonymizer import (
    anonymize_first_name, anonymize_last_name, anonymize_personnummer,
    anonymize_email_staff, anonymize_phone,
)


def load_registry_and_scrubber(mapping_path: str, seed: int):
    """Load the registry from mapping JSON and build a NameScrubber.

    Since the mapping JSON doesn't contain original names (only anonymized),
    we need to rebuild the scrubber from the raw dump. Instead, we'll
    build a comvius-specific scrubber from People.csv after matching.
    """
    registry = PersonRegistry.load_mapping(mapping_path)
    return registry


def match_comvius_person(row: dict, registry: PersonRegistry, seed: int) -> dict:
    """Match a Comvius person to the Django person registry.

    Returns dict with anonymized fields.
    """
    pnr = row.get("SocSecNo", "").strip()
    comvius_id = row.get("Id", "").strip()

    # Try PNR match first
    if pnr:
        p = registry.by_pnr(pnr)
        if p:
            return {
                "Firstname": p.anon_first,
                "Lastname": p.anon_last,
                "Mail": p.anon_email or "",
                "Mobile": p.anon_phone if row.get("Mobile") else "",
                "SocSecNo": p.anon_pnr or "",
            }

    # Try comvius_id match
    if comvius_id:
        p = registry.by_comvius_id(comvius_id)
        if p:
            return {
                "Firstname": p.anon_first,
                "Lastname": p.anon_last,
                "Mail": p.anon_email or "",
                "Mobile": p.anon_phone if row.get("Mobile") else "",
                "SocSecNo": p.anon_pnr or "",
            }

    # No match — generate new deterministic identity for this Comvius person
    role = row.get("Role", "").upper()
    gender = None
    first = row.get("Firstname", "")
    if first:
        # Simple gender heuristic
        if first.endswith(("a", "e")) and not first.endswith(("ste", "ke", "ge")):
            gender = "Kvinna"
        else:
            gender = "Man"

    anon_first = anonymize_first_name(seed, f"comvius_{comvius_id}", gender)
    anon_last = anonymize_last_name(seed, f"comvius_{comvius_id}")
    anon_pnr = anonymize_personnummer(seed, f"comvius_{comvius_id}", pnr) if pnr else ""

    if role == "STUDENT":
        from scripts.anonymizer import anonymize_email_student
        anon_email = anonymize_email_student(seed, anon_first, anon_last)
    elif role in ("STAFF", "ADMIN"):
        anon_email = anonymize_email_staff(seed, anon_first, anon_last)
    else:
        from scripts.anonymizer import anonymize_email_guardian
        anon_email = anonymize_email_guardian(seed, anon_first, anon_last)

    return {
        "Firstname": anon_first,
        "Lastname": anon_last,
        "Mail": anon_email if row.get("Mail") else "",
        "Mobile": anonymize_phone(seed, f"comvius_{comvius_id}") if row.get("Mobile") else "",
        "SocSecNo": anon_pnr,
    }


def anonymize_people_csv(input_path: str, output_path: str, registry: PersonRegistry, seed: int) -> dict:
    """Anonymize People.csv. Returns {comvius_id: (orig_full_name, anon_full_name)} for scrubbing."""
    name_map = {}

    with open(input_path, "r", encoding="utf-8-sig") as fin:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames

        with open(output_path, "w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                orig_first = row.get("Firstname", "")
                orig_last = row.get("Lastname", "")
                orig_full = f"{orig_first} {orig_last}".strip()

                anon = match_comvius_person(row, registry, seed)
                row["Firstname"] = anon["Firstname"]
                row["Lastname"] = anon["Lastname"]
                row["Mail"] = anon["Mail"]
                row["Mobile"] = anon["Mobile"]
                row["SocSecNo"] = anon["SocSecNo"]

                # Update Username to match anonymized names
                if row.get("Username") and row["Username"] != "NULL":
                    first3 = anon["Firstname"][:3].lower()
                    last3 = anon["Lastname"][:3].lower()
                    row["Username"] = f"{first3}{last3}"

                anon_full = f"{anon['Firstname']} {anon['Lastname']}".strip()
                if orig_full and orig_full != anon_full:
                    name_map[row["Id"]] = (orig_full, anon_full)

                writer.writerow(row)

    return name_map


def build_comvius_scrubber(name_map: dict) -> 'ComviusScrubber':
    """Build a name scrubber from Comvius People name mappings."""
    import re

    # Full names (highest priority — specific enough to not need word boundaries)
    full_name_pairs = {}
    for cid, (orig, anon) in name_map.items():
        if orig and anon and orig != anon:
            full_name_pairs[orig] = anon

    # Individual names (need word boundaries to avoid matching inside Swedish words)
    word_pairs = {}
    for cid, (orig, anon) in name_map.items():
        orig_parts = orig.split()
        anon_parts = anon.split()
        if len(orig_parts) >= 2 and len(anon_parts) >= 2:
            # Last name — only 5+ chars to be safe
            ln = orig_parts[-1]
            if len(ln) >= 5 and ln not in word_pairs and ln not in full_name_pairs:
                word_pairs[ln] = anon_parts[-1]
            # First name — only 5+ chars
            fn = orig_parts[0]
            if len(fn) >= 5 and fn not in word_pairs and fn not in full_name_pairs:
                word_pairs[fn] = anon_parts[0]

    # School name replacements (exact, no word boundary)
    school_pairs = {
        "carlssonsskola.se": "skolskold.se",
        "Carlssons Skola": "Demoskolan",
        "Carlssons": "Demoskolan",
        "carlssons": "demoskolan",
        "S_CARLSSONS": "S_DEMOSKOLAN",
        "A_CARLSSONS": "A_DEMOSKOLAN",
        "KL_CARLSSONS": "KL_DEMOSKOLAN",
        "FR_CARLSSONS": "FR_DEMOSKOLAN",
    }

    patterns = []

    # School names first (exact match, longest first)
    for real, fake in sorted(school_pairs.items(), key=lambda x: len(x[0]), reverse=True):
        patterns.append((re.compile(re.escape(real), re.IGNORECASE), fake))

    # Full names (longest first, no word boundary)
    for real, fake in sorted(full_name_pairs.items(), key=lambda x: len(x[0]), reverse=True):
        try:
            patterns.append((re.compile(re.escape(real), re.IGNORECASE), fake))
        except re.error:
            continue

    # Individual names with word boundaries
    for real, fake in sorted(word_pairs.items(), key=lambda x: len(x[0]), reverse=True):
        try:
            patterns.append((re.compile(r'\b' + re.escape(real) + r'\b', re.IGNORECASE), fake))
        except re.error:
            continue

    return patterns


def scrub_text(text: str, patterns: list) -> str:
    """Apply name scrubbing patterns to text."""
    if not text:
        return text
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text


def anonymize_csv_with_scrub(input_path: str, output_path: str, scrub_cols: list, email_cols: list,
                              patterns: list, email_map: dict):
    """Generic CSV anonymizer: scrubs text columns and maps email columns."""
    with open(input_path, "r", encoding="utf-8-sig") as fin:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames

        with open(output_path, "w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in reader:
                for col in scrub_cols:
                    if col in row and row[col]:
                        row[col] = scrub_text(row[col], patterns)
                for col in email_cols:
                    if col in row and row[col]:
                        email = row[col].strip()
                        row[col] = email_map.get(email, scrub_text(email, patterns))
                writer.writerow(row)


def passthrough_csv(input_path: str, output_path: str, patterns: list):
    """Copy CSV with only school name replacements."""
    with open(input_path, "r", encoding="utf-8-sig") as fin:
        content = fin.read()
    content = scrub_text(content, patterns)
    with open(output_path, "w", encoding="utf-8") as fout:
        fout.write(content)


def main():
    parser = argparse.ArgumentParser(description="Anonymize Comvius CSV exports")
    parser.add_argument("--csv-dir", required=True, help="Directory containing raw Comvius CSVs")
    parser.add_argument("--mapping", required=True, help="Path to mapping JSON from anonymize_dump.py")
    parser.add_argument("--output-dir", required=True, help="Output directory for anonymized CSVs")
    parser.add_argument("--seed", type=int, default=42, help="Anonymization seed (default: 42)")

    args = parser.parse_args()

    if not os.path.exists(args.csv_dir):
        print(f"Error: CSV directory not found: {args.csv_dir}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Loading mapping from {args.mapping}...")
    registry = load_registry_and_scrubber(args.mapping, args.seed)

    # Step 1: Anonymize People.csv and build name map
    people_in = os.path.join(args.csv_dir, "People.csv")
    people_out = os.path.join(args.output_dir, "People.csv")
    print("Anonymizing People.csv...")
    name_map = anonymize_people_csv(people_in, people_out, registry, args.seed)
    print(f"  Mapped {len(name_map)} persons")

    # Build scrubber and email map from People results
    patterns = build_comvius_scrubber(name_map)

    # Build email map: original email -> anonymized email (use alias for staff)
    email_map = {}
    with open(people_in, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            orig_email = (row.get("Mail") or "").strip()
            if not orig_email:
                continue
            pnr = row.get("SocSecNo", "").strip()
            comvius_id = row.get("Id", "").strip()
            # Look up the person to get alias email for staff
            p = None
            if pnr:
                p = registry.by_pnr(pnr)
            if not p and comvius_id:
                p = registry.by_comvius_id(comvius_id)
            if p and p.anon_email_alias:
                # Staff: map to alias (firstname.lastname@skolskold.se) which matches auth_user.email
                email_map[orig_email] = p.anon_email_alias
            elif p and p.anon_email:
                email_map[orig_email] = p.anon_email
            else:
                anon = match_comvius_person(row, registry, args.seed)
                if anon["Mail"]:
                    email_map[orig_email] = anon["Mail"]

    # Step 2: Anonymize other CSV files
    csv_configs = {
        "Incidents.csv": {
            "scrub": ["Description"],
            "email": ["CreatedByEmail", "EditedByEmail"],
        },
        "Referrals.csv": {
            "scrub": ["Title", "ReasonForConcern", "RequiredActionDescription"],
            "email": ["CreatedBy", "EditedBy"],
        },
        "StudentHealthMeetings.csv": {
            "scrub": [],
            "email": ["CreatedBy"],
        },
        "StudentHealthMeetingStudents.csv": {
            "scrub": ["Notes"],
            "email": ["AddedBy"],
        },
    }

    for filename, config in csv_configs.items():
        filepath = os.path.join(args.csv_dir, filename)
        if os.path.exists(filepath):
            print(f"Anonymizing {filename}...")
            anonymize_csv_with_scrub(
                filepath,
                os.path.join(args.output_dir, filename),
                config["scrub"], config["email"],
                patterns, email_map,
            )

    # Step 3: Pass through structural CSVs with school name replacement only
    passthrough_files = [
        "Enrollments.csv",
        "PersonEnrollments.csv",
        "PersonPersons.csv",
        "IncidentPeople.csv",
        "IncidentLocationSettings.csv",
        "IncidentRoleSettings.csv",
    ]
    for filename in passthrough_files:
        filepath = os.path.join(args.csv_dir, filename)
        if os.path.exists(filepath):
            print(f"Processing {filename} (school name replacement)...")
            passthrough_csv(filepath, os.path.join(args.output_dir, filename), patterns)

    # Copy TSV files if they exist (with school name scrub)
    for filename in ["Incidents.tsv", "Referrals.tsv"]:
        filepath = os.path.join(args.csv_dir, filename)
        if os.path.exists(filepath):
            print(f"Processing {filename}...")
            passthrough_csv(filepath, os.path.join(args.output_dir, filename), patterns)

    print(f"\nDone! Anonymized CSVs written to {args.output_dir}/")


if __name__ == "__main__":
    main()
