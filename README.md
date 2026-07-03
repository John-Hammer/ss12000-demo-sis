# SS12000 Demo SIS

Mock SS12000 v2.1 API server with synthetic Swedish school data.
Used as the data source for the Skolsköld demo instance and for testing
the SS12000 integration.

## Quick Start

1. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or .venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy environment file:
   ```bash
   cp .env.example .env
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

5. Test the API:
   ```bash
   curl http://localhost:8080/health
   ```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `POST /token` | OAuth2 token (client_credentials) |
| `GET /v2/organisations` | List organisations |
| `GET /v2/persons` | List all persons (students, staff, guardians) |
| `GET /v2/groups` | List all groups/classes |
| `GET /v2/duties` | List staff duty assignments |

## Authentication

Get a token using OAuth2 client_credentials flow:
```bash
curl -X POST http://localhost:8080/token \
  -d "grant_type=client_credentials" \
  -d "client_id=skolskold_demo" \
  -d "client_secret=demo_secret_123"
```

Use the token in subsequent requests:
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8080/v2/persons
```

## Demo Data

The server auto-seeds on first run. The data source is selected with the
`DEMO_SEED_DATA` env var (`minimal` is the default — see CLAUDE.md for the
full table). If the deployed dataset name or version changes, the database
is **wiped and reseeded automatically on startup** (tracked in the
`seed_meta` table), so pushing new seed data updates the online demo
despite the persistent volume.

### Minimal dataset (default) — two classes, KISS

**Demoskolan** (Huvudman → Skola → Grundskola), class **7A** with 30
students and class **7B** with 15 students (year 7, born 2013),
~2 guardians each (83 guardians total).

| Staff | Role | Assignment |
|-------|------|------------|
| Sara Lindqvist | Lärare | **Mentor of 7A** + teaches SV7 + SV7B (Svenska) |
| Erik Sandberg | Lärare | **Mentor of 7B** + teaches MA7 + MA7B (Matematik) |
| Maria Holmgren | Lärare | EN7 (Engelska) |
| Johan Ek | Lärare | NO7 (NO) |
| Anna Bergström | Lärare | IDH7 (Idrott och hälsa) |
| Eva Ström | Kurator | EHT |
| Lars Wikström | Rektor | Skolledning |
| Karin Åberg | Administratör | — |

Every 7A student is a member of all five 7A teaching groups; 7B has only
SV7B and MA7B, taught cross-wise so both main demo personas have a
teaching group whose students they do NOT mentor. Mentorship is
modelled as a Duty `assignmentRole` of type `Mentor` on the class group;
teaching as `Lärare` assignments on the teaching groups plus Activities —
matching how skolSköld's SS12000 sync distinguishes `Group.mentor` from
`Group.teachers`.

The four demo login personas in skolSköld (`setup_demo_users`) map to
staff 1001 (mentor), 1002 (lärare), 1006 (EHT), 1007 (skolledare) via
their deterministic uuid5 person IDs. Two students carry
sekretessmarkering (set by the seeder for protected-identity testing).

## Deployment (CapRover)

This project is designed for CapRover deployment:

1. Create app with "Has Persistent Data" checked
2. Add persistent directory: `/app/data`
3. Set environment variables (use production secrets!)
4. Connect GitHub repo for webhook auto-deploy

## License

MIT - Use freely for testing and development.
