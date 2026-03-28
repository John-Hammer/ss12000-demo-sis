"""
Map production Django database tables to SS12000 demo SIS entities.

Production schema → Demo SIS schema:
  students_student          → Person (student) + Enrolment
  auth_user + users_staff   → Person (staff) + Duty
  parents_parent            → Person (guardian)
  parents_parent_students   → person_responsibles
  groups_group (mentor)     → Group (Klass) + GroupMembership
  groups_group (other)      → Group (Undervisning)
  lessons_lesson            → Activity + ActivityTeacher + ActivityGroup
  core_schoolsettings       → Organisation hierarchy
"""
from datetime import date
from typing import Optional

from .anonymizer import (
    make_uuid, anonymize_first_name, anonymize_last_name,
    anonymize_personnummer, anonymize_email_staff, anonymize_email_student,
    anonymize_email_guardian, anonymize_phone, anonymize_address,
    anonymize_signature, anonymize_username,
)
from .extract_from_dump import (
    get_active_students, get_active_staff, get_active_parents,
    get_active_groups, get_staff_roles, get_school_settings,
)


# Django auth group name → SS12000 DutyRole
ROLE_MAPPING = {
    "Skolledare": "Rektor",
    "Lärare": "Lärare",
    "EHT": "Kurator",
    "Fritids": "Barnskötare/Elevassistent",
    "Servicepersonal": "Annan personal",
    "IKT": "Skoladministratör",
    "Modersmål": "Lärare",
}

# School start date for the academic year
SCHOOL_START = date(2024, 8, 15)
ORG_START = date(2024, 1, 1)


def map_all(data: dict, seed: int = 42) -> dict:
    """
    Transform extracted production data into SS12000 demo SIS format.
    Returns a dict with all the entities needed for anon_data.py.
    """
    # Get filtered/joined production data
    students = get_active_students(data)
    staff = get_active_staff(data)
    parents = get_active_parents(data)
    groups = get_active_groups(data)
    staff_roles = get_staff_roles(data)
    settings = get_school_settings(data)

    # Build ID maps
    # These map original production IDs to anonymized UUIDs
    student_id_map = {}  # student.id → uuid
    staff_id_map = {}    # staff.id → uuid (also keyed by user_id)
    staff_user_id_map = {}  # user_id → uuid
    parent_id_map = {}   # parent.id → uuid
    group_id_map = {}    # group.id → uuid

    # Organisation UUIDs (fixed structure)
    org_ids = {
        "huvudman": make_uuid(seed, "org", "huvudman"),
        "skola": make_uuid(seed, "org", "skola"),
        "grundskola": make_uuid(seed, "org", "grundskola"),
        "gymnasium": make_uuid(seed, "org", "gymnasium"),
    }

    # --- 1. Map organisations ---
    school_name = "Demoskolan"
    organisations = _map_organisations(org_ids, school_name)

    # --- 2. Map staff ---
    mapped_staff = []
    for s in staff:
        uid = make_uuid(seed, "staff", s["staff_id"])
        staff_id_map[s["staff_id"]] = uid
        staff_user_id_map[s["user_id"]] = uid

        gender = _guess_gender_staff(s)
        anon_first = anonymize_first_name(seed, s["staff_id"], gender)
        anon_last = anonymize_last_name(seed, s["staff_id"])

        # Determine duty role from auth groups
        roles = staff_roles.get(s["user_id"], [])
        duty_role = _map_duty_role(roles)

        anon_email = anonymize_email_staff(seed, anon_first, anon_last)
        civic_no = anonymize_personnummer(seed, s["staff_id"], s.get("socialnumber"))
        birth_date = _parse_date(s.get("birthday"))

        has_phone = s.get("mobile") or s.get("workphone") or s.get("homephone")
        has_address = s.get("address1") or s.get("pocode")

        staff_entry = {
            "id": uid,
            "given_name": anon_first,
            "family_name": anon_last,
            "email": anon_email,
            "edu_person_principal_name": anon_email,
            "duty_role": duty_role,
            "signature": anonymize_signature(anon_last),
            "description": duty_role,
            "sex": gender or "Man",
            "civic_no": civic_no,
            "birth_date": birth_date,
            "external_id": make_uuid(seed, "ext_staff", s["staff_id"]),
        }

        if has_phone:
            staff_entry["phone_number"] = anonymize_phone(seed, s["staff_id"])
        if has_address:
            street, postal, city = anonymize_address(seed, s["staff_id"])
            staff_entry["street_address"] = street
            staff_entry["postal_code"] = postal
            staff_entry["locality"] = city

        mapped_staff.append(staff_entry)

    # --- 3. Map students ---
    mapped_students = []
    # Build student → parent links
    parent_student_links = data.get("parents_parent_students", [])
    student_parents = {}  # student_id → [parent_id, ...]
    for link in parent_student_links:
        sid = link["student_id"]
        pid = link["parent_id"]
        if sid not in student_parents:
            student_parents[sid] = []
        student_parents[sid].append(pid)

    # Build student → class group mapping
    student_groups_m2m = data.get("groups_group_students", [])
    student_class_groups = {}  # student_id → group_id (mentor/class group)
    mentor_groups = {g["id"]: g for g in groups if g.get("group_type") == "mentor"}
    for sg in student_groups_m2m:
        if sg["group_id"] in mentor_groups:
            student_class_groups[sg["student_id"]] = sg["group_id"]

    # Determine school_type for groups
    group_school_type = {}
    for g in groups:
        if g.get("group_type") == "mentor":
            name = (g.get("name") or "").lower()
            # Classes with names like "1a", "2b", etc. are grundskola
            # Look at name patterns for class year hints
            group_school_type[g["id"]] = "GR"  # default grundskola

    for s in students:
        uid = make_uuid(seed, "student", s["id"])
        student_id_map[s["id"]] = uid

        gender = _normalize_gender(s.get("gender"))
        anon_first = anonymize_first_name(seed, s["id"], gender)
        anon_last = anonymize_last_name(seed, s["id"])

        # Determine school year and school unit
        year_val = s.get("year")
        try:
            school_year = int(year_val) if year_val else None
        except (ValueError, TypeError):
            school_year = None

        school_type = (s.get("school_type") or "grundskola").lower()
        if school_type == "gymnasium" or (school_year and school_year > 9):
            school_unit_id = org_ids["gymnasium"]
            ss_school_type = "GY"
        else:
            school_unit_id = org_ids["grundskola"]
            ss_school_type = "GR"

        # Get class group
        class_group_id = student_class_groups.get(s["id"])

        # Get guardian IDs
        guardian_orig_ids = student_parents.get(s["id"], [])

        # Parse birth date
        birth_date = _parse_date(s.get("birthday"))

        # Parse civic number
        civic_no = anonymize_personnummer(seed, s["id"], s.get("socialnumber"))

        mapped_students.append({
            "id": uid,
            "given_name": anon_first,
            "family_name": anon_last,
            "email": anonymize_email_student(seed, anon_first, anon_last),
            "guardian_ids": guardian_orig_ids,  # Will be resolved later
            "group_id": class_group_id,  # Will be resolved later
            "school_unit_id": school_unit_id,
            "school_year": school_year,
            "civic_no": civic_no,
            "sex": gender or "Man",
            "external_id": make_uuid(seed, "ext_student", s["id"]),
            "birth_date": birth_date,
            "_orig_id": s["id"],
        })

    # --- 4. Map parents/guardians ---
    mapped_guardians = []
    for p in parents:
        uid = make_uuid(seed, "parent", p["id"])
        parent_id_map[p["id"]] = uid

        gender = _guess_gender_parent(p)
        anon_first = anonymize_first_name(seed, p["id"], gender)
        anon_last = anonymize_last_name(seed, p["id"])

        street, postal, city = anonymize_address(seed, p["id"])
        phone = anonymize_phone(seed, p["id"])

        mapped_guardians.append({
            "id": uid,
            "given_name": anon_first,
            "family_name": anon_last,
            "email": anonymize_email_guardian(seed, anon_first, anon_last),
            "phone_number": phone,
            "external_id": make_uuid(seed, "ext_parent", p["id"]),
            "street_address": street,
            "postal_code": postal,
            "locality": city,
            "sex": gender or "Man",
        })

    # --- 5. Map class groups ---
    mapped_groups = []
    for g in groups:
        if g.get("group_type") != "mentor":
            continue

        uid = make_uuid(seed, "group", g["id"])
        group_id_map[g["id"]] = uid

        name = g.get("name") or g.get("code") or ""
        code = name.upper().replace(":", "").replace(" ", "")

        # Determine school type from class name
        school_type = _guess_school_type_from_class(name)
        org_id = org_ids["gymnasium"] if school_type == "GY" else org_ids["grundskola"]

        # Find mentor
        mentor_staff_id = g.get("mentor_id")
        mentor_uuid = staff_id_map.get(mentor_staff_id)

        mapped_groups.append({
            "id": uid,
            "display_name": f"Klass {name.upper()}",
            "group_code": code,
            "group_type": "Klass",
            "school_type": school_type,
            "organisation_id": org_id,
            "start_date": SCHOOL_START,
            "mentor_id": mentor_uuid,
            "_orig_id": g["id"],
        })

    # --- 6. Build teaching groups from non-mentor groups ---
    teaching_group_id_map = {}
    mapped_teaching_groups = []

    non_mentor_groups = [g for g in groups if g.get("group_type") != "mentor"]
    for g in non_mentor_groups:
        uid = make_uuid(seed, "teaching_group", g["id"])
        teaching_group_id_map[g["id"]] = uid
        group_id_map[g["id"]] = uid  # Also add to main map

        name = g.get("name") or g.get("code") or ""
        code = (g.get("code") or name).upper().replace(":", "").replace(" ", "")

        # Find which class groups' students overlap with this group
        class_ids = _find_class_ids_for_teaching_group(
            g["id"], data, mentor_groups, group_id_map
        )

        # Determine org from related class groups
        org_id = org_ids["grundskola"]  # default
        for cid in class_ids:
            for mg in mapped_groups:
                if mg.get("_orig_id") == cid:
                    org_id = mg["organisation_id"]
                    break

        mapped_teaching_groups.append({
            "id": uid,
            "display_name": name,
            "group_code": code,
            "group_type": "Undervisning",
            "organisation_id": org_id,
            "start_date": SCHOOL_START,
            "class_ids": [group_id_map[cid] for cid in class_ids if cid in group_id_map],
            "_orig_id": g["id"],
        })

    # --- 7. Map activities from lessons ---
    mapped_activities = []
    lessons = data.get("lessons_lesson", [])
    lesson_groups_m2m = data.get("lessons_lesson_groups", [])
    lesson_teachers_m2m = data.get("lessons_lesson_teachers", [])

    # Build lesson → groups and lesson → teachers maps
    lesson_to_groups = {}
    for lg in lesson_groups_m2m:
        lid = lg["lesson_id"]
        gid = lg["group_id"]
        if lid not in lesson_to_groups:
            lesson_to_groups[lid] = []
        lesson_to_groups[lid].append(gid)

    lesson_to_teachers = {}
    for lt in lesson_teachers_m2m:
        lid = lt["lesson_id"]
        sid = lt["staff_id"]
        if lid not in lesson_to_teachers:
            lesson_to_teachers[lid] = []
        lesson_to_teachers[lid].append(sid)

    # Synthesize activities: group by (subject_name, group_set) to deduplicate lessons
    activity_key_map = {}  # (subject, frozenset(group_ids)) → activity data
    for lesson in lessons:
        if lesson.get("active") != "t":
            continue

        subject_name = lesson.get("name") or lesson.get("subject") or "Lektion"
        group_ids = lesson_to_groups.get(lesson["id"], [])
        teacher_ids = lesson_to_teachers.get(lesson["id"], [])

        if not group_ids:
            continue

        # Create a key for deduplication
        group_key = frozenset(group_ids)
        activity_key = (subject_name, group_key)

        if activity_key not in activity_key_map:
            act_uid = make_uuid(seed, "activity", f"{subject_name}:{sorted(group_ids)}")

            # Map teacher IDs to anonymized UUIDs
            teacher_uuids = []
            for tid in teacher_ids:
                if tid in staff_id_map:
                    teacher_uuids.append(staff_id_map[tid])

            # Map group IDs to anonymized UUIDs
            group_uuids = []
            for gid in group_ids:
                if gid in group_id_map:
                    group_uuids.append(group_id_map[gid])

            if not group_uuids:
                continue

            # Determine org from groups
            org_id = org_ids["grundskola"]
            for gid in group_ids:
                for mg in mapped_groups + mapped_teaching_groups:
                    if mg.get("_orig_id") == gid:
                        org_id = mg["organisation_id"]
                        break

            # Extract subject code from the lesson name
            subject_code = _extract_subject_code(subject_name)

            activity_key_map[activity_key] = {
                "id": act_uid,
                "display_name": subject_name,
                "subject_code": subject_code,
                "subject_name": subject_name,
                "activity_type": "Undervisning",
                "organisation_id": org_id,
                "start_date": SCHOOL_START,
                "teacher_ids": teacher_uuids,
                "group_ids": group_uuids,
            }
        else:
            # Merge additional teachers
            existing = activity_key_map[activity_key]
            for tid in teacher_ids:
                if tid in staff_id_map:
                    tuuid = staff_id_map[tid]
                    if tuuid not in existing["teacher_ids"]:
                        existing["teacher_ids"].append(tuuid)

    mapped_activities = list(activity_key_map.values())

    # --- 8. Resolve FK references in students ---
    for s in mapped_students:
        # Resolve guardian IDs
        s["guardian_ids"] = [
            parent_id_map[pid] for pid in s["guardian_ids"]
            if pid in parent_id_map
        ]
        # Resolve group ID
        orig_group = s.pop("group_id", None)
        if orig_group and orig_group in group_id_map:
            s["group_id"] = group_id_map[orig_group]
        else:
            s["group_id"] = None
        # Remove internal fields
        s.pop("_orig_id", None)

    # Clean up internal fields
    for g in mapped_groups:
        g.pop("_orig_id", None)
    for g in mapped_teaching_groups:
        g.pop("_orig_id", None)

    # Build UUID lookup dicts (like ORGS, PERSONS, GROUPS etc in lotr_data.py)
    orgs_dict = org_ids
    persons_dict = {}
    for s in mapped_staff:
        key = f"staff_{s['given_name'].lower()}_{s['family_name'].lower()}"
        key = _safe_key(key)
        persons_dict[key] = s["id"]
    for s in mapped_students:
        key = f"student_{s['given_name'].lower()}_{s['family_name'].lower()}"
        key = _safe_key(key)
        persons_dict[key] = s["id"]
    for g in mapped_guardians:
        key = f"guardian_{g['given_name'].lower()}_{g['family_name'].lower()}"
        key = _safe_key(key)
        persons_dict[key] = g["id"]

    groups_dict = {g["group_code"].lower(): g["id"] for g in mapped_groups}
    teaching_groups_dict = {
        g["group_code"].lower(): g["id"] for g in mapped_teaching_groups
    }

    return {
        "ORGANISATIONS": organisations,
        "STAFF": mapped_staff,
        "STUDENTS": mapped_students,
        "GUARDIANS": mapped_guardians,
        "GROUPS_DATA": mapped_groups,
        "TEACHING_GROUPS_DATA": mapped_teaching_groups,
        "ACTIVITIES_DATA": mapped_activities,
        "ORGS": orgs_dict,
        "PERSONS": persons_dict,
        "GROUPS": groups_dict,
        "TEACHING_GROUPS": teaching_groups_dict,
    }


def _map_organisations(org_ids: dict, school_name: str) -> list[dict]:
    """Build the 4-level organisation hierarchy."""
    return [
        {
            "id": org_ids["huvudman"],
            "display_name": f"{school_name} Utbildning AB",
            "organisation_type": "Huvudman",
            "organisation_number": "802100-0000",
            "municipality_code": "0180",
            "email": f"info@demoskolan.se",
            "phone_number": "08-123 00 00",
            "street_address": "Storgatan 1",
            "postal_code": "111 22",
            "locality": "Stockholm",
        },
        {
            "id": org_ids["skola"],
            "display_name": school_name,
            "organisation_type": "Skola",
            "organisation_code": "DEMO",
            "parent_id": org_ids["huvudman"],
            "municipality_code": "0180",
            "email": f"info@demoskolan.se",
            "phone_number": "08-123 00 00",
        },
        {
            "id": org_ids["grundskola"],
            "display_name": f"{school_name} Grundskola",
            "organisation_type": "Skolenhet",
            "organisation_code": "DEMOGR",
            "school_unit_code": "99990001",
            "school_types": "GR",
            "parent_id": org_ids["skola"],
            "municipality_code": "0180",
            "email": f"grundskola@demoskolan.se",
        },
        {
            "id": org_ids["gymnasium"],
            "display_name": f"{school_name} Gymnasium",
            "organisation_type": "Skolenhet",
            "organisation_code": "DEMOGY",
            "school_unit_code": "99990002",
            "school_types": "GY",
            "parent_id": org_ids["skola"],
            "municipality_code": "0180",
            "email": f"gymnasium@demoskolan.se",
        },
    ]


def _map_duty_role(auth_group_names: list[str]) -> str:
    """Map Django auth group names to SS12000 duty role."""
    for name in auth_group_names:
        if name in ROLE_MAPPING:
            return ROLE_MAPPING[name]
    return "Annan personal"


def _guess_gender_staff(staff: dict) -> Optional[str]:
    """Guess gender from Swedish first name ending (heuristic)."""
    name = (staff.get("first_name") or "").strip()
    if not name:
        return None
    # Common Swedish female name endings
    if name.endswith(("a", "e")) and not name.endswith(("ste", "ke", "ge")):
        return "Kvinna"
    return "Man"


def _guess_gender_parent(parent: dict) -> Optional[str]:
    """Guess gender from first name."""
    name = (parent.get("first_name") or "").strip()
    if not name:
        return None
    if name.endswith(("a", "e")) and not name.endswith(("ste", "ke", "ge")):
        return "Kvinna"
    return "Man"


def _normalize_gender(gender: Optional[str]) -> Optional[str]:
    """Normalize gender value to SS12000 format."""
    if not gender:
        return None
    g = gender.strip().lower()
    if g in ("flicka", "f", "kvinna", "female", "woman"):
        return "Kvinna"
    if g in ("pojke", "m", "man", "male", "boy"):
        return "Man"
    return None


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse a date string (YYYY-MM-DD) to a date object."""
    if not date_str:
        return None
    try:
        parts = date_str.strip().split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        pass
    return None


def _guess_school_type_from_class(class_name: str) -> str:
    """Guess if a class is grundskola or gymnasium from its name."""
    name = class_name.lower().strip()
    # Higher grades (7+) or names starting with numbers > 9 = gymnasium
    # Common patterns: "1a", "2b", "gy1", "na21a"
    if name.startswith("gy") or name.startswith("na") or name.startswith("sa"):
        return "GY"
    # Try to extract leading number
    num_str = ""
    for c in name:
        if c.isdigit():
            num_str += c
        else:
            break
    if num_str:
        num = int(num_str)
        if num > 9:
            return "GY"
    return "GR"


def _find_class_ids_for_teaching_group(
    group_id: str, data: dict, mentor_groups: dict, group_id_map: dict
) -> list[str]:
    """
    Find which mentor/class groups share students with a teaching group.
    Returns list of mentor group original IDs.
    """
    student_groups_m2m = data.get("groups_group_students", [])

    # Get students in this teaching group
    tg_students = set()
    for sg in student_groups_m2m:
        if sg["group_id"] == group_id:
            tg_students.add(sg["student_id"])

    if not tg_students:
        return []

    # Find which mentor groups these students belong to
    class_ids = set()
    for sg in student_groups_m2m:
        if sg["student_id"] in tg_students and sg["group_id"] in mentor_groups:
            class_ids.add(sg["group_id"])

    return sorted(class_ids)


def _extract_subject_code(name: str) -> str:
    """Extract a subject code from a lesson/subject name."""
    name_upper = name.strip().upper()
    # Common Swedish subject codes
    code_map = {
        "SVENSKA": "SV", "SV": "SV",
        "MATEMATIK": "MA", "MA": "MA", "MATTE": "MA",
        "ENGELSKA": "EN", "EN": "EN",
        "HISTORIA": "HI", "HI": "HI",
        "GEOGRAFI": "GE", "GE": "GE",
        "SAMHÄLLSKUNSKAP": "SH", "SH": "SH", "SO": "SO",
        "RELIGION": "RE", "RE": "RE",
        "BIOLOGI": "BI", "BI": "BI",
        "FYSIK": "FY", "FY": "FY",
        "KEMI": "KE", "KE": "KE",
        "NO": "NO", "NATURKUNSKAP": "NK",
        "IDROTT": "IDH", "IDH": "IDH",
        "BILD": "BL", "BL": "BL",
        "MUSIK": "MU", "MU": "MU",
        "SLÖJD": "SL", "SL": "SL",
        "TEKNIK": "TK", "TK": "TK",
        "HEMKUNSKAP": "HKK", "HKK": "HKK",
        "MODERSMÅL": "ML", "ML": "ML",
        "FRANSKA": "FR", "FR": "FR",
        "SPANSKA": "SP", "SP": "SP",
        "TYSKA": "TY", "TY": "TY",
    }

    # Try exact match first
    if name_upper in code_map:
        return code_map[name_upper]

    # Try partial match
    for key, code in code_map.items():
        if key in name_upper:
            return code

    # Fallback: first 2-3 chars
    clean = "".join(c for c in name_upper if c.isalpha())
    return clean[:3] if clean else "ÖVR"


def _safe_key(key: str) -> str:
    """Make a safe dictionary key from a name."""
    import re
    key = key.replace(" ", "_").replace("-", "_")
    key = re.sub(r'[^a-z0-9_åäö]', '', key)
    return key
