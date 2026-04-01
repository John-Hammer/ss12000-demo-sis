#!/usr/bin/env python3
"""
Build SS12000 seed data from Comvius anonymized export.

Reads comvius_anon.zip and generates app/seed/schoolsoft_data.py with
students, guardians, staff, and class groups that match the Comvius data
exactly — so that skolSköld's SS12000 sync + Comvius import align on
personnummer (students/staff) and email (guardians).

Usage:
    python -m scripts.build_from_comvius [--zip comvius_anon.zip] [--seed 42]
"""
import argparse
import csv
import io
import hashlib
import json
import os
import re
import sys
import textwrap
import uuid
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Deterministic UUID generation
# ---------------------------------------------------------------------------
NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def make_uuid(kind: str, key: str) -> str:
    """Deterministic UUID5 from a kind+key pair."""
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


# ---------------------------------------------------------------------------
# Parse Comvius CSVs from zip
# ---------------------------------------------------------------------------
def read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> list[dict]:
    """Read a CSV/TSV from the zip, trying TSV first."""
    tsv_name = name.replace(".csv", ".tsv")
    for try_name in [tsv_name, name]:
        try:
            raw = zf.read(try_name)
            text = raw.decode("utf-8-sig")
            # Detect delimiter
            first_line = text.split("\n")[0]
            delimiter = "\t" if "\t" in first_line else ","
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            return list(reader)
        except KeyError:
            continue
    raise FileNotFoundError(f"Neither {tsv_name} nor {name} found in zip")


def parse_comvius(zip_path: str) -> dict:
    """Parse all relevant Comvius data from the zip file."""
    with zipfile.ZipFile(zip_path) as zf:
        people = read_csv_from_zip(zf, "People.csv")
        person_persons = read_csv_from_zip(zf, "PersonPersons.csv")
        enrollments = read_csv_from_zip(zf, "Enrollments.csv")
        person_enrollments = read_csv_from_zip(zf, "PersonEnrollments.csv")

    # Normalize People field names: Comvius uses Firstname, Lastname, Mail, SocSecNo, Mobile
    for p in people:
        # Create normalized aliases
        p["FirstName"] = p.get("Firstname", p.get("FirstName", ""))
        p["LastName"] = p.get("Lastname", p.get("LastName", ""))
        p["Email"] = p.get("Mail", p.get("Email", ""))
        p["PersonalIdNumber"] = p.get("SocSecNo", p.get("PersonalIdNumber", ""))
        p["Phone"] = p.get("Mobile", p.get("Phone", ""))

    # Index people by ID
    people_by_id = {p["Id"]: p for p in people}

    # Classify people
    students_raw = [p for p in people if p.get("Role") == "STUDENT"]
    guardians_raw = [p for p in people if p.get("Role") == "CARER"]
    staff_raw = [p for p in people if p.get("Role") == "STAFF"]

    # Build guardian->student links from PersonPersons
    guardian_to_students = defaultdict(list)
    student_to_guardians = defaultdict(list)
    for pp in person_persons:
        gid = pp.get("Person_ID", pp.get("Person_Id", "")).strip()
        sid = pp.get("Person_ID1", pp.get("Person_Id1", "")).strip()
        if gid and sid:
            guardian_to_students[gid].append(sid)
            student_to_guardians[sid].append(gid)

    # Build enrollment groups
    enrollment_by_id = {}
    for e in enrollments:
        eid = e.get("ID", e.get("Id", "")).strip()
        name = e.get("Name", "").strip()
        school_id = e.get("School_ID", e.get("School_Id", "")).strip()
        enrollment_by_id[eid] = {"id": eid, "name": name, "school_id": school_id}

    # Build person -> enrollment links
    person_to_enrollments = defaultdict(list)
    enrollment_to_persons = defaultdict(list)
    for pe in person_enrollments:
        pid = pe.get("Person_ID", pe.get("Person_Id", "")).strip()
        eid = pe.get("Enrollment_ID", pe.get("Enrollment_Id", "")).strip()
        if pid and eid:
            person_to_enrollments[pid].append(eid)
            enrollment_to_persons[eid].append(pid)

    return {
        "people_by_id": people_by_id,
        "students_raw": students_raw,
        "guardians_raw": guardians_raw,
        "staff_raw": staff_raw,
        "guardian_to_students": guardian_to_students,
        "student_to_guardians": student_to_guardians,
        "enrollment_by_id": enrollment_by_id,
        "person_to_enrollments": person_to_enrollments,
        "enrollment_to_persons": enrollment_to_persons,
    }


# ---------------------------------------------------------------------------
# Determine grade from personnummer
# ---------------------------------------------------------------------------
# School year 2025/2026: F-klass born 2019, grade 1 born 2018, ..., grade 9 born 2010
# Adjust the reference year if needed
SCHOOL_YEAR_START = 2025  # Autumn of this year
FKLASS_BIRTH_YEAR = SCHOOL_YEAR_START - 6  # Born 2019 -> F-klass


def grade_from_birth_year(birth_year: int) -> int | None:
    """Calculate school grade from birth year. Returns 0 for F-klass, 1-9 for grades."""
    grade = FKLASS_BIRTH_YEAR - birth_year
    if 0 <= grade <= 9:
        return grade
    return None


def parse_civic_no(civic_no: str) -> tuple[date | None, int, str]:
    """Parse personnummer. Returns (birth_date, birth_year, sex)."""
    cleaned = civic_no.replace("-", "").replace(" ", "")
    try:
        if len(cleaned) == 10:
            # YYMMDD + XXXX
            yy = int(cleaned[:2])
            mm = int(cleaned[2:4])
            dd = int(cleaned[4:6])
            ctrl = cleaned[6:]
            # Determine century: if yy > 25 -> 1900s, else 2000s
            year = 1900 + yy if yy > 25 else 2000 + yy
            birth_date = date(year, mm, dd)
            sex = "Man" if int(ctrl[2]) % 2 == 1 else "Kvinna"
            return birth_date, year, sex
        elif len(cleaned) == 12:
            # YYYYMMDD + XXXX
            year = int(cleaned[:4])
            mm = int(cleaned[4:6])
            dd = int(cleaned[6:8])
            ctrl = cleaned[8:]
            birth_date = date(year, mm, dd)
            sex = "Man" if int(ctrl[2]) % 2 == 1 else "Kvinna"
            return birth_date, year, sex
    except (ValueError, IndexError):
        pass
    return None, 0, "Okänt"


# ---------------------------------------------------------------------------
# Grade-to-class-group mapping
# ---------------------------------------------------------------------------
GRADE_GROUP_NAMES = {
    0: ["FA", "FB", "FC"],
    1: ["1a", "1b", "1c"],
    2: ["2a", "2b", "2c"],
    3: ["3a", "3b", "3c"],
    4: ["4a", "4b", "4c"],
    5: ["5a", "5b", "5c"],
    6: ["6a", "6b", "6c"],
    7: ["7a", "7b", "7c"],
    8: ["8a", "8b", "8c"],
    9: ["9a", "9b", "9c"],
}


def find_eg_group_for_student(person_enrollments: list[str],
                              enrollment_by_id: dict) -> str | None:
    """Find the EG_ class group for a student from their enrollments."""
    for eid in person_enrollments:
        if eid.startswith("EG_"):
            enr = enrollment_by_id.get(eid)
            if enr:
                return enr["name"]
    return None


# ---------------------------------------------------------------------------
# Build seed data
# ---------------------------------------------------------------------------
def build_seed_data(comvius: dict) -> dict:
    """Build the complete seed data from parsed Comvius data."""

    # ---- Organisations (fixed hierarchy) ----
    org_huvudman = make_uuid("org", "huvudman")
    org_skola = make_uuid("org", "skola")
    org_grundskola = make_uuid("org", "grundskola")
    org_gymnasium = make_uuid("org", "gymnasium")

    ORGANISATIONS = [
        {
            "id": org_huvudman,
            "display_name": "Demoskolan Huvudman",
            "organisation_type": "Huvudman",
            "organisation_number": "5500000001",
            "organisation_code": "DEMO",
            "municipality_code": "0180",
            "email": "info@demoskolan.se",
            "phone_number": "08-000 00 00",
            "street_address": "Demovägen 1",
            "postal_code": "100 00",
            "locality": "Stockholm",
        },
        {
            "id": org_skola,
            "display_name": "Demoskolan",
            "organisation_type": "Skola",
            "organisation_number": "5500000002",
            "organisation_code": "DEMO_SKOLA",
            "parent_id": org_huvudman,
            "municipality_code": "0180",
            "email": "skola@demoskolan.se",
        },
        {
            "id": org_grundskola,
            "display_name": "Demoskolan Grundskola",
            "organisation_type": "Skolenhet",
            "school_unit_code": "10000001",
            "school_types": "GR",
            "parent_id": org_skola,
            "municipality_code": "0180",
        },
        {
            "id": org_gymnasium,
            "display_name": "Demoskolan Gymnasium",
            "organisation_type": "Skolenhet",
            "school_unit_code": "10000002",
            "school_types": "GY",
            "parent_id": org_skola,
            "municipality_code": "0180",
        },
    ]

    ORGS = {
        "huvudman": org_huvudman,
        "skola": org_skola,
        "grundskola": org_grundskola,
        "gymnasium": org_gymnasium,
    }

    # ---- Staff ----
    STAFF = []
    PERSONS = {}
    staff_id_map = {}  # comvius_id -> uuid

    # Duty role assignment based on email patterns or position
    # Default to Larare, use signature patterns for special roles
    SPECIAL_ROLES = {
        "Rektor": ["rektor"],
        "Kurator": ["kurator"],
        "Skoladministrator": ["admin"],
    }

    for s in comvius["staff_raw"]:
        cid = s["Id"].strip()
        first = s.get("FirstName", "").strip()
        last = s.get("LastName", "").strip()
        email = s.get("Email", "").strip() or None
        if email == "NULL":
            email = None
        civic_no = s.get("PersonalIdNumber", "").strip() or None
        if civic_no == "NULL":
            civic_no = None

        if not first and not last:
            continue

        person_uuid = make_uuid("staff", cid)
        staff_id_map[cid] = person_uuid
        PERSONS[f"staff_{first.lower()}_{last.lower()}"] = person_uuid

        birth_date, birth_year, sex = ("", 0, "Okänt")
        if civic_no:
            birth_date, birth_year, sex = parse_civic_no(civic_no)

        # Derive signature from email
        signature = None
        if email:
            signature = email.split("@")[0]

        # Determine duty role
        duty_role = "Larare"
        enrollments = comvius["person_to_enrollments"].get(cid, [])
        # Check if staff is in class groups (F-3) -> might be Barnskotare
        in_kl_groups = any(e.startswith("KL_") for e in enrollments)
        in_eg_groups = any(e.startswith("EG_") for e in enrollments)
        in_teaching = any(e.startswith("FG_") or e.startswith("L_") for e in enrollments)

        if not in_teaching and (in_kl_groups or in_eg_groups):
            # Staff in class groups but not teaching -> likely Barnskotare/assistant
            duty_role = "Barnskotare/Elevassistent"

        staff_dict = {
            "id": person_uuid,
            "given_name": first,
            "family_name": last,
            "email": email,
            "edu_person_principal_name": email,
            "duty_role": duty_role,
            "signature": signature,
            "description": duty_role,
            "sex": sex,
            "civic_no": civic_no,
            "birth_date": birth_date or None,
            "external_id": cid,
        }
        STAFF.append(staff_dict)

    # ---- Class groups (from EG_ enrollments) ----
    # Build groups from the 30 EG_ groups that have students
    eg_groups = {}
    for eid, enr in comvius["enrollment_by_id"].items():
        if eid.startswith("EG_"):
            name = enr["name"]
            persons_in = comvius["enrollment_to_persons"].get(eid, [])
            # Only include groups that have students (check if any person is a student)
            student_ids_in = [
                pid for pid in persons_in
                if comvius["people_by_id"].get(pid, {}).get("Role") == "STUDENT"
            ]
            if not student_ids_in:
                continue

            # Determine grade from group name
            grade = None
            if name in ("FA", "FB", "FC"):
                grade = 0
            else:
                m = re.match(r"(\d+)", name)
                if m:
                    grade = int(m.group(1))

            eg_groups[name] = {
                "eid": eid,
                "name": name,
                "grade": grade,
                "student_comvius_ids": student_ids_in,
                "staff_comvius_ids": [
                    pid for pid in persons_in
                    if comvius["people_by_id"].get(pid, {}).get("Role") == "STAFF"
                ],
            }

    # Find staff mentors for each class group
    # For F-3: use staff from KL_ groups
    # For 4-9: derive from mentor groups (KL_ with grade:signature pattern)
    kl_groups_staff = {}  # group_name -> [staff_ids]
    mentor_groups_by_class = defaultdict(list)  # class_name -> [(mentor_name, staff_ids, student_ids)]

    for eid, enr in comvius["enrollment_by_id"].items():
        if not eid.startswith("KL_"):
            continue
        name = enr["name"]
        persons_in = comvius["enrollment_to_persons"].get(eid, [])
        staff_in = [
            pid for pid in persons_in
            if comvius["people_by_id"].get(pid, {}).get("Role") == "STAFF"
        ]
        student_in = [
            pid for pid in persons_in
            if comvius["people_by_id"].get(pid, {}).get("Role") == "STUDENT"
        ]

        # KL_ class groups (matching EG_ names like "1a", "FA")
        if name in eg_groups:
            kl_groups_staff[name] = staff_in
        # Mentor groups (grade:signature pattern like "4a:jonjoh")
        elif ":" in name:
            # Extract the class prefix (e.g., "4a" from "4a:jonjoh", "5" from "5:camedl")
            prefix = name.split(":")[0]
            # Map mentor students to their EG_ class group
            class_assignments = defaultdict(int)
            for sid in student_in:
                eg_name = find_eg_group_for_student(
                    comvius["person_to_enrollments"].get(sid, []),
                    comvius["enrollment_by_id"]
                )
                if eg_name:
                    class_assignments[eg_name] += 1
            mentor_groups_by_class[name] = {
                "staff_ids": staff_in,
                "student_ids": student_in,
                "class_assignments": dict(class_assignments),
                "prefix": prefix,
            }

    # Assign mentors to each class group
    class_mentors = {}  # group_name -> [staff_comvius_ids]

    for gname, gdata in eg_groups.items():
        grade = gdata["grade"]
        mentors = []

        # First try KL_ staff
        if gname in kl_groups_staff and kl_groups_staff[gname]:
            mentors = kl_groups_staff[gname][:2]  # Max 2 mentors from KL_

        # For grades 4-9, also check mentor groups
        if not mentors and grade is not None and grade >= 4:
            # Find mentor groups whose students are mostly in this class
            best_mentors = []
            for mname, mdata in mentor_groups_by_class.items():
                ca = mdata["class_assignments"]
                if gname in ca and ca[gname] > 0:
                    # This mentor group has students in this class
                    best_mentors.append((ca[gname], mdata["staff_ids"]))
            best_mentors.sort(key=lambda x: -x[0])
            for _, staff_ids in best_mentors[:2]:
                for sid in staff_ids:
                    if sid not in mentors:
                        mentors.append(sid)

        # Fallback: use staff from EG_ group itself
        if not mentors and gdata["staff_comvius_ids"]:
            mentors = gdata["staff_comvius_ids"][:2]

        class_mentors[gname] = mentors

    # Build GROUPS_DATA
    GROUPS_DATA = []
    GROUPS = {}
    group_uuid_map = {}  # group_name -> uuid

    for gname in sorted(eg_groups.keys(), key=lambda n: (eg_groups[n]["grade"] or 0, n)):
        gdata = eg_groups[gname]
        group_uuid = make_uuid("group", gname)
        group_uuid_map[gname] = group_uuid
        GROUPS[gname] = group_uuid

        mentor_id = None
        mentors = class_mentors.get(gname, [])
        if mentors and mentors[0] in staff_id_map:
            mentor_id = staff_id_map[mentors[0]]

        GROUPS_DATA.append({
            "id": group_uuid,
            "display_name": gname,
            "group_code": gname,
            "group_type": "Klass",
            "school_type": "GR",
            "organisation_id": org_grundskola,
            "start_date": date(2024, 8, 15),
            "mentor_id": mentor_id,
        })

    # ---- Students ----
    STUDENTS = []
    student_id_map = {}  # comvius_id -> uuid

    # Track class group assignments for students without EG_ groups
    class_group_counts = defaultdict(int)
    for gname, gdata in eg_groups.items():
        class_group_counts[gname] = len(gdata["student_comvius_ids"])

    for s in comvius["students_raw"]:
        cid = s["Id"].strip()
        first = s.get("FirstName", "").strip()
        last = s.get("LastName", "").strip()
        email = s.get("Email", "").strip() or None
        if email == "NULL":
            email = None
        civic_no = s.get("PersonalIdNumber", "").strip() or None
        if civic_no == "NULL":
            civic_no = None

        if not first and not last:
            continue
        if not civic_no:
            continue

        birth_date, birth_year, sex = parse_civic_no(civic_no)

        # Find class group from EG_ enrollment — this is the authoritative grade source
        enrollments = comvius["person_to_enrollments"].get(cid, [])
        class_group_name = find_eg_group_for_student(enrollments, comvius["enrollment_by_id"])

        # Determine grade from class group first, then fall back to birth year
        if class_group_name and class_group_name in eg_groups:
            grade = eg_groups[class_group_name]["grade"]
        else:
            grade = grade_from_birth_year(birth_year)

        if grade is None:
            continue  # Skip graduated/inactive students

        person_uuid = make_uuid("student", cid)
        student_id_map[cid] = person_uuid
        PERSONS[f"student_{first.lower()}_{last.lower()}"] = person_uuid

        # If no class group, assign to the smallest group for this grade
        if not class_group_name and grade in GRADE_GROUP_NAMES:
            candidates = [n for n in GRADE_GROUP_NAMES[grade] if n in group_uuid_map]
            if candidates:
                # Pick the one with fewest students
                class_group_name = min(candidates, key=lambda n: class_group_counts[n])
                class_group_counts[class_group_name] += 1

        group_id = group_uuid_map.get(class_group_name)

        # Get guardian IDs
        guardian_comvius_ids = comvius["student_to_guardians"].get(cid, [])

        STUDENTS.append({
            "id": person_uuid,
            "given_name": first,
            "family_name": last,
            "email": email,
            "guardian_comvius_ids": guardian_comvius_ids,  # resolve after guardians built
            "school_unit_id": org_grundskola,
            "school_year": grade if grade > 0 else None,
            "civic_no": civic_no,
            "sex": sex,
            "external_id": cid,
            "birth_date": birth_date or None,
            "group_id": group_id,
            "group_name": class_group_name,
        })

    # ---- Guardians ----
    GUARDIANS = []
    guardian_id_map = {}  # comvius_id -> uuid

    for g in comvius["guardians_raw"]:
        cid = g["Id"].strip()
        first = g.get("FirstName", "").strip()
        last = g.get("LastName", "").strip()
        email = g.get("Email", "").strip() or None
        if email == "NULL":
            email = None
        phone = g.get("Phone", "").strip() or None
        if phone == "NULL":
            phone = None

        if not first and not last:
            continue

        # Check if this guardian is linked to any active student
        linked_students = comvius["guardian_to_students"].get(cid, [])
        has_active_student = any(sid in student_id_map for sid in linked_students)
        if not has_active_student:
            # Guardian not linked to any active student - skip
            # (unless they're the only guardian option)
            pass  # Include anyway, dedup happens in the linking step

        person_uuid = make_uuid("guardian", cid)
        guardian_id_map[cid] = person_uuid
        PERSONS[f"guardian_{first.lower()}_{last.lower()}"] = person_uuid

        # Try to determine sex from personnummer
        sex = None
        civic_no = g.get("PersonalIdNumber", "").strip() or None
        if civic_no == "NULL":
            civic_no = None
        if civic_no:
            _, _, sex = parse_civic_no(civic_no)

        GUARDIANS.append({
            "id": person_uuid,
            "given_name": first,
            "family_name": last,
            "email": email,
            "phone_number": phone,
            "external_id": cid,
            "street_address": None,
            "postal_code": None,
            "locality": None,
            "sex": sex,
        })

    # ---- Resolve guardian IDs on students ----
    # Also create synthetic guardians for students who have none
    synthetic_guardian_counter = 0
    for student in STUDENTS:
        guardian_ids = []
        for gcid in student.pop("guardian_comvius_ids", []):
            if gcid in guardian_id_map:
                guardian_ids.append(guardian_id_map[gcid])

        if not guardian_ids:
            # Create a synthetic guardian pair
            for i in range(2):
                synthetic_guardian_counter += 1
                syn_id = make_uuid("syn_guardian", f"{student['id']}_{i}")
                syn_first = f"Förälder{synthetic_guardian_counter}"
                syn_last = student["family_name"]
                syn_email = f"foralder{synthetic_guardian_counter}.{syn_last.lower().replace(' ', '')}@example.se"
                syn_phone = f"070-{100 + synthetic_guardian_counter:03d} 00 {synthetic_guardian_counter:02d}"

                GUARDIANS.append({
                    "id": syn_id,
                    "given_name": syn_first,
                    "family_name": syn_last,
                    "email": syn_email,
                    "phone_number": syn_phone,
                    "external_id": f"syn_{synthetic_guardian_counter}",
                    "street_address": None,
                    "postal_code": None,
                    "locality": None,
                    "sex": "Kvinna" if i == 0 else "Man",
                })
                guardian_ids.append(syn_id)
                PERSONS[f"guardian_syn_{syn_first.lower()}_{syn_last.lower()}"] = syn_id

        student["guardian_ids"] = guardian_ids

    # ---- Teaching groups (simplified from FG_ Comvius data) ----
    TEACHING_GROUPS_DATA = []
    TEACHING_GROUPS = {}

    # Build teaching groups from FG_ enrollment groups that match class names
    for eid, enr in comvius["enrollment_by_id"].items():
        if not eid.startswith("FG_"):
            continue
        name = enr["name"]
        persons_in = comvius["enrollment_to_persons"].get(eid, [])
        student_in = [
            pid for pid in persons_in
            if pid in student_id_map
        ]
        if not student_in:
            continue

        tg_uuid = make_uuid("teaching_group", eid)
        TEACHING_GROUPS[name] = tg_uuid

        # Find which class groups these students belong to
        class_ids_set = set()
        for sid in student_in:
            for st in STUDENTS:
                if st["external_id"] == sid and st.get("group_id"):
                    class_ids_set.add(st["group_id"])
                    break

        TEACHING_GROUPS_DATA.append({
            "id": tg_uuid,
            "display_name": name,
            "group_code": name,
            "group_type": "Undervisning",
            "organisation_id": org_grundskola,
            "start_date": date(2024, 8, 15),
            "class_ids": list(class_ids_set),
        })

    # ---- Activities (generate one per teaching group) ----
    ACTIVITIES_DATA = []
    for tg in TEACHING_GROUPS_DATA:
        act_uuid = make_uuid("activity", tg["id"])
        # Find a teacher for this activity from staff in the FG_ group
        teacher_ids = []
        tg_name = tg["display_name"]
        # Find the FG_ enrollment that matches
        for eid, enr in comvius["enrollment_by_id"].items():
            if eid.startswith("FG_") and enr["name"] == tg_name:
                persons_in = comvius["enrollment_to_persons"].get(eid, [])
                teacher_ids = [
                    staff_id_map[pid] for pid in persons_in
                    if pid in staff_id_map
                ]
                break

        ACTIVITIES_DATA.append({
            "id": act_uuid,
            "display_name": tg_name,
            "subject_code": None,
            "subject_name": tg_name,
            "activity_type": "Undervisning",
            "organisation_id": org_grundskola,
            "start_date": date(2024, 8, 15),
            "teacher_ids": teacher_ids[:3],  # Max 3 teachers
            "group_ids": [tg["id"]],
        })

    # ---- Ensure every class group has a mentor ----
    # If any group still lacks a mentor, assign one from staff not yet mentoring
    mentoring_staff = set()
    for gd in GROUPS_DATA:
        if gd.get("mentor_id"):
            mentoring_staff.add(gd["mentor_id"])

    available_staff = [s for s in STAFF if s["id"] not in mentoring_staff and s["duty_role"] == "Larare"]
    avail_idx = 0

    for gd in GROUPS_DATA:
        if not gd.get("mentor_id") and available_staff:
            gd["mentor_id"] = available_staff[avail_idx % len(available_staff)]["id"]
            mentoring_staff.add(gd["mentor_id"])
            avail_idx += 1

    return {
        "ORGANISATIONS": ORGANISATIONS,
        "ORGS": ORGS,
        "STAFF": STAFF,
        "STUDENTS": STUDENTS,
        "GUARDIANS": GUARDIANS,
        "GROUPS_DATA": GROUPS_DATA,
        "GROUPS": GROUPS,
        "TEACHING_GROUPS_DATA": TEACHING_GROUPS_DATA,
        "TEACHING_GROUPS": TEACHING_GROUPS,
        "ACTIVITIES_DATA": ACTIVITIES_DATA,
        "PERSONS": PERSONS,
    }


# ---------------------------------------------------------------------------
# Write seed data Python file
# ---------------------------------------------------------------------------
def format_value(v, indent=4):
    """Format a Python value for source code output."""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, date):
        return f"date({v.year}, {v.month}, {v.day})"
    if isinstance(v, list):
        if not v:
            return "[]"
        items = ", ".join(format_value(i, indent) for i in v)
        if len(items) < 80:
            return f"[{items}]"
        sep = f",\n{' ' * (indent + 4)}"
        items = sep.join(format_value(i, indent + 4) for i in v)
        return f"[\n{' ' * (indent + 4)}{items},\n{' ' * indent}]"
    if isinstance(v, dict):
        items = []
        for k2, v2 in v.items():
            items.append(f"{repr(k2)}: {format_value(v2, indent + 4)}")
        if len(", ".join(items)) < 60:
            return "{" + ", ".join(items) + "}"
        sep = f",\n{' ' * (indent + 4)}"
        return "{\n" + " " * (indent + 4) + sep.join(items) + ",\n" + " " * indent + "}"
    return repr(v)


def write_seed_file(data: dict, output_path: str):
    """Write the seed data to a Python file."""
    lines = [
        '"""',
        'Anonymized production data for Demo SIS.',
        'Generated by scripts/build_from_comvius.py — DO NOT EDIT MANUALLY.',
        'Contains zero real PII — safe to commit.',
        '"""',
        'from datetime import date',
        '',
        '# Organisation UUIDs',
    ]

    # ORGS
    lines.append("ORGS = {")
    for k, v in data["ORGS"].items():
        lines.append(f'    {repr(k)}: {repr(v)},')
    lines.append("}")
    lines.append("")

    # PERSONS (just a subset of keys for lookup)
    lines.append("# Person UUIDs (staff, students, guardians)")
    lines.append("PERSONS = {")
    # Only include a manageable subset
    for k, v in sorted(data["PERSONS"].items()):
        lines.append(f'    {repr(k)}: {repr(v)},')
    lines.append("}")
    lines.append("")

    # GROUPS
    lines.append("# Group UUIDs")
    lines.append("GROUPS = {")
    for k, v in sorted(data["GROUPS"].items()):
        lines.append(f'    {repr(k)}: {repr(v)},')
    lines.append("}")
    lines.append("")

    # TEACHING_GROUPS
    lines.append("# Teaching group UUIDs")
    lines.append("TEACHING_GROUPS = {")
    for k, v in sorted(data["TEACHING_GROUPS"].items()):
        lines.append(f'    {repr(k)}: {repr(v)},')
    lines.append("}")
    lines.append("")

    # ORGANISATIONS
    lines.append("# Organisation hierarchy")
    lines.append("ORGANISATIONS = [")
    for org in data["ORGANISATIONS"]:
        lines.append("    {")
        for k, v in org.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # STAFF
    lines.append(f"# Staff ({len(data['STAFF'])} members)")
    lines.append("STAFF = [")
    for staff in data["STAFF"]:
        lines.append("    {")
        for k, v in staff.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # GUARDIANS
    lines.append(f"# Guardians ({len(data['GUARDIANS'])} persons)")
    lines.append("GUARDIANS = [")
    for g in data["GUARDIANS"]:
        lines.append("    {")
        for k, v in g.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # GROUPS_DATA
    lines.append(f"# Class groups ({len(data['GROUPS_DATA'])} groups)")
    lines.append("GROUPS_DATA = [")
    for g in data["GROUPS_DATA"]:
        lines.append("    {")
        for k, v in g.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # TEACHING_GROUPS_DATA
    lines.append(f"# Teaching groups ({len(data['TEACHING_GROUPS_DATA'])} groups)")
    lines.append("TEACHING_GROUPS_DATA = [")
    for g in data["TEACHING_GROUPS_DATA"]:
        lines.append("    {")
        for k, v in g.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # STUDENTS (last, since they reference guardian and group UUIDs)
    lines.append(f"# Students ({len(data['STUDENTS'])} persons)")
    lines.append("STUDENTS = [")
    for s in data["STUDENTS"]:
        # Remove internal fields
        out = {k: v for k, v in s.items() if k not in ("group_name",)}
        lines.append("    {")
        for k, v in out.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # ACTIVITIES_DATA
    lines.append(f"# Activities ({len(data['ACTIVITIES_DATA'])} activities)")
    lines.append("ACTIVITIES_DATA = [")
    for a in data["ACTIVITIES_DATA"]:
        lines.append("    {")
        for k, v in a.items():
            lines.append(f"        {repr(k)}: {format_value(v, 8)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Build seed data from Comvius export")
    parser.add_argument(
        "--zip",
        default=os.path.join(os.path.dirname(__file__), "..", "comvius_anon.zip"),
        help="Path to comvius_anon.zip",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(__file__), "..", "app", "seed", "schoolsoft_data.py"),
        help="Output path for seed data",
    )
    args = parser.parse_args()

    zip_path = os.path.abspath(args.zip)
    output_path = os.path.abspath(args.output)

    print(f"Reading Comvius data from {zip_path}...")
    comvius = parse_comvius(zip_path)

    print(f"  People: {len(comvius['students_raw'])} students, "
          f"{len(comvius['guardians_raw'])} guardians, "
          f"{len(comvius['staff_raw'])} staff")
    print(f"  Guardian links: {sum(len(v) for v in comvius['guardian_to_students'].values())}")
    print(f"  Enrollments: {len(comvius['enrollment_by_id'])} groups")

    print("Building seed data...")
    data = build_seed_data(comvius)

    # Validation
    students_without_guardians = [s for s in data["STUDENTS"] if not s.get("guardian_ids")]
    students_without_groups = [s for s in data["STUDENTS"] if not s.get("group_id")]
    groups_without_mentors = [g for g in data["GROUPS_DATA"] if not g.get("mentor_id")]

    print(f"\nSeed data summary:")
    print(f"  Staff: {len(data['STAFF'])}")
    print(f"  Students: {len(data['STUDENTS'])}")
    print(f"  Guardians: {len(data['GUARDIANS'])}")
    print(f"  Class groups: {len(data['GROUPS_DATA'])}")
    print(f"  Teaching groups: {len(data['TEACHING_GROUPS_DATA'])}")
    print(f"  Activities: {len(data['ACTIVITIES_DATA'])}")
    print(f"\nValidation:")
    print(f"  Students without guardians: {len(students_without_guardians)}")
    print(f"  Students without class group: {len(students_without_groups)}")
    print(f"  Class groups without mentor: {len(groups_without_mentors)}")

    if students_without_guardians:
        print("  WARNING: Some students have no guardians!")
        for s in students_without_guardians[:5]:
            print(f"    {s['given_name']} {s['family_name']} (grade {s.get('school_year')})")

    if groups_without_mentors:
        print("  WARNING: Some class groups have no mentor!")
        for g in groups_without_mentors:
            print(f"    {g['display_name']}")

    print(f"\nWriting seed data to {output_path}...")
    write_seed_file(data, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
