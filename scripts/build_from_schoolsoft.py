"""
Convert SchoolSoft TSV exports into SS12000 seed data for the demo SIS.

Reads TSV files from a directory (staff.txt, students.txt, parents.txt, groups.txt, lessons.txt)
and generates app/seed/schoolsoft_data.py with all entities mapped to SS12000 format.

Usage:
    python -m scripts.build_from_schoolsoft --tsv-dir ../skolSköld/demo_schoolsoft_tsv
"""
import argparse
import csv
import hashlib
import re
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path


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
    "Sv": ("SV", "Svenska"),
    "Sven": ("SVA", "Svenska som andraspråk"),
    "Ma": ("MA", "Matematik"),
    "En": ("EN", "Engelska"),
    "So": ("SO", "Samhällsorienterande ämnen"),
    "NO": ("NO", "Naturorienterande ämnen"),
    "Idh": ("IDH", "Idrott och hälsa"),
    "Mu": ("MU", "Musik"),
    "Bl": ("BL", "Bild"),
    "Sl": ("SL", "Slöjd"),
    "Hkk": ("HKK", "Hem- och konsumentkunskap"),
    "Tema": ("TEMA", "Tema"),
    "Retorik": ("RET", "Retorik"),
    "Sp": ("ML-SP", "Moderna språk - Spanska"),
    "fr": ("ML-FR", "Moderna språk - Franska"),
    "Ty": ("ML-TY", "Moderna språk - Tyska"),
    "Tk": ("TK", "Teknik"),
}

SKIP_SUBJECTS = {
    "Lektion", "Lunch", "Rast", "Vikarieanskaffning", "Klassråd",
    "Elevrapport F-3", "Elevrapport 4-6", "Elevrapport 7-9",
    "Elevråd", "STÖDLÄXLÄSNING", "Samverkan åk 1", "Samverkan åk 2",
    "Samverkan åk 3", "SamvIdh", "Resurs 7",
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

        # Pick first teacher as the primary mentor
        mentor_id = mentor_ids[0] if mentor_ids else None
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
            "mentor_id": mentor_id,
        })

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

    print(f"  Staff:           {len(data['staff'])}")
    print(f"  Students:        {len(data['students'])}")
    print(f"  Guardians:       {len(data['guardians'])}")
    print(f"  Class groups:    {len(data['groups_data'])}")
    print(f"  Teaching groups: {len(data['teaching_groups_data'])}")
    print(f"  Activities:      {len(data['activities_data'])}")
    print(f"  Organisations:   {len(data['organisations'])}")

    print(f"\nWriting {output_path}...")
    generate_python(data, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
