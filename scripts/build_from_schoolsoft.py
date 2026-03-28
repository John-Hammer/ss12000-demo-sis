"""
Convert SchoolSoft TSV exports into SS12000 seed data for the demo SIS.

Reads TSV files from a directory (staff.txt, students.txt, parents.txt, groups.txt, lessons.txt)
and generates app/seed/schoolsoft_data.py with all entities mapped to SS12000 format.

Supports PII anonymization (--anonymize) for use with original/production data.

Usage:
    # From original data with anonymization (recommended):
    python -m scripts.build_from_schoolsoft --tsv-dir Schoolsoft_TSV --anonymize --seed 42

    # From pre-anonymized demo data:
    python -m scripts.build_from_schoolsoft --tsv-dir ../skolSköld/demo_schoolsoft_tsv
"""
import argparse
import csv
import hashlib
import re
import uuid
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .anonymizer import (
    anonymize_first_name, anonymize_last_name, anonymize_personnummer,
    anonymize_email_staff, anonymize_email_student, anonymize_email_guardian,
    anonymize_phone, anonymize_address, anonymize_signature, anonymize_username,
)


# --- Deterministic UUID generation ---

NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def make_uuid(entity_type: str, identifier: str) -> str:
    """Generate a deterministic UUID5 from entity type + identifier."""
    return str(uuid.uuid5(NAMESPACE, f"{entity_type}:{identifier}"))


# --- SchoolSoft type → SS12000 duty role mapping ---

STAFF_TYPE_TO_DUTY_ROLE = {
    "0": "Lärare",
    "1": "Rektor",
    "2": "Övrig pedagogisk personal",
    "3": "Övrig personal",
    "4": "Övrig personal",
}

# --- Lesson subject code mapping ---

SUBJECT_CODE_MAP = {
    # Core subjects
    "Sv": ("SV", "Svenska"),
    "Sven": ("SVA", "Svenska som andraspråk"),
    "sva 1-9": ("SVA", "Svenska som andraspråk"),
    "Ma": ("MA", "Matematik"),
    "En": ("EN", "Engelska"),
    # SO block
    "So": ("SO", "Samhällsorienterande ämnen"),
    "Hi": ("HI", "Historia"),
    "Ge": ("GE", "Geografi"),
    "Re": ("RE", "Religionskunskap"),
    "Sh": ("SH", "Samhällskunskap"),
    # NO block
    "NO": ("NO", "Naturorienterande ämnen"),
    "No-lab": ("NO", "Naturorienterande ämnen"),
    "Bi": ("BI", "Biologi"),
    "Fy": ("FY", "Fysik"),
    "Ke": ("KE", "Kemi"),
    # Practical / aesthetic
    "Idh": ("IDH", "Idrott och hälsa"),
    "Mu": ("MU", "Musik"),
    "Bl": ("BL", "Bild"),
    "Sl": ("SL", "Slöjd"),
    "Hkk": ("HKK", "Hem- och konsumentkunskap"),
    "Tk": ("TK", "Teknik"),
    # Languages
    "Sp": ("ML-SP", "Moderna språk - Spanska"),
    "C-språk sp": ("ML-SP", "Moderna språk - Spanska"),
    "fr": ("ML-FR", "Moderna språk - Franska"),
    "C-språk fr": ("ML-FR", "Moderna språk - Franska"),
    "Ty": ("ML-TY", "Moderna språk - Tyska"),
    "C-språk ty": ("ML-TY", "Moderna språk - Tyska"),
    "C-språk md": ("ML", "Moderna språk"),
    "Modersmål": ("MOD", "Modersmål"),
    # Other teaching
    "Tema": ("TEMA", "Tema"),
    "Retorik": ("RET", "Retorik"),
    "kör": ("KOR", "Kör"),
    "Ensemble": ("ENS", "Ensemble"),
}

SKIP_SUBJECTS = {
    # Non-teaching / admin
    "Lektion", "Lunch", "Rast", "Vikarieanskaffning", "Klassråd",
    "Elevrapport F-3", "Elevrapport 4-6", "Elevrapport 7-9",
    "Elevråd", "elevråd", "STÖDLÄXLÄSNING",
    # Staff meetings / collaboration
    "Samverkan åk 1", "Samverkan åk 2", "Samverkan åk 3", "Samverkan åk F",
    "Samverkan", "SamvIdh", "SamvHÄLSA",
    "A-lagskonferens åk 1", "A-lagskonferens åk 2", "A-lagskonferens åk 3",
    "A-lagskonferens åk 4", "A-lagskonferens åk 5", "A-lagskonferens åk 6",
    "A-lagskonferens åk 7", "A-lagskonferens åk 8", "A-lagskonferens åk 9",
    "A-lagskonferens åk F",
    "EHM", "EHM ÅK 1",
    # Admin / non-lesson
    "Adm", "Arbetstid", "Studietid",
    "Trygghetsdag", "SkV Utflykt", "No-dag",
    "Rörelse", "Skapande f-klass",
    "Omprovstid åk 7-9", "Ta igen tid 4-6", "Ta igen tid 7-9",
    "Resurs 4", "Resurs 5", "Resurs 7", "Resurs 8",
    # Special math groups (sub-groups, not standalone activities)
    "specma4", "specma5", "specma6",
    "specma4PL", "specma5PL", "specma6ÅP",
    # Other non-teaching
    "mentor", "Utmaning", "RV",
}


def parse_tsv(filepath: Path) -> list[dict]:
    """Parse a TSV file into list of dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def parse_sex(raw: str) -> str | None:
    """Map SchoolSoft sex field to SS12000."""
    if raw == "m":
        return "Man"
    if raw == "f":
        return "Kvinna"
    return None


def parse_civic_no(socialnumber: str) -> str | None:
    """Normalize personnummer to YYYYMMDD-XXXX format."""
    if not socialnumber:
        return None
    s = socialnumber.strip().replace(" ", "")
    # Handle YYMMDD-XXXX → 19YYMMDD-XXXX or 20YYMMDD-XXXX
    if len(s) == 11 and s[6] == "-":
        yy = int(s[:2])
        century = "20" if yy < 30 else "19"
        s = century + s
    return s if len(s) >= 12 else None


def birth_date_from_civic(civic_no: str | None) -> str | None:
    """Extract birth date string from civic_no, validating it's a real date."""
    if not civic_no or len(civic_no) < 8:
        return None
    try:
        y, m, d = int(civic_no[:4]), int(civic_no[4:6]), int(civic_no[6:8])
        date(y, m, d)  # validate
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (ValueError, OverflowError):
        return None


def map_group_to_class(group_name: str, class_names: set[str]) -> str | None:
    """Map a lesson group name (e.g. '4a1SUSANNE') back to its class group ('4a')."""
    if group_name in class_names:
        return group_name
    # Try prefix match, longest class name first
    for cg in sorted(class_names, key=len, reverse=True):
        if len(cg) >= 2 and group_name.startswith(cg):
            return cg
    return None


def determine_school_year(class_name: str) -> int | None:
    """Extract school year from class name like '4a' -> 4, 'FA' -> 0."""
    if class_name.startswith("F"):
        return 0
    m = re.match(r"^(\d+)", class_name)
    if m:
        return int(m.group(1))
    return None


def infer_mentors_from_lessons(
    lesson_rows: list[dict],
    class_names: set[str],
    staff_by_username: dict[str, str],
    group_mentor_map: dict[str, list[str]],
) -> None:
    """Infer mentors for class groups that have no teacher assignment in groups.txt.

    Finds the teacher with the most lesson occurrences for each class
    and assigns them as mentor.
    """
    classes_needing_mentors = {cn for cn, mentors in group_mentor_map.items() if not mentors}
    if not classes_needing_mentors:
        return

    skip_days = {"", "blank", "sat", "sun", "lör", "sön", "saturday", "sunday"}
    teacher_class_counts: Counter = Counter()

    for row in lesson_rows:
        day = row.get("day", "").strip().lower()
        teacher_str = row.get("teacher", "").strip()
        group_str = row.get("group", "").strip()

        if day in skip_days or not teacher_str or not group_str:
            continue

        teachers = [t.strip() for t in teacher_str.split(",") if t.strip()]
        groups = [g.strip() for g in group_str.split(",") if g.strip()]

        for teacher in teachers:
            if teacher not in staff_by_username:
                continue
            for g in groups:
                mapped = map_group_to_class(g, class_names)
                if mapped and mapped in classes_needing_mentors:
                    teacher_class_counts[(teacher, mapped)] += 1

    # Pick the teacher with the most lessons per class
    best: dict[str, tuple[str, int]] = {}
    for (teacher, class_name), count in teacher_class_counts.items():
        if class_name not in best or count > best[class_name][1]:
            best[class_name] = (teacher, count)

    for class_name, (teacher_username, _count) in best.items():
        teacher_id = staff_by_username[teacher_username]
        group_mentor_map[class_name] = [teacher_id]


def build_data(tsv_dir: Path) -> dict:
    """Build all SS12000 entities from SchoolSoft TSV files."""

    # --- Read all TSV files ---
    staff_rows = parse_tsv(tsv_dir / "staff.txt")
    student_rows = parse_tsv(tsv_dir / "students.txt")
    parent_rows = parse_tsv(tsv_dir / "parents.txt")
    group_rows = parse_tsv(tsv_dir / "groups.txt")
    lesson_rows = parse_tsv(tsv_dir / "lessons.txt")

    # --- Organisation hierarchy ---
    org_huvudman_id = make_uuid("org", "huvudman")
    org_school_id = make_uuid("org", "school")
    org_grundskola_id = make_uuid("org", "grundskola")

    organisations = [
        {
            "id": org_huvudman_id,
            "display_name": "Demoskolan Huvudman",
            "organisation_type": "Huvudman",
            "organisation_code": "DEMO",
        },
        {
            "id": org_school_id,
            "display_name": "Demoskolan",
            "organisation_type": "Skola",
            "parent_id": org_huvudman_id,
        },
        {
            "id": org_grundskola_id,
            "display_name": "Demoskolan Grundskola",
            "organisation_type": "Skolenhet",
            "school_unit_code": "12345678",
            "school_types": "GR",
            "parent_id": org_school_id,
        },
    ]

    # --- Staff ---
    staff_list = []
    staff_by_username = {}  # username -> person_id
    staff_by_id = {}  # SchoolSoft id -> person_id

    for row in staff_rows:
        ss_id = row.get("id", "").strip()
        username = row.get("username", "").strip()
        if not ss_id or not username:
            continue

        person_id = make_uuid("staff", ss_id)
        staff_by_username[username] = person_id
        staff_by_id[ss_id] = person_id

        staff_type = row.get("type", "0").strip()
        duty_role = STAFF_TYPE_TO_DUTY_ROLE.get(staff_type, "Övrig personal")
        civic_no = parse_civic_no(row.get("socialnumber", ""))

        staff_list.append({
            "id": person_id,
            "given_name": row.get("fname", "").strip(),
            "family_name": row.get("lname", "").strip(),
            "email": row.get("email", "").strip() or None,
            "edu_person_principal_name": row.get("email", "").strip() or None,
            "civic_no": civic_no,
            "birth_date": birth_date_from_civic(civic_no),
            "phone_number": row.get("mobile", "").strip() or None,
            "street_address": row.get("address1", "").strip() or None,
            "postal_code": row.get("pocode", "").strip() or None,
            "locality": row.get("city", "").strip() or None,
            "external_id": ss_id,
            "duty_role": duty_role,
            "signature": row.get("initial", "").strip() or username,
        })

    # --- Students ---
    student_list = []
    student_by_id = {}  # SchoolSoft id -> person_id
    student_class = {}  # SchoolSoft id -> class name

    # Build class list from groups
    class_groups_info = {}  # name -> group row
    for row in group_rows:
        if row.get("classtype") == "1":
            class_groups_info[row["name"]] = row

    class_names = set(class_groups_info.keys())

    for row in student_rows:
        ss_id = row.get("id", "").strip()
        if not ss_id:
            continue
        if row.get("active", "1") != "1":
            continue

        person_id = make_uuid("student", ss_id)
        student_by_id[ss_id] = person_id

        class_name = row.get("class", "").strip()
        student_class[ss_id] = class_name

        school_year = determine_school_year(class_name)
        civic_no = parse_civic_no(row.get("socialnumber", ""))
        sex = parse_sex(row.get("sex", "").strip())

        student_list.append({
            "id": person_id,
            "given_name": row.get("fname", "").strip(),
            "family_name": row.get("lname", "").strip(),
            "email": row.get("email", "").strip() or None,
            "civic_no": civic_no,
            "birth_date": birth_date_from_civic(civic_no),
            "sex": sex,
            "external_id": ss_id,
            "school_unit_id": org_grundskola_id,
            "school_year": school_year,
            "group_id": None,  # filled in below
            "guardian_ids": [],  # filled in below
        })

    # --- Groups (class groups only, classtype=1) ---
    groups_data = []
    group_id_map = {}  # group name -> SS12000 group UUID
    group_mentor_map = {}  # group name -> list of teacher person_ids

    for name, row in class_groups_info.items():
        ss_id = row.get("id", "").strip()
        group_id = make_uuid("group", ss_id)
        group_id_map[name] = group_id

        # Parse teachers (mentors) from group row
        teacher_usernames = [t.strip() for t in row.get("teacher", "").split(",") if t.strip()]
        mentor_ids = []
        for tu in teacher_usernames:
            pid = staff_by_username.get(tu)
            if pid:
                mentor_ids.append(pid)

        group_mentor_map[name] = mentor_ids

        school_year = determine_school_year(name)
        school_type = "GR"

        groups_data.append({
            "id": group_id,
            "display_name": name,
            "group_code": name,
            "group_type": "Klass",
            "school_type": school_type,
            "organisation_id": org_grundskola_id,
            "start_date": "2024-08-15",
            "mentor_id": None,  # assigned after mentor inference
        })

    # --- Infer mentors for classes without teacher assignments ---
    infer_mentors_from_lessons(lesson_rows, class_names, staff_by_username, group_mentor_map)

    # Assign mentor_id to groups from (possibly inferred) mentor map
    for g in groups_data:
        mentors = group_mentor_map.get(g["display_name"], [])
        g["mentor_id"] = mentors[0] if mentors else None

    # Assign group_id to students
    for s in student_list:
        class_name = student_class.get(s["external_id"], "")
        if class_name in group_id_map:
            s["group_id"] = group_id_map[class_name]

    # --- Parents/Guardians ---
    guardian_list = []
    guardian_by_id = {}  # parent SchoolSoft id -> person_id
    student_guardian_links = defaultdict(list)  # student_ss_id -> [guardian_person_id]

    for row in parent_rows:
        parent_id = row.get("id", "").strip()
        if not parent_id:
            continue

        student_ids_raw = row.get("studentid", "").strip()
        if not student_ids_raw:
            continue

        # Multiple students possible (comma-separated)
        linked_student_ids = [sid.strip() for sid in student_ids_raw.split(",") if sid.strip()]
        # Only keep parents that link to students we have
        valid_student_ids = [sid for sid in linked_student_ids if sid in student_by_id]
        if not valid_student_ids:
            continue

        person_id = make_uuid("guardian", parent_id)
        guardian_by_id[parent_id] = person_id

        for sid in valid_student_ids:
            student_guardian_links[sid].append(person_id)

        civic_no = parse_civic_no(row.get("studentsocialnumber", "").split(",")[0] if row.get("studentsocialnumber") else "")

        guardian_list.append({
            "id": person_id,
            "given_name": row.get("fname1", "").strip(),
            "family_name": row.get("lname1", "").strip(),
            "email": row.get("email1", "").strip() or None,
            "phone_number": row.get("mobile1", "").strip() or None,
            "street_address": row.get("address1", "").strip() or None,
            "postal_code": row.get("pocode", "").strip() or None,
            "locality": row.get("city", "").strip() or None,
            "external_id": parent_id,
        })

    # Assign guardian_ids to students
    for s in student_list:
        s["guardian_ids"] = student_guardian_links.get(s["external_id"], [])

    # --- Deduplicate guardians (same parent can appear multiple times) ---
    seen_guardian_ids = set()
    unique_guardians = []
    for g in guardian_list:
        if g["id"] not in seen_guardian_ids:
            seen_guardian_ids.add(g["id"])
            unique_guardians.append(g)
    guardian_list = unique_guardians

    # --- Activities from lessons ---
    # An Activity in SS12000 = a subject taught by a teacher to a group of students
    # We aggregate lessons into (subject, teacher) -> set of class groups

    skip_days = {"", "blank", "sat", "sun", "lör", "sön", "saturday", "sunday"}
    activity_map = {}  # (subject, teacher_username) -> set of class group names

    for row in lesson_rows:
        day = row.get("day", "").strip().lower()
        teacher_str = row.get("teacher", "").strip()
        group_str = row.get("group", "").strip()
        subject = row.get("subject", "").strip()

        if day in skip_days:
            continue
        if not teacher_str or not group_str:
            continue
        if subject in SKIP_SUBJECTS:
            continue

        # Each teacher gets their own activity for this subject+groups
        teachers = [t.strip() for t in teacher_str.split(",") if t.strip()]
        groups = [g.strip() for g in group_str.split(",") if g.strip()]

        # Map lesson groups back to class groups
        mapped_classes = set()
        for g in groups:
            mapped = map_group_to_class(g, class_names)
            if mapped:
                mapped_classes.add(mapped)

        if not mapped_classes:
            continue

        for teacher in teachers:
            if teacher not in staff_by_username:
                continue
            key = (subject, teacher)
            if key not in activity_map:
                activity_map[key] = set()
            activity_map[key].update(mapped_classes)

    # Build activities list
    activities_data = []
    teaching_groups_data = []
    teaching_group_ids = {}  # (subject, frozenset(classes)) -> group_id

    for (subject, teacher_username), class_group_names in sorted(activity_map.items()):
        teacher_id = staff_by_username.get(teacher_username)
        if not teacher_id:
            continue

        # Create or reuse a teaching group for this subject+classes combo
        classes_key = frozenset(class_group_names)
        tg_key = (subject, classes_key)

        if tg_key not in teaching_group_ids:
            tg_id = make_uuid("teaching_group", f"{subject}:{','.join(sorted(classes_key))}")
            class_display = ",".join(sorted(classes_key))
            teaching_group_ids[tg_key] = tg_id

            teaching_groups_data.append({
                "id": tg_id,
                "display_name": f"{subject} ({class_display})",
                "group_code": f"{subject}_{class_display}",
                "group_type": "Undervisning",
                "organisation_id": org_grundskola_id,
                "start_date": "2024-08-15",
                "class_ids": [group_id_map[cn] for cn in sorted(classes_key) if cn in group_id_map],
            })

        tg_id = teaching_group_ids[tg_key]

        # Subject code mapping
        subj_info = SUBJECT_CODE_MAP.get(subject, (subject[:3].upper(), subject))
        subject_code, subject_name = subj_info

        act_id = make_uuid("activity", f"{subject}:{teacher_username}:{','.join(sorted(classes_key))}")
        activities_data.append({
            "id": act_id,
            "display_name": f"{subject_name} - {teacher_username}",
            "organisation_id": org_grundskola_id,
            "start_date": "2024-08-15",
            "end_date": "2025-06-15",
            "activity_type": "Undervisning",
            "subject_code": subject_code,
            "subject_name": subject_name,
            "teacher_ids": [teacher_id],
            "group_ids": [tg_id],
        })

    return {
        "organisations": organisations,
        "staff": staff_list,
        "students": student_list,
        "guardians": guardian_list,
        "groups_data": groups_data,
        "teaching_groups_data": teaching_groups_data,
        "activities_data": activities_data,
        "org_ids": {
            "huvudman": org_huvudman_id,
            "school": org_school_id,
            "grundskola": org_grundskola_id,
        },
        "group_id_map": group_id_map,
        "staff_by_username": staff_by_username,
    }


# --- Anonymization ---


def apply_anonymization(data: dict, seed: int) -> dict:
    """Apply deterministic PII anonymization to all person data.

    Anonymizes names, civic numbers, emails, phones, addresses.
    Preserves all IDs, relationships, and structural data.
    """
    staff_name_map = {}  # person_id -> (anon_first, anon_last, anon_username)

    # Anonymize staff
    for s in data["staff"]:
        oid = s["external_id"]
        gender = s.get("sex")

        anon_first = anonymize_first_name(seed, oid, gender)
        anon_last = anonymize_last_name(seed, oid)
        anon_user = anonymize_username(seed, anon_first, anon_last)
        staff_name_map[s["id"]] = (anon_first, anon_last, anon_user)

        s["given_name"] = anon_first
        s["family_name"] = anon_last
        s["email"] = anonymize_email_staff(seed, anon_first, anon_last)
        s["edu_person_principal_name"] = s["email"]
        s["civic_no"] = anonymize_personnummer(seed, oid, s.get("civic_no"))
        if s.get("civic_no"):
            bd = birth_date_from_civic(s["civic_no"])
            if bd:
                s["birth_date"] = bd
        if s.get("phone_number"):
            s["phone_number"] = anonymize_phone(seed, oid)
        if s.get("street_address"):
            street, postal, city = anonymize_address(seed, oid)
            s["street_address"] = street
            s["postal_code"] = postal
            s["locality"] = city
        s["signature"] = anonymize_signature(anon_last)

    # Anonymize students
    for s in data["students"]:
        oid = s["external_id"]
        gender = s.get("sex")

        anon_first = anonymize_first_name(seed, oid, gender)
        anon_last = anonymize_last_name(seed, oid)

        s["given_name"] = anon_first
        s["family_name"] = anon_last
        s["email"] = anonymize_email_student(seed, anon_first, anon_last)
        s["civic_no"] = anonymize_personnummer(seed, oid, s.get("civic_no"))
        if s.get("civic_no"):
            bd = birth_date_from_civic(s["civic_no"])
            if bd:
                s["birth_date"] = bd

    # Anonymize guardians
    for g in data["guardians"]:
        oid = g["external_id"]

        anon_first = anonymize_first_name(seed, oid)
        anon_last = anonymize_last_name(seed, oid)

        g["given_name"] = anon_first
        g["family_name"] = anon_last
        g["email"] = anonymize_email_guardian(seed, anon_first, anon_last)
        if g.get("phone_number"):
            g["phone_number"] = anonymize_phone(seed, oid)
        if g.get("street_address"):
            street, postal, city = anonymize_address(seed, oid)
            g["street_address"] = street
            g["postal_code"] = postal
            g["locality"] = city

    # Update activity display names with anonymized teacher names
    for a in data["activities_data"]:
        teacher_id = a["teacher_ids"][0] if a.get("teacher_ids") else None
        if teacher_id and teacher_id in staff_name_map:
            _, _, anon_user = staff_name_map[teacher_id]
            subject_name = a.get("subject_name", "")
            a["display_name"] = f"{subject_name} - {anon_user}"

    return data


# --- Admin staff injection ---


def inject_admin_staff(data: dict, name: str, email: str) -> dict:
    """Inject a named admin staff member (Rektor) into the data.

    This person is NOT anonymized — used for real login testing.
    """
    parts = name.strip().split(None, 1)
    given_name = parts[0]
    family_name = parts[1] if len(parts) > 1 else ""

    person_id = make_uuid("staff", f"admin:{email}")

    admin_staff = {
        "id": person_id,
        "given_name": given_name,
        "family_name": family_name,
        "email": email,
        "edu_person_principal_name": email,
        "civic_no": None,
        "birth_date": None,
        "phone_number": None,
        "street_address": None,
        "postal_code": None,
        "locality": None,
        "external_id": f"admin_{email.split('@')[0]}",
        "duty_role": "Rektor",
        "signature": family_name[:3].upper() if family_name else given_name[:3].upper(),
    }

    data["staff"].insert(0, admin_staff)
    return data


# --- Output generation ---


DATE_FIELDS = {"birth_date", "start_date", "end_date"}


def format_value(key: str, value) -> str:
    """Format a value for Python output, converting date strings to date() objects."""
    if key in DATE_FIELDS and isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        parts = value.split("-")
        return f"date({int(parts[0])}, {int(parts[1])}, {int(parts[2])})"
    return repr(value)


def generate_python(data: dict, output_path: Path):
    """Write the seed data as a Python module."""

    lines = []
    lines.append('"""')
    lines.append("Anonymized SchoolSoft demo data for the SS12000 Demo SIS.")
    lines.append(f"Generated by: python -m scripts.build_from_schoolsoft")
    lines.append("DO NOT EDIT — regenerate with build_from_schoolsoft.")
    lines.append('"""')
    lines.append("from datetime import date")
    lines.append("")

    # ORGS dict
    lines.append("ORGS = {")
    for key, val in data["org_ids"].items():
        lines.append(f'    "{key}": "{val}",')
    lines.append("}")
    lines.append("")

    # PERSONS dict (quick-lookup)
    lines.append("PERSONS = {")
    for s in data["staff"]:
        lines.append(f'    "staff_{s["external_id"]}": "{s["id"]}",')
    lines.append("}")
    lines.append("")

    # GROUPS dict (quick-lookup)
    lines.append("GROUPS = {")
    for name, gid in sorted(data["group_id_map"].items()):
        safe_name = name.replace('"', '\\"')
        lines.append(f'    "{safe_name}": "{gid}",')
    lines.append("}")
    lines.append("")

    # TEACHING_GROUPS dict
    lines.append("TEACHING_GROUPS = {")
    for tg in data["teaching_groups_data"]:
        safe_name = tg["display_name"].replace('"', '\\"')
        lines.append(f'    "{safe_name}": "{tg["id"]}",')
    lines.append("}")
    lines.append("")

    # ORGANISATIONS list
    lines.append("ORGANISATIONS = [")
    for org in data["organisations"]:
        lines.append("    {")
        for k, v in org.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # STAFF list
    lines.append("STAFF = [")
    for s in data["staff"]:
        lines.append("    {")
        for k, v in s.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # STUDENTS list
    lines.append("STUDENTS = [")
    for s in data["students"]:
        lines.append("    {")
        for k, v in s.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # GUARDIANS list
    lines.append("GUARDIANS = [")
    for g in data["guardians"]:
        lines.append("    {")
        for k, v in g.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # GROUPS_DATA list
    lines.append("GROUPS_DATA = [")
    for g in data["groups_data"]:
        lines.append("    {")
        for k, v in g.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # TEACHING_GROUPS_DATA list
    lines.append("TEACHING_GROUPS_DATA = [")
    for tg in data["teaching_groups_data"]:
        lines.append("    {")
        for k, v in tg.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    # ACTIVITIES_DATA list
    lines.append("ACTIVITIES_DATA = [")
    for a in data["activities_data"]:
        lines.append("    {")
        for k, v in a.items():
            if v is not None:
                lines.append(f'        "{k}": {format_value(k, v)},')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Convert SchoolSoft TSV to SS12000 seed data")
    parser.add_argument("--tsv-dir", required=True, help="Directory with SchoolSoft TSV files")
    parser.add_argument("--output", default="app/seed/schoolsoft_data.py", help="Output Python file")
    parser.add_argument("--anonymize", action="store_true", default=False,
                        help="Anonymize PII (names, civic numbers, emails, phones, addresses)")
    parser.add_argument("--seed", type=int, default=42, help="Anonymization seed (default: 42)")
    parser.add_argument("--admin-name", default=None, help="Admin staff name (e.g. 'John Hammer')")
    parser.add_argument("--admin-email", default=None, help="Admin staff email (e.g. 'john@skolskold.se')")
    args = parser.parse_args()

    tsv_dir = Path(args.tsv_dir)
    output_path = Path(args.output)

    # Verify input files exist
    required = ["staff.txt", "students.txt", "parents.txt", "groups.txt", "lessons.txt"]
    for f in required:
        if not (tsv_dir / f).exists():
            print(f"ERROR: Missing {tsv_dir / f}")
            return

    print(f"Reading SchoolSoft TSV data from {tsv_dir}...")
    data = build_data(tsv_dir)

    # Inject admin staff (before anonymization so they don't get anonymized)
    if args.admin_name and args.admin_email:
        print(f"  Injecting admin: {args.admin_name} ({args.admin_email})")
        inject_admin_staff(data, args.admin_name, args.admin_email)

    # Apply anonymization if requested
    if args.anonymize:
        print(f"  Anonymizing PII (seed={args.seed})...")
        # Protect admin from anonymization
        admin_entry = None
        if args.admin_name and args.admin_email:
            admin_entry = data["staff"].pop(0)  # remove admin before anonymizing
        apply_anonymization(data, args.seed)
        if admin_entry:
            data["staff"].insert(0, admin_entry)  # re-insert unanonymized admin

    groups_with_mentors = sum(1 for g in data["groups_data"] if g.get("mentor_id"))
    print(f"  Staff:           {len(data['staff'])}")
    print(f"  Students:        {len(data['students'])}")
    print(f"  Guardians:       {len(data['guardians'])}")
    print(f"  Class groups:    {len(data['groups_data'])} ({groups_with_mentors} with mentors)")
    print(f"  Teaching groups: {len(data['teaching_groups_data'])}")
    print(f"  Activities:      {len(data['activities_data'])}")
    print(f"  Organisations:   {len(data['organisations'])}")

    print(f"\nWriting {output_path}...")
    generate_python(data, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
