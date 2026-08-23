"""Generated Swedish demo-kommun dataset: Tallvikens kommun.

The sales-facing multi-school dataset (DEMO_SEED_DATA=kommun) for the kommun
demo instance — realistic Swedish names from the SCB pools, a fictional
kommun so no real municipality is impersonated. Three school units under one
huvudman:

    Tallviks skola        (GR, åk 4-6, 5 klasser)
    Björkängens skola     (GR, åk 7-9, 5 klasser)
    Tallvikens gymnasium  (GY, år 1-3, 3 klasser)

Everything is DETERMINISTIC: uuid5 ids + a fixed RNG seed, so reseeding a
persistent demo-SIS volume never churns person UUIDs (the app matches synced
rows by that UUID). Same export contract as lotr_data/minimal_data.
"""
import random
import uuid
from datetime import date

from .svenska_namn import (
    FEMALE_FIRST_NAMES,
    LAST_NAMES,
    MALE_FIRST_NAMES,
    POSTAL_CODE_CITY,
    STREET_NAMES,
)

DATASET_VERSION = "1"

_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "kommun-demo.skolshield.se")
_rng = random.Random(20260823)


def _uid(key):
    return str(uuid.uuid5(_NS, key))


def _slug(text):
    table = str.maketrans("åäöéü", "aaoeu")
    return text.lower().translate(table).replace(" ", ".")


# --- Organisations -----------------------------------------------------------

ORGS = {
    "huvudman": _uid("org:huvudman"),
    "tallvik_skola": _uid("org:tallvik-skola"),
    "tallvik_gr": _uid("org:tallvik-gr"),
    "bjorkangen_skola": _uid("org:bjorkangen-skola"),
    "bjorkangen_gr": _uid("org:bjorkangen-gr"),
    "gymnasiet_skola": _uid("org:gymnasiet-skola"),
    "gymnasiet_gy": _uid("org:gymnasiet-gy"),
}

ORGANISATIONS = [
    {
        "id": ORGS["huvudman"],
        "display_name": "Tallvikens kommun",
        "organisation_type": "Huvudman",
        "organisation_number": "212000-7401",
        "municipality_code": "1799",
        "email": "utbildning@tallvik.example",
        "phone_number": "0570-123 45 00",
        "url": "https://tallvik.example",
        "street_address": "Kommunhuset, Storgatan 1",
        "postal_code": "671 00",
        "locality": "Tallviken",
    },
    {
        "id": ORGS["tallvik_skola"],
        "display_name": "Tallviks skola",
        "organisation_type": "Skola",
        "organisation_code": "TALSK",
        "parent_id": ORGS["huvudman"],
        "municipality_code": "1799",
        "email": "tallviks.skola@tallvik.example",
    },
    {
        "id": ORGS["tallvik_gr"],
        "display_name": "Tallviks skola",
        "organisation_type": "Skolenhet",
        "organisation_code": "TALGR",
        "school_unit_code": "87654321",
        "school_types": "GR",
        "parent_id": ORGS["tallvik_skola"],
        "municipality_code": "1799",
        "email": "tallviks.skola@tallvik.example",
    },
    {
        "id": ORGS["bjorkangen_skola"],
        "display_name": "Björkängens skola",
        "organisation_type": "Skola",
        "organisation_code": "BJOSK",
        "parent_id": ORGS["huvudman"],
        "municipality_code": "1799",
        "email": "bjorkangen@tallvik.example",
    },
    {
        "id": ORGS["bjorkangen_gr"],
        "display_name": "Björkängens skola",
        "organisation_type": "Skolenhet",
        "organisation_code": "BJOGR",
        "school_unit_code": "87654322",
        "school_types": "GR",
        "parent_id": ORGS["bjorkangen_skola"],
        "municipality_code": "1799",
        "email": "bjorkangen@tallvik.example",
    },
    {
        "id": ORGS["gymnasiet_skola"],
        "display_name": "Tallvikens gymnasium",
        "organisation_type": "Skola",
        "organisation_code": "TALGYS",
        "parent_id": ORGS["huvudman"],
        "municipality_code": "1799",
        "email": "gymnasiet@tallvik.example",
    },
    {
        "id": ORGS["gymnasiet_gy"],
        "display_name": "Tallvikens gymnasium",
        "organisation_type": "Skolenhet",
        "organisation_code": "TALGY",
        "school_unit_code": "87654323",
        "school_types": "GY",
        "parent_id": ORGS["gymnasiet_skola"],
        "municipality_code": "1799",
        "email": "gymnasiet@tallvik.example",
    },
]

# --- School specs ------------------------------------------------------------
# (unit_key, class specs [(code, school_year, school_type)], subjects,
#  staff role plan)

_TERM_START = date(2026, 8, 17)

_SCHOOLS = [
    {
        "unit": "tallvik_gr",
        "email_domain": "tallvik.example",
        "school_type": "GR",
        "classes": [("4A", 4), ("4B", 4), ("5A", 5), ("5B", 5), ("6A", 6)],
        "subjects": [("SV", "Svenska"), ("MA", "Matematik"),
                     ("EN", "Engelska"), ("NO", "NO")],
        "roles": ["Rektor", "Lärare", "Lärare", "Lärare", "Lärare", "Lärare",
                  "Kurator", "Specialpedagog"],
    },
    {
        "unit": "bjorkangen_gr",
        "email_domain": "tallvik.example",
        "school_type": "GR",
        "classes": [("7A", 7), ("7B", 7), ("8A", 8), ("8B", 8), ("9A", 9)],
        "subjects": [("SV", "Svenska"), ("MA", "Matematik"),
                     ("EN", "Engelska"), ("SO", "SO")],
        "roles": ["Rektor", "Lärare", "Lärare", "Lärare", "Lärare", "Lärare",
                  "Kurator", "Specialpedagog"],
    },
    {
        "unit": "gymnasiet_gy",
        "email_domain": "tallvik.example",
        "school_type": "GY",
        "classes": [("NA1", 1), ("EK2", 2), ("SA3", 3)],
        "subjects": [("SV", "Svenska"), ("MA", "Matematik"),
                     ("EN", "Engelska"), ("HI", "Historia")],
        "roles": ["Rektor", "Biträdande rektor", "Lärare", "Lärare", "Lärare",
                  "Lärare", "Lärare", "Kurator"],
    },
]

_CLASS_SIZE = (20, 24)      # inclusive range per class
_SIBLING_CHANCE = 0.15      # chance a student joins an existing family
_TWO_GUARDIANS_CHANCE = 0.7


# --- Person generation -------------------------------------------------------

_used_names = set()
_used_emails = set()


def _pick_name(sex):
    """A (given, family) pair not used before (keeps the cast legible)."""
    pool = MALE_FIRST_NAMES if sex == "Man" else FEMALE_FIRST_NAMES
    while True:
        given = _rng.choice(pool)
        family = _rng.choice(LAST_NAMES)
        if (given, family) not in _used_names:
            _used_names.add((given, family))
            return given, family


def _email(given, family, domain):
    base = f"{_slug(given)}.{_slug(family)}"
    addr, n = f"{base}@{domain}", 1
    while addr in _used_emails:
        n += 1
        addr = f"{base}{n}@{domain}"
    _used_emails.add(addr)
    return addr


def _civic_no(school_year, school_type):
    if school_type == "GY":
        birth_year = 2011 - school_year          # år 1 → 2010, år 3 → 2008
    else:
        birth_year = 2026 - (6 + school_year)    # åk 4 → 2016, åk 9 → 2011
    month = _rng.randint(1, 12)
    day = _rng.randint(1, 28)
    suffix = _rng.randint(1000, 9999)
    return f"{birth_year}{month:02d}{day:02d}-{suffix}"


def _address():
    street = _rng.choice(STREET_NAMES)
    number = _rng.randint(1, 89)
    postal, city = _rng.choice(POSTAL_CODE_CITY)
    return f"{street} {number}", postal, city


STAFF = []
GUARDIANS = []
STUDENTS = []
GROUPS_DATA = []
TEACHING_GROUPS_DATA = []
ACTIVITIES_DATA = []

# id maps in the same shape the other datasets export
PERSONS = {}
GROUPS = {}
TEACHING_GROUPS = {}

_staff_no = 0
_student_no = 0
_guardian_no = 0
_families = []   # (family_name, [guardian_ids]) available for siblings


def _new_staff(role, school, i):
    global _staff_no
    _staff_no += 1
    sex = _rng.choice(["Man", "Kvinna"])
    given, family = _pick_name(sex)
    key = f"staff:{school['unit']}:{i}"
    pid = _uid(key)
    PERSONS[f"{school['unit']}_staff_{i}"] = pid
    initials = (given[:2] + family[:1]).upper()
    STAFF.append({
        "id": pid, "given_name": given, "family_name": family,
        "email": _email(given, family, school["email_domain"]),
        "duty_role": role, "signature": initials,
        "sex": sex, "external_id": f"STAFF{_staff_no:03d}",
        "school_unit_id": ORGS[school["unit"]],
    })
    return pid


def _new_guardian(family_name=None):
    global _guardian_no
    _guardian_no += 1
    sex = _rng.choice(["Man", "Kvinna"])
    given, family = _pick_name(sex)
    if family_name is not None:
        family = family_name
    pid = _uid(f"guardian:{_guardian_no}")
    PERSONS[f"guardian_{_guardian_no}"] = pid
    street, postal, city = _address()
    GUARDIANS.append({
        "id": pid, "given_name": given, "family_name": family,
        "email": _email(given, family, "example.net"),
        "phone_number": f"070-{_rng.randint(100, 999)} "
                        f"{_rng.randint(10, 99)} {_rng.randint(10, 99)}",
        "external_id": f"GUARD{_guardian_no:03d}",
        "street_address": street, "postal_code": postal, "locality": city,
        "sex": sex,
    })
    return pid, family


def _family():
    """(family_name, guardian_ids) — new household, or an existing one
    (sibling) now and then."""
    if _families and _rng.random() < _SIBLING_CHANCE:
        return _rng.choice(_families)
    gid, family_name = _new_guardian()
    guardian_ids = [gid]
    if _rng.random() < _TWO_GUARDIANS_CHANCE:
        gid2, _ = _new_guardian(
            family_name if _rng.random() < 0.6 else None)
        guardian_ids.append(gid2)
    fam = (family_name, guardian_ids)
    _families.append(fam)
    return fam


def _new_student(school, group_id, school_year):
    global _student_no
    _student_no += 1
    sex = _rng.choice(["Man", "Kvinna"])
    family_name, guardian_ids = _family()
    given, _ = _pick_name(sex)
    pid = _uid(f"student:{_student_no}")
    PERSONS[f"student_{_student_no}"] = pid
    STUDENTS.append({
        "id": pid, "given_name": given, "family_name": family_name,
        "guardian_ids": list(guardian_ids), "group_id": group_id,
        "school_unit_id": ORGS[school["unit"]], "school_year": school_year,
        "civic_no": _civic_no(school_year, school["school_type"]),
        "email": _email(given, family_name,
                        f"student.{school['email_domain']}"),
        "sex": sex, "external_id": f"STU{_student_no:03d}",
    })


for school in _SCHOOLS:
    staff_ids = [_new_staff(role, school, i)
                 for i, role in enumerate(school["roles"], start=1)]
    teachers = [pid for pid, role in zip(staff_ids, school["roles"])
                if role in ("Lärare", "Biträdande rektor")]

    class_ids = []
    for ci, (code, school_year) in enumerate(school["classes"]):
        gkey = f"{school['unit']}_{code}"
        gid = _uid(f"group:{gkey}")
        GROUPS[gkey] = gid
        class_ids.append(gid)
        GROUPS_DATA.append({
            "id": gid, "display_name": f"Klass {code}", "group_code": code,
            "group_type": "Klass", "school_type": school["school_type"],
            "organisation_id": ORGS[school["unit"]],
            "start_date": _TERM_START,
            "mentor_id": teachers[ci % len(teachers)],
        })
        for _n in range(_rng.randint(*_CLASS_SIZE)):
            _new_student(school, gid, school_year)

    # One teaching group + activity per class and subject; subject teachers
    # rotate through the school's teacher pool.
    for si, (subj_code, subj_name) in enumerate(school["subjects"]):
        teacher = teachers[si % len(teachers)]
        for (code, school_year), gid in zip(school["classes"], class_ids):
            tkey = f"{school['unit']}_{subj_code}_{code}"
            tgid = _uid(f"tgroup:{tkey}")
            TEACHING_GROUPS[tkey] = tgid
            TEACHING_GROUPS_DATA.append({
                "id": tgid, "display_name": f"{subj_name} {code}",
                "group_code": f"{subj_code}{code}",
                "group_type": "Undervisning",
                "organisation_id": ORGS[school["unit"]],
                "start_date": _TERM_START, "class_ids": [gid],
            })
            ACTIVITIES_DATA.append({
                "id": _uid(f"activity:{tkey}"),
                "display_name": f"{subj_name} {code}",
                "subject_code": subj_code, "subject_name": subj_name,
                "activity_type": "Undervisning",
                "organisation_id": ORGS[school["unit"]],
                "start_date": _TERM_START,
                "teacher_ids": [teacher], "group_ids": [tgid],
            })

for s in STUDENTS:
    if "birth_date" not in s:
        year = int(s["civic_no"][:4])
        s["birth_date"] = date(year, int(s["civic_no"][4:6]),
                               int(s["civic_no"][6:8]))
