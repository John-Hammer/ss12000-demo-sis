"""Single-school projections of the Tallviken kommun dataset.

Serves ONE Tallviken school unit as its own SS12000 endpoint, so each
school's SyncSource in the kommun demo pulls only its own students/staff/
groups — the same per-school-SIS reality a real kommun has (SchoolSoft
provisions a webapp+API per school). Selected via
``DEMO_SEED_DATA=kommun_tallvik`` / ``kommun_bjorkangen`` /
``kommun_gymnasiet``. Derived from ``kommun_data`` so the three
single-school views and the combined dataset stay consistent (one source
of truth). Mirrors lotr_school_data.build().
"""
from . import kommun_data as _k

# DEMO_SEED_DATA value -> the Skolenhet organisation id it serves.
_UNIT = {
    'kommun_tallvik': _k.ORGS['tallvik_gr'],
    'kommun_bjorkangen': _k.ORGS['bjorkangen_gr'],
    'kommun_gymnasiet': _k.ORGS['gymnasiet_gy'],
}

# The Skolenhet's parent "Skola" node, kept so the org tree stays intact.
_PARENT_SKOLA = {
    _k.ORGS['tallvik_gr']: _k.ORGS['tallvik_skola'],
    _k.ORGS['bjorkangen_gr']: _k.ORGS['bjorkangen_skola'],
    _k.ORGS['gymnasiet_gy']: _k.ORGS['gymnasiet_skola'],
}


def build(which):
    """Return the seeder's data-module tuple for one Tallviken school."""
    target = _UNIT[which]

    # Org tree: Huvudman -> the school's Skola node -> the target Skolenhet.
    keep_orgs = {_k.ORGS['huvudman'], _PARENT_SKOLA[target], target}
    organisations = [o for o in _k.ORGANISATIONS if o['id'] in keep_orgs]

    groups_data = [g for g in _k.GROUPS_DATA
                   if g.get('organisation_id') == target]
    keep_class_ids = {g['id'] for g in groups_data}
    students = [s for s in _k.STUDENTS
                if s.get('group_id') in keep_class_ids
                or s.get('school_unit_id') == target]

    teaching = [t for t in _k.TEACHING_GROUPS_DATA
                if t.get('organisation_id') == target]
    keep_teach_ids = {t['id'] for t in teaching}
    activities = [a for a in _k.ACTIVITIES_DATA
                  if any(gid in keep_teach_ids for gid in a.get('group_ids', []))]

    # Staff: everyone with a duty at this unit (the generator places every
    # staff member at exactly one unit), plus mentors/teachers as a guard.
    staff_ids = {s['id'] for s in _k.STAFF
                 if s.get('school_unit_id') == target}
    staff_ids.update(g['mentor_id'] for g in groups_data if g.get('mentor_id'))
    for a in activities:
        staff_ids.update(a.get('teacher_ids', []))
    staff = [s for s in _k.STAFF if s['id'] in staff_ids]

    # Guardians of the kept students. Households may span schools (siblings
    # at different units share guardians); each slice carries the guardians
    # its own students reference, so no dangling responsible links.
    guardian_ids = set()
    for s in students:
        guardian_ids.update(s.get('guardian_ids', []))
    guardians = [g for g in _k.GUARDIANS if g['id'] in guardian_ids]

    return (organisations, staff, students, guardians, groups_data,
            teaching, activities,
            _k.ORGS, _k.PERSONS, _k.GROUPS, _k.TEACHING_GROUPS)
