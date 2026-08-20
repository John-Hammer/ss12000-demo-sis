"""Single-school projections of the combined LOTR dataset.

Serves ONE Rivendell school as its own SS12000 endpoint — the way SchoolSoft
provisions a webapp+API per school — so each school's SyncSource in the main
app pulls only its own students/staff/groups. Selected via
``DEMO_SEED_DATA=lotr_gr`` (Rivendell Grundskola) or ``lotr_gy`` (Rivendell
Gymnasium). Derived from ``lotr_data`` so the two single-school views stay
consistent with the combined kommun dataset (one source of truth).

The slice keys on **class-group organisation**, not the noisy per-staff
``school_unit_id`` in the source data: a school's students are those in its
class groups (or enrolled at its unit), its staff are the mentors/teachers of
those groups plus anyone explicitly placed at the unit, and its guardians are
the guardians of those students.
"""
from . import lotr_data as _l

# DEMO_SEED_DATA value -> the Skolenhet organisation id it serves.
_UNIT = {
    'lotr_gr': _l.ORGS['rivendell_grundskola'],
    'lotr_gy': _l.ORGS['rivendell_gymnasium'],
}


def build(which):
    """Return the seeder's data-module tuple for one school."""
    target = _UNIT[which]

    # Org tree: Huvudman -> Skola -> only the target Skolenhet.
    keep_orgs = {_l.ORGS['middle_earth'], _l.ORGS['rivendell_academy'], target}
    organisations = [o for o in _l.ORGANISATIONS if o['id'] in keep_orgs]

    # Class groups at this unit, and the students in them (or enrolled here).
    groups_data = [g for g in _l.GROUPS_DATA if g.get('organisation_id') == target]
    keep_class_ids = {g['id'] for g in groups_data}
    students = [s for s in _l.STUDENTS
                if s.get('group_id') in keep_class_ids
                or s.get('school_unit_id') == target]

    # Teaching groups + activities at this unit.
    teaching = [t for t in _l.TEACHING_GROUPS_DATA if t.get('organisation_id') == target]
    keep_teach_ids = {t['id'] for t in teaching}
    activities = [a for a in _l.ACTIVITIES_DATA
                  if any(gid in keep_teach_ids for gid in a.get('group_ids', []))]

    # Staff: class mentors + activity teachers here + anyone placed at the unit.
    staff_ids = {g['mentor_id'] for g in groups_data if g.get('mentor_id')}
    for a in activities:
        staff_ids.update(a.get('teacher_ids', []))
    staff_ids.update(s['id'] for s in _l.STAFF if s.get('school_unit_id') == target)
    staff = [s for s in _l.STAFF if s['id'] in staff_ids]

    # Guardians of the kept students.
    guardian_ids = set()
    for s in students:
        guardian_ids.update(s.get('guardian_ids', []))
    guardians = [g for g in _l.GUARDIANS if g['id'] in guardian_ids]

    # The id registries stay whole — they are lookup tables; only referenced
    # ids get materialised (the filtered lists above drive what is created).
    return (organisations, staff, students, guardians, groups_data,
            teaching, activities,
            _l.ORGS, _l.PERSONS, _l.GROUPS, _l.TEACHING_GROUPS)
