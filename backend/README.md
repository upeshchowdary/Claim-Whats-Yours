# Claim What's Yours: Backend

## What it is

The backend is the eligibility discovery API for "Claim What's Yours", a catalogue of Indian government benefit schemes (Union, state and UT). Eligibility evaluation is deterministic code and declarative rule data. There are no runtime LLM or AI calls.

## Requirements

- Python 3.12+
- Windows PowerShell or Command Prompt (commands below)

## Setup (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Configuration

Copy the example file and fill in your own values. Use placeholders only; never commit `.env`.

```bat
copy .env.example .env
```

- `ADMIN_API_TOKEN`: leave empty to disable the admin endpoints. Set a long random value to enable them.
- `DATABASE_URL`: defaults to a local SQLite file. For PostgreSQL use a `postgresql+psycopg://` URL.

Configuration is read from environment variables only. No paid API keys are required.

## Migrations

```bat
alembic upgrade head
```

Run migrations before starting the app. The production container does this automatically.

## Run

```bat
uvicorn claim_whats_yours.app:app --reload --port 8000
```

If the package is not installed, set the source path first:

```bat
set PYTHONPATH=src
uvicorn claim_whats_yours.app:app --reload --port 8000
```

## Tests

```bat
python -m pytest tests -q
```

## Lint and format check

```bat
python -m ruff check src tests alembic scripts
python -m ruff format --check src tests alembic scripts
```

## Scripts

Both scripts take a directory of scheme source records.

```bat
python scripts\validate_schemes.py <dir>
python scripts\import_schemes.py <dir>
```

- `validate_schemes.py` checks records and reports problems. It changes nothing.
- `import_schemes.py` imports records as drafts only. Imports never publish. Publishing is a separate, human-reviewed admin action that records who and when.

## Docs

Specifications live in the repository's `docs/backend/` directory:

- `ARCHITECTURE.md`: components, layering, request flow, deployment
- `API_CONTRACT.md`: endpoints, schemas, error codes, pagination

If code and spec disagree, the spec wins until it is explicitly changed.

## Data status

The database currently has zero published schemes. No official scheme data is loaded. Scheme records must come from sourced, verified inputs before they can be imported and published.
