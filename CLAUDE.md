# Demo SIS — SS12000 v2.1 Mock API

## Purpose

A mock School Information System (SIS) that implements the Swedish SS12000 v2.1 standard API. Used as a data source for [skolSköld](../skolSköld) and [skolSköld_Management](../skolSköld_Management) during development and demos. Provides realistic school data (students, staff, guardians, groups, duties, activities) without requiring a real SIS vendor.

## Tech Stack

- **FastAPI** — async REST API framework
- **SQLAlchemy 2.0** (async) with **aiosqlite** — ORM + SQLite database
- **Pydantic v2** — settings and schema validation
- **python-jose** — JWT authentication (OAuth2 client_credentials flow)
- **Python 3.12+**

## Project Structure

```
app/
├── api/v2/           # SS12000 v2.1 endpoints
│   ├── activities.py   # GET /v2/activities
│   ├── duties.py       # GET /v2/duties
│   ├── groups.py       # GET /v2/groups
│   ├── organisations.py # GET /v2/organisations
│   ├── persons.py      # GET /v2/persons
│   └── router.py       # Router assembly
├── auth/
│   ├── dependencies.py # Auth middleware (get_current_client)
│   ├── jwt.py          # JWT token creation/validation
│   └── routes.py       # POST /token (OAuth2)
├── models/
│   ├── activity.py     # Activity, ActivityTeacher, ActivityGroup
│   ├── duty.py         # Duty, DutyAssignment
│   ├── group.py        # Group, GroupMembership
│   ├── organisation.py # Organisation (hierarchical)
│   └── person.py       # Person, Enrolment, person_responsibles
├── schemas/
│   ├── common.py       # Shared response schemas
│   └── enums.py        # Enum definitions
├── seed/
│   ├── schoolsoft_data.py  # Anonymized SchoolSoft data (default)
│   ├── carlssons_data.py   # Anonymized Carlssons data (fallback)
│   └── seeder.py           # Database seeder (auto-seeds on startup)
├── config.py           # Pydantic settings (.env)
├── database.py         # Async SQLAlchemy engine + session
└── main.py             # FastAPI app entry point
scripts/
├── build_from_schoolsoft.py # Convert SchoolSoft TSV → SS12000 seed data
├── anonymize.py             # CLI: parse dump → anonymize → write anon_data.py
├── anonymizer.py            # Deterministic field-level anonymization
├── extract_from_dump.py     # Parse pg_dump COPY blocks
├── schema_mapper.py         # Django → SS12000 schema transformation
├── swedish_names.py         # Swedish name pools for anonymization
└── verify.py                # PII leak checker + integrity validator
```

## Data Model

All entities use UUIDs as primary keys. Hierarchy:

- **Organisation** — 4-level: Huvudman → Skola → Skolenhet (GR/GY)
- **Person** — staff, students, guardians (single table, distinguished by role/enrolments)
- **Enrolment** — student ↔ school unit (with school_type, school_year)
- **person_responsibles** — guardian ↔ student M2M (relation_type=Vårdnadshavare)
- **Group** — Klass (homeroom) or Undervisning (teaching group)
- **GroupMembership** — student ↔ group M2M
- **Duty** — staff role at an organisation (with DutyAssignment for mentor roles)
- **Activity** — lesson/teaching linking teachers (ActivityTeacher) to groups (ActivityGroup)

## Seed Data System

Two data sources, selected via `DEMO_SEED_DATA` env var:

| Value | Source | Description |
|-------|--------|-------------|
| `schoolsoft` (default) | `schoolsoft_data.py` | Anonymized SchoolSoft data: 689 students, 123 staff, 916 guardians, 33 class groups, 85 teaching groups, 89 activities |
| `carlssons` | `carlssons_data.py` | Anonymized Carlssons/Ekbergsskolan (no teaching groups or activities) |

The schoolsoft data is generated from anonymized SchoolSoft TSV exports via `python -m scripts.build_from_schoolsoft --tsv-dir ../skolSköld/demo_schoolsoft_tsv`. It includes all entity types: orgs, staff, students, guardians, class groups, teaching groups, and activities.

All data sources export: `ORGANISATIONS`, `STAFF`, `STUDENTS`, `GUARDIANS`, `GROUPS_DATA`, `ORGS`, `PERSONS`, `GROUPS`. SchoolSoft additionally exports `TEACHING_GROUPS_DATA`, `ACTIVITIES_DATA`, `TEACHING_GROUPS`.

The `external_id` fields are the critical link — the main skolSköld app uses these to match staff/students after SS12000 sync with the anonymized incident/referral data it imports separately.

The database auto-seeds on first startup if empty. Delete `data/fake_sis.db` to re-seed.

## Anonymization Pipeline

Generates `anon_data.py` from a production skolSköld PostgreSQL dump:

```bash
# Generate anonymized data
python3 -m scripts.anonymize --dump ../skolSköld/skolskold_backup.sql --seed 42

# Verify no PII leaks
python3 -m scripts.verify --dump ../skolSköld/skolskold_backup.sql
```

All anonymization is **deterministic** (hash-seeded): same seed + same dump = identical output.

| Field | Technique |
|-------|-----------|
| Names | SHA256-indexed into Swedish name pool (gender-aware) |
| Personnummer | Birth date preserved, last 4 digits scrambled |
| Email | `first.last@demoskolan.se` (staff), `firlast@student.demoskolan.se` |
| Phone | Swedish mobile format from hash |
| Address | Random from Swedish street/city pool |
| IDs | UUID5 from original ID + seed namespace |

**Never extracted**: OAuth secrets, client IDs, tenant IDs from `core_schoolsettings`.

## API Endpoints

All endpoints require JWT Bearer token. Get token:

```bash
curl -X POST http://localhost:8080/token \
  -d "grant_type=client_credentials&client_id=skolskold_demo&client_secret=demo_secret_123"
```

| Endpoint | Methods | Key Filters |
|----------|---------|-------------|
| `/v2/organisations` | GET, GET/:id, POST /lookup | parent, schoolUnitCode, type |
| `/v2/persons` | GET, GET/:id, POST /lookup | expand: enrolments, responsibles |
| `/v2/groups` | GET, GET/:id, POST /lookup | organisation, groupType, expand: groupMemberships |
| `/v2/duties` | GET, GET/:id, POST /lookup | dutyAt, dutyRole |
| `/v2/activities` | GET, GET/:id, POST /lookup | organisation, activityType, subject |
| `/health` | GET | — |
| `/token` | POST | OAuth2 client_credentials |

Response format: `{"data": [...], "pageToken": null}`

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload                            # SchoolSoft data (default)
DEMO_SEED_DATA=carlssons uvicorn app.main:app --reload   # Carlssons data
```

## Deployment

Docker + CapRover. Persistent SQLite in `/app/data/`.

```bash
docker build -t demo-sis .
docker run -p 8080:8080 -v sis-data:/app/data demo-sis
```

Set env vars in CapRover: `DEMO_SEED_DATA=schoolsoft`, `JWT_SECRET=<production-secret>`, etc.

## Sibling Projects

- **skolSköld** (`../skolSköld`) — Main Django app that syncs data from this SIS
- **skolSköld_Management** (`../skolSköld_Management`) — React management dashboard
