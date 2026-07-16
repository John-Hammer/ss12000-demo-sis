"""
Database seeder for demo data.
Seeds the database with school data from the selected data source.

Set DEMO_SEED_DATA env var to choose data source:
  minimal (default) — hand-curated KISS dataset: one class (7A, 30 students),
                      5 teachers (one mentor), 1 EHT, 1 rektor, 1 admin
  schoolsoft        — anonymized SchoolSoft data with teaching groups + activities
  carlssons         — anonymized production data from Carlssons/Ekbergsskolan (no activities)

The seeder stamps the database with the dataset name + version (seed_meta
table). If the deployed code carries a different dataset or version, the
database is wiped and reseeded automatically on startup — so pushing a new
dataset updates the online demo SIS despite the persistent volume.
"""
import os
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session_maker, create_tables, drop_tables
from ..models.organisation import Organisation
from ..models.person import Person, Enrolment, person_responsibles
from ..models.group import Group, GroupMembership
from ..models.duty import Duty, DutyAssignment
from ..models.activity import Activity, ActivityTeacher, ActivityGroup
from ..models.seed_meta import SeedMeta

DATA_SOURCE = os.environ.get("DEMO_SEED_DATA", "minimal")
DATASET_VERSION = "1"

if DATA_SOURCE == "minimal":
    try:
        from .minimal_data import (
            ORGANISATIONS, STAFF, STUDENTS, GUARDIANS, GROUPS_DATA,
            TEACHING_GROUPS_DATA, ACTIVITIES_DATA,
            ORGS, PERSONS, GROUPS, TEACHING_GROUPS,
            DATASET_VERSION,
        )
    except ImportError:
        DATA_SOURCE = "schoolsoft"  # fall back

if DATA_SOURCE == "schoolsoft":
    try:
        from .schoolsoft_data import (
            ORGANISATIONS, STAFF, STUDENTS, GUARDIANS, GROUPS_DATA,
            TEACHING_GROUPS_DATA, ACTIVITIES_DATA,
            ORGS, PERSONS, GROUPS, TEACHING_GROUPS
        )
    except ImportError:
        DATA_SOURCE = "carlssons"  # fall back

if DATA_SOURCE == "carlssons":
    try:
        from .carlssons_data import (
            ORGANISATIONS, STAFF, STUDENTS, GUARDIANS, GROUPS_DATA,
            ORGS, PERSONS, GROUPS
        )
        # Teaching groups and activities are optional for carlssons data
        try:
            from .carlssons_data import TEACHING_GROUPS_DATA, ACTIVITIES_DATA, TEACHING_GROUPS
        except ImportError:
            TEACHING_GROUPS_DATA = []
            ACTIVITIES_DATA = []
    except ImportError:
        raise ImportError("No seed data available. Generate with: python -m scripts.build_from_schoolsoft")

DATASET_STAMP = f"{DATA_SOURCE}:{DATASET_VERSION}"


async def _current_stamp(session: AsyncSession):
    """Return the dataset stamp the DB was seeded with, or None."""
    result = await session.execute(
        select(SeedMeta).filter(SeedMeta.key == "dataset")
    )
    row = result.scalar_one_or_none()
    return row.value if row else None


async def seed_database():
    """
    Seed the database if it is empty, or wipe and reseed if it was seeded
    with a different dataset/version than the code now carries.
    """
    async with async_session_maker() as session:
        stamp = await _current_stamp(session)
        result = await session.execute(select(Organisation).limit(1))
        has_data = result.scalar_one_or_none() is not None

        if has_data and stamp == DATASET_STAMP:
            print(f"Database already seeded with {DATASET_STAMP}, skipping...")
            return

        if has_data:
            print(f"Dataset changed ({stamp or 'unstamped'} -> {DATASET_STAMP}), wiping database...")
            await drop_tables()
            await create_tables()

    async with async_session_maker() as session:
        source_labels = {
            "minimal": "minimal KISS (one class)",
            "schoolsoft": "SchoolSoft (anonymized)",
            "carlssons": "Carlssons/Ekbergsskolan",
        }
        source_label = source_labels.get(DATA_SOURCE, DATA_SOURCE)
        print(f"Seeding database with {source_label} demo data...")

        # 1. Create organisations
        await seed_organisations(session)

        # 2. Create staff (as persons)
        await seed_staff(session)

        # 3. Create guardians (as persons)
        await seed_guardians(session)

        # 4. Create groups (class groups)
        await seed_groups(session)

        # 5. Create teaching groups (if available)
        if TEACHING_GROUPS_DATA:
            await seed_teaching_groups(session)

        # 6. Create students (as persons with enrolments)
        await seed_students(session)

        # 7. Create duties for staff
        await seed_duties(session)

        # 8. Create group memberships
        await seed_memberships(session)

        # 9. Create activities (if available)
        if ACTIVITIES_DATA:
            await seed_activities(session)

        # 10. Mark two students as protected (for sekretessmarkering testing)
        await seed_protected_students(session)

        # 11. Stamp the DB with the dataset name + version
        session.add(SeedMeta(key="dataset", value=DATASET_STAMP))

        await session.commit()
        print("Database seeding complete!")
        print(f"  - {len(STAFF)} staff members")
        print(f"  - {len(STUDENTS)} students")
        print(f"  - {len(GUARDIANS)} guardians")
        print(f"  - {len(GROUPS_DATA)} class groups")
        if TEACHING_GROUPS_DATA:
            print(f"  - {len(TEACHING_GROUPS_DATA)} teaching groups")
        if ACTIVITIES_DATA:
            print(f"  - {len(ACTIVITIES_DATA)} activities")


async def seed_organisations(session: AsyncSession):
    """Seed organisation hierarchy."""
    print("  Creating organisations...")

    for org_data in ORGANISATIONS:
        org = Organisation(
            id=org_data["id"],
            display_name=org_data["display_name"],
            organisation_type=org_data["organisation_type"],
            organisation_code=org_data.get("organisation_code"),
            organisation_number=org_data.get("organisation_number"),
            school_unit_code=org_data.get("school_unit_code"),
            municipality_code=org_data.get("municipality_code"),
            email=org_data.get("email"),
            phone_number=org_data.get("phone_number"),
            url=org_data.get("url"),
            street_address=org_data.get("street_address"),
            postal_code=org_data.get("postal_code"),
            locality=org_data.get("locality"),
            school_types=org_data.get("school_types"),
            parent_id=org_data.get("parent_id"),
            start_date=date(2024, 1, 1),
        )
        session.add(org)

    await session.flush()


async def seed_staff(session: AsyncSession):
    """Seed staff members as persons."""
    print("  Creating staff...")

    for staff_data in STAFF:
        person = Person(
            id=staff_data["id"],
            given_name=staff_data["given_name"],
            family_name=staff_data["family_name"],
            middle_name=staff_data.get("middle_name"),
            email=staff_data.get("email"),
            edu_person_principal_name=staff_data.get("edu_person_principal_name", staff_data.get("email")),
            birth_date=staff_data.get("birth_date"),
            sex=staff_data.get("sex"),
            civic_no=staff_data.get("civic_no"),
            external_id=staff_data.get("external_id"),
            external_id_context="http://demo-sis.example.se",
            street_address=staff_data.get("street_address"),
            postal_code=staff_data.get("postal_code"),
            locality=staff_data.get("locality"),
            person_status="Aktiv",
        )
        session.add(person)

    await session.flush()


async def seed_guardians(session: AsyncSession):
    """Seed guardians as persons."""
    print("  Creating guardians...")

    for guard_data in GUARDIANS:
        person = Person(
            id=guard_data["id"],
            given_name=guard_data["given_name"],
            family_name=guard_data["family_name"],
            email=guard_data.get("email"),
            birth_date=guard_data.get("birth_date"),
            sex=guard_data.get("sex"),
            phone_number=guard_data.get("phone_number"),
            civic_no=guard_data.get("civic_no"),
            external_id=guard_data.get("external_id"),
            external_id_context="http://demo-sis.example.se",
            street_address=guard_data.get("street_address"),
            postal_code=guard_data.get("postal_code"),
            locality=guard_data.get("locality"),
            person_status="Aktiv",
        )
        session.add(person)

    await session.flush()


async def seed_groups(session: AsyncSession):
    """Seed school groups (classes)."""
    print("  Creating class groups...")

    for group_data in GROUPS_DATA:
        group = Group(
            id=group_data["id"],
            display_name=group_data["display_name"],
            group_code=group_data.get("group_code"),
            group_type=group_data["group_type"],
            school_type=group_data.get("school_type"),
            organisation_id=group_data["organisation_id"],
            start_date=group_data["start_date"],
        )
        session.add(group)

    await session.flush()


async def seed_teaching_groups(session: AsyncSession):
    """Seed teaching groups (Undervisning)."""
    print("  Creating teaching groups...")

    for group_data in TEACHING_GROUPS_DATA:
        group = Group(
            id=group_data["id"],
            display_name=group_data["display_name"],
            group_code=group_data.get("group_code"),
            group_type=group_data["group_type"],
            organisation_id=group_data["organisation_id"],
            start_date=group_data["start_date"],
        )
        session.add(group)

    await session.flush()


async def seed_students(session: AsyncSession):
    """Seed students as persons with enrolments and guardian relationships."""
    print("  Creating students...")

    for student_data in STUDENTS:
        # Create person
        person = Person(
            id=student_data["id"],
            given_name=student_data["given_name"],
            family_name=student_data["family_name"],
            email=student_data.get("email"),
            birth_date=student_data.get("birth_date"),
            sex=student_data.get("sex"),
            civic_no=student_data.get("civic_no"),
            external_id=student_data.get("external_id"),
            external_id_context="http://demo-sis.example.se",
            person_status="Aktiv",
        )
        session.add(person)
        await session.flush()

        # Create enrolment
        school_year = student_data.get("school_year")
        enrolment = Enrolment(
            person_id=student_data["id"],
            organisation_id=student_data["school_unit_id"],
            school_type="GR" if (school_year or 0) <= 9 else "GY",
            school_year=school_year,
            start_date=date(2024, 8, 15),
        )
        session.add(enrolment)

        # Create guardian relationships using raw SQL insert
        for guardian_id in student_data.get("guardian_ids", []):
            await session.execute(
                person_responsibles.insert().values(
                    person_id=student_data["id"],
                    responsible_id=guardian_id,
                    relation_type="Vårdnadshavare"
                )
            )

    await session.flush()


async def seed_duties(session: AsyncSession):
    """Seed staff duties and assignments."""
    print("  Creating duties...")

    # Find the "Skola" org for duty assignments
    school_org_id = None
    for org_data in ORGANISATIONS:
        if org_data["organisation_type"] == "Skola":
            school_org_id = org_data["id"]
            break
    if not school_org_id:
        school_org_id = ORGANISATIONS[0]["id"]

    # Spec Code_DutyRole has exactly six values — rich seed roles are
    # translated the way a real SIS must express them, and the EHT-ness
    # travels as an assignmentRole (Elevhälsopersonal / Specialpedagog),
    # which is where SS12000 actually carries it.
    SPEC_DUTY_ROLE = {
        "Rektor": "Rektor",
        "Biträdande rektor": "Rektor",
        "Lärare": "Lärare",
        "Förskollärare": "Förskollärare",
        "Förskolechef": "Förskolechef",
        "Specialpedagog": "Övrig pedagogisk personal",
        "Speciallärare/specialpedagog": "Övrig pedagogisk personal",
        "Fritidspedagog": "Övrig pedagogisk personal",
        "Lärarassistent": "Övrig pedagogisk personal",
    }
    EHT_ASSIGNMENT = {
        "Kurator": "Elevhälsopersonal",
        "Skolsköterska": "Elevhälsopersonal",
        "Skolläkare": "Elevhälsopersonal",
        "Skolpsykolog": "Elevhälsopersonal",
        "Psykolog": "Elevhälsopersonal",
        "Specialpedagog": "Specialpedagog",
        "Speciallärare/specialpedagog": "Specialpedagog",
    }
    eht_group_id = GROUPS_DATA[0]["id"] if GROUPS_DATA else None

    for staff_data in STAFF:
        seed_role = staff_data["duty_role"]
        spec_role = SPEC_DUTY_ROLE.get(seed_role, "Annan personal")
        # Keep the rich seed role visible in the free-text description,
        # like a real huvudman often does.
        description = staff_data.get("description") or seed_role

        # Create duty at the main school
        duty = Duty(
            person_id=staff_data["id"],
            organisation_id=school_org_id,
            duty_role=spec_role,
            description=description,
            signature=staff_data.get("signature"),
            duty_percent=100,
            start_date=date(2024, 1, 1),
        )
        session.add(duty)
        await session.flush()

        # EHT staff: spec-correct signal is an assignmentRole
        eht_type = EHT_ASSIGNMENT.get(seed_role)
        if eht_type and eht_group_id:
            session.add(DutyAssignment(
                duty_id=duty.id,
                group_id=eht_group_id,
                assignment_role_type=eht_type,
                start_date=date(2024, 8, 15),
            ))

        # Create mentor assignments for teachers
        for group_data in GROUPS_DATA:
            if group_data.get("mentor_id") == staff_data["id"]:
                assignment = DutyAssignment(
                    duty_id=duty.id,
                    group_id=group_data["id"],
                    assignment_role_type="Mentor",
                    start_date=date(2024, 8, 15),
                )
                session.add(assignment)

        # Create teacher assignments for teaching groups that declare
        # teacher_ids (minimal dataset) — this is what populates
        # Group.teachers in skolSköld via the duties endpoint
        for tg_data in TEACHING_GROUPS_DATA:
            if staff_data["id"] in tg_data.get("teacher_ids", []):
                assignment = DutyAssignment(
                    duty_id=duty.id,
                    group_id=tg_data["id"],
                    assignment_role_type="Lärare",
                    start_date=date(2024, 8, 15),
                )
                session.add(assignment)

    await session.flush()


async def seed_memberships(session: AsyncSession):
    """Seed group memberships for students."""
    print("  Creating group memberships...")

    # Create class group memberships for students
    for student_data in STUDENTS:
        if not student_data.get("group_id"):
            continue
        membership = GroupMembership(
            group_id=student_data["group_id"],
            person_id=student_data["id"],
            start_date=date(2024, 8, 15),
        )
        session.add(membership)

    # Create teaching group memberships based on class membership
    # Students in a class are also members of teaching groups that include that class
    class_to_students = {}
    for student_data in STUDENTS:
        class_id = student_data.get("group_id")
        if not class_id:
            continue
        if class_id not in class_to_students:
            class_to_students[class_id] = []
        class_to_students[class_id].append(student_data["id"])

    for tg_data in TEACHING_GROUPS_DATA:
        for class_id in tg_data.get("class_ids", []):
            for student_id in class_to_students.get(class_id, []):
                membership = GroupMembership(
                    group_id=tg_data["id"],
                    person_id=student_id,
                    start_date=date(2024, 8, 15),
                )
                session.add(membership)

    await session.flush()


async def seed_activities(session: AsyncSession):
    """Seed activities (lessons) linking teachers to teaching groups."""
    print("  Creating activities...")

    for act_data in ACTIVITIES_DATA:
        # Create activity
        activity = Activity(
            id=act_data["id"],
            display_name=act_data["display_name"],
            organisation_id=act_data["organisation_id"],
            start_date=act_data["start_date"],
            end_date=act_data.get("end_date"),
            activity_type=act_data.get("activity_type"),
            subject_code=act_data.get("subject_code"),
            subject_name=act_data.get("subject_name"),
        )
        session.add(activity)
        await session.flush()

        # Create teacher assignments
        for teacher_id in act_data.get("teacher_ids", []):
            teacher = ActivityTeacher(
                activity_id=act_data["id"],
                person_id=teacher_id,
                start_date=date(2024, 8, 15),
                allocation_percent=100 // len(act_data.get("teacher_ids", [1])),
            )
            session.add(teacher)

        # Create group assignments
        for group_id in act_data.get("group_ids", []):
            group = ActivityGroup(
                activity_id=act_data["id"],
                group_id=group_id,
            )
            session.add(group)

    await session.flush()


async def seed_protected_students(session: AsyncSession):
    """Mark two students as protected for sekretessmarkering testing.

    Picks students that have group memberships and guardians,
    regardless of which data source generated the seed data.
    """
    print("  Setting protected student markers...")

    markings = ["Sekretessmarkering", "Skyddad folkbokf\u00f6ring"]

    # Find students with both a group_id and at least one guardian
    candidates = [
        s for s in STUDENTS
        if s.get("group_id") and s.get("guardian_ids")
    ]

    for i, marking in enumerate(markings):
        if i >= len(candidates):
            break
        student_data = candidates[i]
        result = await session.execute(
            select(Person).filter(Person.id == student_data["id"])
        )
        person = result.scalar_one_or_none()
        if person:
            person.security_marking = marking
            print(f"    {person.given_name} {person.family_name} -> {marking}")

    await session.flush()
