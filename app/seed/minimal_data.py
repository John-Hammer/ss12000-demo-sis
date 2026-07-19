"""
Minimal KISS demo dataset — two classes, hand-curated.

One full class (7A, 30 students) plus a smaller grade-8 class
(8A, 15 students) at a single school unit:
  - 5 teachers; Sara Lindqvist is mentor for all of 7A, Maria Holmgren
    is mentor for all of 8A. Erik Sandberg deliberately mentors NOBODY:
    he is the demo_larare persona, and a pure subject teacher is what
    demonstrates teaching-based least-privilege access (a teacher sees
    only what their teaching relationship grants — the GDPR story).
  - 1 EHT (kurator), 1 skolledare (rektor), 1 generic staff (administratör)
  - ~2 guardians per student (a few single-guardian households)
  - 5 teaching groups for 7A (SV7, MA7, EN7, NO7, IDH7) — every 7A student
    in each, one teacher per group, with matching activities
  - 2 teaching groups for 8A (SV8 taught by Sara, MA8 taught by Erik) —
    deliberately sparse; they give both main demo personas a teaching
    group whose students they do NOT mentor (the dashboard's Teaching
    Groups widget is meaningless when it mirrors the mentor class)

All UUIDs are uuid5-derived from external_id, so they are stable across
reseeds. The four demo login personas in the main skolSköld app
(setup_demo_users) reference staff 1001/1002/1006/1007 by these UUIDs —
if you renumber staff here, update setup_demo_users.py to match.

Bump DATASET_VERSION whenever this data changes: the seeder wipes and
reseeds the deployed database when the stored version differs.
"""
import uuid
from datetime import date

NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

DATASET_VERSION = '6'  # 6: 8A mentor moved Erik→Maria (pure-teacher persona)


def _uid(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f'minimal:{key}'))


def _ascii(s: str) -> str:
    return (s.lower()
            .replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
            .replace('é', 'e').replace(' ', ''))


# ---------------------------------------------------------------------------
# Organisations
# ---------------------------------------------------------------------------

ORGS = {
    'huvudman': _uid('org:huvudman'),
    'skola': _uid('org:skola'),
    'grundskola': _uid('org:grundskola'),
}

ORGANISATIONS = [
    {
        'id': ORGS['huvudman'],
        'display_name': 'Demoskolan Huvudman',
        'organisation_type': 'Huvudman',
        'organisation_number': '5500000001',
        'organisation_code': 'DEMO',
        'municipality_code': '0180',
        'email': 'info@demoskolan.se',
        'phone_number': '08-000 00 00',
        'street_address': 'Demovägen 1',
        'postal_code': '100 00',
        'locality': 'Stockholm',
    },
    {
        'id': ORGS['skola'],
        'display_name': 'Demoskolan',
        'organisation_type': 'Skola',
        'organisation_number': '5500000002',
        'organisation_code': 'DEMO_SKOLA',
        'parent_id': ORGS['huvudman'],
        'municipality_code': '0180',
        'email': 'skola@demoskolan.se',
    },
    {
        'id': ORGS['grundskola'],
        'display_name': 'Demoskolan Grundskola',
        'organisation_type': 'Skolenhet',
        'school_unit_code': '10000001',
        'school_types': 'GR',
        'parent_id': ORGS['skola'],
        'municipality_code': '0180',
    },
]

_UNIT = ORGS['grundskola']


# ---------------------------------------------------------------------------
# Staff (8) — external_ids 1001–1008
# ---------------------------------------------------------------------------
# (ext_id, given, family, duty_role, sex, birth_date)
_STAFF_DEFS = [
    ('1001', 'Sara', 'Lindqvist', 'Lärare', 'Kvinna', date(1985, 3, 12)),   # mentor 7A + SV7/SV8
    ('1002', 'Erik', 'Sandberg', 'Lärare', 'Man', date(1979, 9, 4)),        # MA7/MA8 — NO mentor class (pure-teacher persona)
    ('1003', 'Maria', 'Holmgren', 'Lärare', 'Kvinna', date(1990, 6, 21)),   # EN7 + mentor 8A
    ('1004', 'Johan', 'Ek', 'Lärare', 'Man', date(1983, 1, 30)),            # NO7
    ('1005', 'Anna', 'Bergström', 'Lärare', 'Kvinna', date(1994, 11, 8)),   # IDH7
    ('1006', 'Eva', 'Ström', 'Kurator', 'Kvinna', date(1976, 4, 17)),       # EHT
    ('1007', 'Lars', 'Wikström', 'Rektor', 'Man', date(1968, 8, 25)),       # skolledare
    ('1008', 'Karin', 'Åberg', 'Administratör', 'Kvinna', date(1988, 2, 14)),
]

STAFF = []
for _ext, _given, _family, _role, _sex, _born in _STAFF_DEFS:
    _email = f'{_ascii(_given)}.{_ascii(_family)}@demoskolan.se'
    _serial = int(_ext) % 100
    _gender_digit = (_serial * 2 + 1) % 10 if _sex == 'Man' else (_serial * 2) % 10
    STAFF.append({
        'id': _uid(f'staff:{_ext}'),
        'given_name': _given,
        'family_name': _family,
        'email': _email,
        'edu_person_principal_name': _email,
        'duty_role': _role,
        'signature': (_ascii(_given)[:3] + _ascii(_family)[:3]),
        'description': _role,
        'sex': _sex,
        'civic_no': f'{_born:%y%m%d}-{_serial:02d}{_gender_digit}{_serial % 10}',
        'birth_date': _born,
        'external_id': _ext,
    })

_STAFF_BY_EXT = {s['external_id']: s['id'] for s in STAFF}

MENTOR_ID = _STAFF_BY_EXT['1001']
MENTOR_8A_ID = _STAFF_BY_EXT['1003']  # Maria Holmgren — NOT the demo_larare persona


# ---------------------------------------------------------------------------
# Class groups — 7A and 8A
# ---------------------------------------------------------------------------

CLASS_7A = _uid('group:7A')
CLASS_8A = _uid('group:8A')

GROUPS = {'7A': CLASS_7A, '8A': CLASS_8A}

GROUPS_DATA = [
    {
        'id': CLASS_7A,
        'display_name': '7A',
        'group_code': '7A',
        'group_type': 'Klass',
        'school_type': 'GR',
        'organisation_id': _UNIT,
        'start_date': date(2025, 8, 18),
        'mentor_id': MENTOR_ID,
    },
    {
        'id': CLASS_8A,
        'display_name': '8A',
        'group_code': '8A',
        'group_type': 'Klass',
        'school_type': 'GR',
        'organisation_id': _UNIT,
        'start_date': date(2025, 8, 18),
        'mentor_id': MENTOR_8A_ID,
    },
]


# ---------------------------------------------------------------------------
# Students (45)
#   7A: 30 students born 2013 (year 7), external_ids 2001–2030
#   8A: 15 students born 2012 (year 8), external_ids 2031–2045
# ---------------------------------------------------------------------------
# (given, family, sex). Guardian spec per student:
#   'both'   → mother + father, same surname as student
#   'single' → one guardian
#   'split'  → mother has a different surname (separated household)
_STUDENT_DEFS = [
    ('Alva', 'Nilsson', 'Kvinna', 'both'),
    ('Elsa', 'Karlsson', 'Kvinna', 'both'),
    ('Maja', 'Eriksson', 'Kvinna', 'split'),
    ('Vera', 'Johansson', 'Kvinna', 'both'),
    ('Alice', 'Lundgren', 'Kvinna', 'both'),
    ('Ines', 'Bergman', 'Kvinna', 'single'),
    ('Stella', 'Axelsson', 'Kvinna', 'both'),
    ('Klara', 'Sjöberg', 'Kvinna', 'both'),
    ('Ebba', 'Lindholm', 'Kvinna', 'both'),
    ('Wilma', 'Norberg', 'Kvinna', 'split'),
    ('Signe', 'Dahl', 'Kvinna', 'both'),
    ('Tuva', 'Hellström', 'Kvinna', 'both'),
    ('Nora', 'Blomqvist', 'Kvinna', 'single'),
    ('Selma', 'Öhman', 'Kvinna', 'both'),
    ('Lovisa', 'Falk', 'Kvinna', 'both'),
    ('Hugo', 'Andersson', 'Man', 'both'),
    ('Liam', 'Pettersson', 'Man', 'both'),
    ('Elias', 'Gustafsson', 'Man', 'single'),
    ('Oscar', 'Holmberg', 'Man', 'both'),
    ('Ludvig', 'Svensson', 'Man', 'both'),
    ('Adam', 'Forsberg', 'Man', 'split'),
    ('Noah', 'Lindgren', 'Man', 'both'),
    ('William', 'Ekström', 'Man', 'both'),
    ('Viggo', 'Sundström', 'Man', 'both'),
    ('Melker', 'Hedlund', 'Man', 'single'),
    ('Arvid', 'Jonsson', 'Man', 'both'),
    ('Leon', 'Månsson', 'Man', 'both'),
    ('Theo', 'Nyström', 'Man', 'both'),
    ('Axel', 'Wallin', 'Man', 'single'),
    ('Vincent', 'Söderlund', 'Man', 'both'),
]

_STUDENT_DEFS_8A = [
    ('Freja', 'Åkesson', 'Kvinna', 'both'),
    ('Agnes', 'Lindberg', 'Kvinna', 'both'),
    ('Molly', 'Sandström', 'Kvinna', 'split'),
    ('Juni', 'Hagström', 'Kvinna', 'single'),
    ('Iris', 'Wallgren', 'Kvinna', 'both'),
    ('Saga', 'Byström', 'Kvinna', 'both'),
    ('Cornelia', 'Åström', 'Kvinna', 'both'),
    ('Ellen', 'Modig', 'Kvinna', 'both'),
    ('Sixten', 'Palm', 'Man', 'both'),
    ('Frank', 'Öberg', 'Man', 'single'),
    ('Otto', 'Lundmark', 'Man', 'both'),
    ('Charlie', 'Sjögren', 'Man', 'both'),
    ('Malte', 'Hjort', 'Man', 'split'),
    ('Edvin', 'Krantz', 'Man', 'both'),
    ('Nils', 'Tornberg', 'Man', 'both'),
]

# Adult first-name pools for guardians (index-paired with students)
_MOTHER_NAMES = [
    'Malin', 'Jenny', 'Camilla', 'Sofia', 'Therese', 'Emma', 'Linda',
    'Johanna', 'Sanna', 'Petra', 'Karolina', 'Frida', 'Cecilia', 'Helena',
    'Åsa', 'Ulrika', 'Rebecka', 'Madeleine', 'Elin', 'Susanne', 'Hanna',
    'Veronica', 'Annika', 'Jessica', 'Charlotte', 'Ida', 'Katarina',
    'Pernilla', 'Angelica', 'Marie',
]
_FATHER_NAMES = [
    'Mikael', 'Andreas', 'Daniel', 'Fredrik', 'Marcus', 'Peter', 'Stefan',
    'Henrik', 'Magnus', 'Niklas', 'Tobias', 'Martin', 'Anders', 'Jonas',
    'Christian', 'Patrik', 'Robert', 'Johannes', 'Rickard', 'Emil',
    'Sebastian', 'Björn', 'Thomas', 'Gustav', 'Oskar', 'Simon', 'Filip',
    'Alexander', 'Kristoffer', 'David',
]
# Maiden names used for 'split' households
_SPLIT_SURNAMES = {
    'Eriksson': 'Vikander', 'Norberg': 'Ahlin', 'Forsberg': 'Rosén',
    'Sandström': 'Kjellberg', 'Hjort': 'Melin',
}

_STREETS = [
    'Björkvägen', 'Tallstigen', 'Storgatan', 'Kyrkogatan', 'Solrosgatan',
    'Ekgränd', 'Lindvägen', 'Aspstigen', 'Rönngatan', 'Hagvägen',
]

STUDENTS = []
GUARDIANS = []

# 7A students get ext ids 2001–2030, 8A continues at 2031–2045 (the shared
# running index _i also keeps guardian ext ids and civic serials unique)
_ALL_STUDENT_DEFS = (
    [(CLASS_7A, 7, 2013, d) for d in _STUDENT_DEFS]
    + [(CLASS_8A, 8, 2012, d) for d in _STUDENT_DEFS_8A]
)

for _i, (_class_id, _school_year, _birth_year,
         (_given, _family, _sex, _household)) in enumerate(_ALL_STUDENT_DEFS):
    _ext = str(2001 + _i)
    _sid = _uid(f'student:{_ext}')
    _born = date(_birth_year, (_i % 12) + 1, ((_i * 7) % 27) + 1)
    _serial = 10 + _i
    _gender_digit = (_i * 2 + 1) % 10 if _sex == 'Man' else (_i * 2) % 10
    _street = f'{_STREETS[_i % len(_STREETS)]} {2 + _i}'

    _guardian_ids = []

    def _add_guardian(g_given, g_family, g_sex, slot):
        g_ext = str(3001 + _i * 2 + slot)
        gid = _uid(f'guardian:{g_ext}')
        GUARDIANS.append({
            'id': gid,
            'given_name': g_given,
            'family_name': g_family,
            'email': f'{_ascii(g_given)}.{_ascii(g_family)}@example.se',
            'phone_number': f'070-{200 + _i:03d} {10 + _i * 2:02d} {30 + slot * 17 + _i:02d}',
            'external_id': g_ext,
            'street_address': _street,
            'postal_code': '112 34',
            'locality': 'Stockholm',
            'sex': g_sex,
        })
        _guardian_ids.append(gid)

    _mother_family = _SPLIT_SURNAMES.get(_family, _family) if _household == 'split' else _family
    _mother_name = _MOTHER_NAMES[_i % len(_MOTHER_NAMES)]
    _father_name = _FATHER_NAMES[_i % len(_FATHER_NAMES)]
    if _household == 'single':
        # Alternate single mothers and single fathers
        if _i % 2 == 0:
            _add_guardian(_mother_name, _family, 'Kvinna', 0)
        else:
            _add_guardian(_father_name, _family, 'Man', 0)
    else:
        _add_guardian(_mother_name, _mother_family, 'Kvinna', 0)
        _add_guardian(_father_name, _family, 'Man', 1)

    STUDENTS.append({
        'id': _sid,
        'given_name': _given,
        'family_name': _family,
        'email': f'{_ascii(_given)[:3]}{_ascii(_family)[:3]}@student.demoskolan.se',
        'school_unit_id': _UNIT,
        'school_year': _school_year,
        'civic_no': f'{_born:%y%m%d}-{_serial:02d}{_gender_digit}{_i % 10}',
        'sex': _sex,
        'external_id': _ext,
        'birth_date': _born,
        'group_id': _class_id,
        'guardian_ids': _guardian_ids,
    })


# ---------------------------------------------------------------------------
# Teaching groups + activities — one subject per teacher, whole class in each.
# 8A gets only two subjects (SV8/MA8), taught cross-wise: Sara (mentor 7A)
# teaches SV8 and Erik (mentor 8A) teaches MA7 — so both demo personas have
# a teaching group with students they do not mentor.
# ---------------------------------------------------------------------------
# (code, subject_name, subject_code, teacher ext_id, class id, class label)
_SUBJECT_DEFS = [
    ('SV7', 'Svenska', 'SVE', '1001', CLASS_7A, '7A'),
    ('MA7', 'Matematik', 'MAT', '1002', CLASS_7A, '7A'),
    ('EN7', 'Engelska', 'ENG', '1003', CLASS_7A, '7A'),
    ('NO7', 'NO', 'NO', '1004', CLASS_7A, '7A'),
    ('IDH7', 'Idrott och hälsa', 'IDH', '1005', CLASS_7A, '7A'),
    ('SV8', 'Svenska', 'SVE', '1001', CLASS_8A, '8A'),
    ('MA8', 'Matematik', 'MAT', '1002', CLASS_8A, '8A'),
]

TEACHING_GROUPS = {}
TEACHING_GROUPS_DATA = []
ACTIVITIES_DATA = []

for _code, _subject, _subject_code, _teacher_ext, _class, _label in _SUBJECT_DEFS:
    _tg_id = _uid(f'teaching_group:{_code}')
    _teacher_id = _STAFF_BY_EXT[_teacher_ext]
    TEACHING_GROUPS[_code] = _tg_id
    TEACHING_GROUPS_DATA.append({
        'id': _tg_id,
        'display_name': _code,
        'group_code': _code,
        'group_type': 'Undervisning',
        'organisation_id': _UNIT,
        'start_date': date(2025, 8, 18),
        'class_ids': [_class],
        # Consumed by seed_duties: creates a "Lärare" DutyAssignment so the
        # SS12000 sync populates Group.teachers in skolSköld
        'teacher_ids': [_teacher_id],
    })
    ACTIVITIES_DATA.append({
        'id': _uid(f'activity:{_code}'),
        'display_name': f'{_subject} {_label}',
        'subject_code': _subject_code,
        'subject_name': _subject,
        'activity_type': 'Undervisning',
        'organisation_id': _UNIT,
        'start_date': date(2025, 8, 18),
        'teacher_ids': [_teacher_id],
        'group_ids': [_tg_id],
    })


# Name → UUID lookups (parity with the other seed modules)
PERSONS = {}
for _p in STAFF + STUDENTS + GUARDIANS:
    PERSONS[f"{_ascii(_p['given_name'])}_{_ascii(_p['family_name'])}"] = _p['id']
