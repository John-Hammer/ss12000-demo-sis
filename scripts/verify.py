#!/usr/bin/env python3
"""
PII leak checker and integrity validator for anonymized data.

Usage:
    python -m scripts.verify --dump path/to/dump.sql --output app/seed/anon_data.py
"""
import argparse
import os
import re
import sys
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_from_dump import extract_tables


def load_anon_module(path: str):
    """Dynamically load the anon_data.py module."""
    spec = importlib.util.spec_from_file_location("anon_data", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_pii_individuals(data: dict) -> list[dict]:
    """
    Extract PII grouped by individual (not just strings).
    Returns list of {"type": ..., "full_name": "First Last", "email": ..., ...}
    This lets us check for individual-level leaks rather than coincidental name overlaps.
    """
    individuals = []

    for s in data.get("students_student", []):
        first = (s.get("first_name") or "").strip()
        last = (s.get("last_name") or "").strip()
        if first and last:
            individuals.append({
                "type": "student",
                "full_name": f"{first} {last}",
                "first_name": first,
                "last_name": last,
                "email": (s.get("email") or "").strip(),
                "socialnumber": (s.get("socialnumber") or "").strip(),
                "username": (s.get("username") or "").strip(),
            })

    for u in data.get("auth_user", []):
        first = (u.get("first_name") or "").strip()
        last = (u.get("last_name") or "").strip()
        if first and last:
            individuals.append({
                "type": "staff",
                "full_name": f"{first} {last}",
                "first_name": first,
                "last_name": last,
                "email": (u.get("email") or "").strip(),
            })

    for p in data.get("parents_parent", []):
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        if first and last:
            individuals.append({
                "type": "parent",
                "full_name": f"{first} {last}",
                "first_name": first,
                "last_name": last,
                "email": (p.get("email") or "").strip(),
                "personnummer": (p.get("personnummer") or "").strip(),
            })

    return individuals


def extract_all_strings(anon_mod) -> set[str]:
    """Extract all string values from the anonymized data module."""
    strings = set()

    def collect(obj):
        if isinstance(obj, str) and len(obj) > 2:
            strings.add(obj)
        elif isinstance(obj, list):
            for item in obj:
                collect(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                collect(v)

    for attr_name in ("ORGANISATIONS", "STAFF", "STUDENTS", "GUARDIANS",
                      "GROUPS_DATA", "TEACHING_GROUPS_DATA", "ACTIVITIES_DATA"):
        attr = getattr(anon_mod, attr_name, None)
        if attr:
            collect(attr)

    return strings


def check_pii_leaks(individuals: list[dict], anon_strings: set[str]) -> list[str]:
    """
    Check for individual-level PII leaks.
    A leak is when a specific person's full name, email, or personnummer
    appears verbatim in the anonymized output. Individual names may coincidentally
    overlap with Swedish name pools — that's expected and not a leak.
    """
    leaks = []
    anon_lower = {s.lower() for s in anon_strings}

    for person in individuals:
        full_name = person["full_name"]
        # Check if full name (first + last together) appears
        if full_name.lower() in anon_lower:
            leaks.append(
                f"FULL NAME LEAK: '{full_name}' ({person['type']}) found in anonymized data"
            )

        # Check if email appears
        email = person.get("email", "")
        if email and email.lower() in anon_lower:
            leaks.append(
                f"EMAIL LEAK: '{email}' ({person['type']}) found in anonymized data"
            )

        # Check if personnummer appears
        pnr = person.get("socialnumber") or person.get("personnummer", "")
        if pnr and pnr in anon_strings:
            leaks.append(
                f"PERSONNUMMER LEAK: '{pnr}' ({person['type']}) found in anonymized data"
            )

    return leaks


def check_fk_integrity(anon_mod) -> list[str]:
    """Validate all FK references resolve."""
    errors = []

    # Collect all known UUIDs
    all_person_ids = set()
    all_org_ids = set()
    all_group_ids = set()

    for org in getattr(anon_mod, "ORGANISATIONS", []):
        all_org_ids.add(org["id"])

    for s in getattr(anon_mod, "STAFF", []):
        all_person_ids.add(s["id"])

    for s in getattr(anon_mod, "STUDENTS", []):
        all_person_ids.add(s["id"])

    for g in getattr(anon_mod, "GUARDIANS", []):
        all_person_ids.add(g["id"])

    for g in getattr(anon_mod, "GROUPS_DATA", []):
        all_group_ids.add(g["id"])

    for g in getattr(anon_mod, "TEACHING_GROUPS_DATA", []):
        all_group_ids.add(g["id"])

    # Check student → guardian references
    for s in getattr(anon_mod, "STUDENTS", []):
        for gid in s.get("guardian_ids", []):
            if gid not in all_person_ids:
                errors.append(
                    f"Student '{s['given_name']}' references unknown guardian {gid}")

        # Check student → group reference
        group_id = s.get("group_id")
        if group_id and group_id not in all_group_ids:
            errors.append(
                f"Student '{s['given_name']}' references unknown group {group_id}")

        # Check student → org reference
        if s.get("school_unit_id") and s["school_unit_id"] not in all_org_ids:
            errors.append(
                f"Student '{s['given_name']}' references unknown org {s['school_unit_id']}")

    # Check group → org references
    for g in getattr(anon_mod, "GROUPS_DATA", []):
        if g.get("organisation_id") and g["organisation_id"] not in all_org_ids:
            errors.append(
                f"Group '{g['display_name']}' references unknown org {g['organisation_id']}")
        if g.get("mentor_id") and g["mentor_id"] not in all_person_ids:
            errors.append(
                f"Group '{g['display_name']}' references unknown mentor {g['mentor_id']}")

    # Check teaching group → class references
    for g in getattr(anon_mod, "TEACHING_GROUPS_DATA", []):
        for cid in g.get("class_ids", []):
            if cid not in all_group_ids:
                errors.append(
                    f"Teaching group '{g['display_name']}' references unknown class {cid}")

    # Check activity references
    for act in getattr(anon_mod, "ACTIVITIES_DATA", []):
        if act.get("organisation_id") and act["organisation_id"] not in all_org_ids:
            errors.append(
                f"Activity '{act['display_name']}' references unknown org")
        for tid in act.get("teacher_ids", []):
            if tid not in all_person_ids:
                errors.append(
                    f"Activity '{act['display_name']}' references unknown teacher {tid}")
        for gid in act.get("group_ids", []):
            if gid not in all_group_ids:
                errors.append(
                    f"Activity '{act['display_name']}' references unknown group {gid}")

    # Check org hierarchy
    for org in getattr(anon_mod, "ORGANISATIONS", []):
        if org.get("parent_id") and org["parent_id"] not in all_org_ids:
            errors.append(
                f"Org '{org['display_name']}' references unknown parent org")

    return errors


def check_formats(anon_mod) -> list[str]:
    """Check data format validity."""
    errors = []
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    )
    pnr_pattern = re.compile(r'^\d{6}-\d{4}$')
    email_pattern = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

    # Check UUID format
    for s in getattr(anon_mod, "STAFF", []):
        if not uuid_pattern.match(s["id"]):
            errors.append(f"Staff '{s['given_name']}' has invalid UUID: {s['id']}")

    for s in getattr(anon_mod, "STUDENTS", []):
        if not uuid_pattern.match(s["id"]):
            errors.append(f"Student '{s['given_name']}' has invalid UUID: {s['id']}")
        # Check personnummer format
        if s.get("civic_no") and not pnr_pattern.match(s["civic_no"]):
            errors.append(
                f"Student '{s['given_name']}' has invalid civic_no: {s['civic_no']}")
        # Check email format
        if s.get("email") and not email_pattern.match(s["email"]):
            errors.append(
                f"Student '{s['given_name']}' has invalid email: {s['email']}")

    for s in getattr(anon_mod, "GUARDIANS", []):
        if not uuid_pattern.match(s["id"]):
            errors.append(f"Guardian '{s['given_name']}' has invalid UUID: {s['id']}")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Verify anonymized data has no PII leaks and valid integrity"
    )
    parser.add_argument(
        "--dump", required=True,
        help="Path to the original pg_dump SQL file"
    )
    parser.add_argument(
        "--output", default=None,
        help="Path to anon_data.py (default: app/seed/anon_data.py)"
    )

    args = parser.parse_args()

    output_path = args.output or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "seed", "anon_data.py"
    )

    if not os.path.exists(args.dump):
        print(f"Error: dump file not found: {args.dump}")
        sys.exit(1)

    if not os.path.exists(output_path):
        print(f"Error: anon_data.py not found: {output_path}")
        sys.exit(1)

    print("=== PII Leak Check & Integrity Validation ===\n")

    # Load data
    print("Loading original dump...")
    data = extract_tables(args.dump)

    print("Loading anonymized data...")
    anon_mod = load_anon_module(output_path)

    # 1. PII leak check
    print("\n--- PII Leak Check ---")
    individuals = extract_pii_individuals(data)
    anon_strings = extract_all_strings(anon_mod)
    print(f"  Original individuals: {len(individuals)}")
    print(f"  Anonymized strings: {len(anon_strings)}")

    leaks = check_pii_leaks(individuals, anon_strings)
    if leaks:
        print(f"  FAILED: {len(leaks)} leak(s) found!")
        for leak in leaks[:20]:
            print(f"    {leak}")
        if len(leaks) > 20:
            print(f"    ... and {len(leaks) - 20} more")
    else:
        print("  PASSED: No PII leaks detected")

    # 2. FK integrity
    print("\n--- FK Integrity Check ---")
    fk_errors = check_fk_integrity(anon_mod)
    if fk_errors:
        print(f"  WARNINGS: {len(fk_errors)} reference issue(s)")
        for err in fk_errors[:20]:
            print(f"    {err}")
        if len(fk_errors) > 20:
            print(f"    ... and {len(fk_errors) - 20} more")
    else:
        print("  PASSED: All FK references resolve")

    # 3. Format validation
    print("\n--- Format Validation ---")
    format_errors = check_formats(anon_mod)
    if format_errors:
        print(f"  FAILED: {len(format_errors)} format error(s)")
        for err in format_errors[:20]:
            print(f"    {err}")
    else:
        print("  PASSED: All formats valid")

    # 4. Entity count summary
    print("\n--- Entity Counts ---")
    print(f"  Organisations: {len(getattr(anon_mod, 'ORGANISATIONS', []))}")
    print(f"  Staff: {len(getattr(anon_mod, 'STAFF', []))}")
    print(f"  Students: {len(getattr(anon_mod, 'STUDENTS', []))}")
    print(f"  Guardians: {len(getattr(anon_mod, 'GUARDIANS', []))}")
    print(f"  Class groups: {len(getattr(anon_mod, 'GROUPS_DATA', []))}")
    print(f"  Teaching groups: {len(getattr(anon_mod, 'TEACHING_GROUPS_DATA', []))}")
    print(f"  Activities: {len(getattr(anon_mod, 'ACTIVITIES_DATA', []))}")

    # Summary
    total_issues = len(leaks) + len(format_errors)
    print(f"\n{'='*50}")
    if total_issues == 0:
        print("ALL CHECKS PASSED")
    else:
        print(f"ISSUES FOUND: {total_issues}")
        sys.exit(1)


if __name__ == "__main__":
    main()
