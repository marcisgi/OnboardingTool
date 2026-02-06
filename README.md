# Application Catalog

An internal, self-hosted catalog for discovering and managing internal tools. The system is split into two services:

- **UI Server** (`ui/app/main.py`): server-rendered HTML pages, Tailwind styling, and minimal JavaScript.
- **BFF API** (`bff/app/main.py`): JSON API with all business logic and PostgreSQL access.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set the PostgreSQL connection for the BFF:

```bash
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/onboarding
```

Start the BFF:

```bash
uvicorn bff.app.main:app --host 0.0.0.0 --port 8001
```

Start the UI server (in another terminal):

```bash
export BFF_URL=http://localhost:8001
uvicorn ui.app.main:app --host 0.0.0.0 --port 8000
```

Open the UI at `http://localhost:8000`.

## API Docs

The BFF exposes Swagger/OpenAPI docs at:

```
http://localhost:8001/api/docs
```
