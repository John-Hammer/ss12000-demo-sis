# SS12000 Demo SIS

Mock SS12000 v2.1 API server with Lord of the Rings themed demo data.
Used for testing Skolsköld's SS12000 integration.

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

## Demo Data (Lord of the Rings Theme)

The server auto-seeds with LotR characters on first run:

### School Structure
- **Middle-earth Educational Authority** (Huvudman)
  - **Rivendell Academy** (Skola)
    - Rivendell Grundskola (Years 1-9)
    - Rivendell Gymnasium (Years 10-12)

### Staff (7)
| Name | Role | Signature |
|------|------|-----------|
| Gandalf the Grey | Rektor (Principal) | GAN |
| Elrond Half-elven | Rektor (Deputy) | ELR |
| Galadriel of Lothlórien | Lärare (Teacher) | GAL |
| Celeborn the Wise | Lärare (Teacher) | CEL |
| Aragorn Elessar | Lärare (Teacher) | ARA |
| Bilbo Baggins | Bibliotekarie | BIL |
| Tom Bombadil | Annan personal | TOM |

### Students (10)
| Name | Class | Guardian |
|------|-------|----------|
| Frodo Baggins | 4A Shire | Bilbo |
| Samwise Gamgee | 4A Shire | Hamfast |
| Meriadoc Brandybuck | 4B Buckland | Saradoc |
| Peregrin Took | 4B Buckland | Paladin |
| Faramir of Gondor | 5A Gondor | Denethor |
| Éowyn of Rohan | 5A Gondor | Théoden |
| Boromir of Gondor | GY1 Fellowship | Denethor |
| Éomer of Rohan | GY1 Fellowship | Théoden |
| Arwen Undómiel | GY2 Elven | Elrond |
| Legolas Greenleaf | GY2 Elven | Thranduil |

### Classes (5)
- 4A - The Shire Class (Mentor: Aragorn)
- 4B - Buckland Class (Mentor: Celeborn)
- 5A - Gondor Class (Mentor: Galadriel)
- GY1 - Fellowship (Mentor: Gandalf)
- GY2 - Elven Studies (Mentor: Elrond)

## Deployment (CapRover)

This project is designed for CapRover deployment:

1. Create app with "Has Persistent Data" checked
2. Add persistent directory: `/app/data`
3. Set environment variables (use production secrets!)
4. Connect GitHub repo for webhook auto-deploy

## License

MIT - Use freely for testing and development.
