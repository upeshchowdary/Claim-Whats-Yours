# Claim What's Yours

> Deterministic eligibility discovery and navigation platform for Indian government schemes (Union, state, and UT).

---

## Overview

**Claim What's Yours** is a civic-tech platform designed to simplify how Indian citizens discover, evaluate, and claim government welfare schemes and public service entitlements. 

- **Deterministic Rule Engine**: Eligibility evaluation is strictly deterministic, declarative, and auditable—no speculative runtime LLM hallucinations for eligibility criteria.
- **Multilingual Citizen Assistant**: AI-driven conversational guidance to translate citizen context into profile attributes and navigate applications.
- **Modern Interactive UI**: High-performance React, Tailwind CSS, Three.js 3D visualizations, and accessible component library.
- **Robust Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL / SQLite, and comprehensive test suite.

---

## Project Structure

```
├── backend/                  # FastAPI backend service
│   ├── alembic/              # Database migration scripts
│   ├── data/                 # Jurisdictions and profile field schemas
│   ├── scripts/              # Validation, import, and seed scripts
│   ├── src/claim_whats_yours/# Core application modules
│   └── tests/                # Unit and integration test suite
├── frontend/                 # Vite + React + TypeScript frontend
│   ├── src/components/       # UI, 3D Hero, and layout components
│   ├── src/pages/            # Application pages (Schemes, Eligibility, etc.)
│   └── src/lib/              # API client and utility helpers
├── docs/                     # Architectural, API, and security documentation
└── docker-compose.yml        # Multi-container orchestration
```

---

## Quick Start

### Prerequisites
- Node.js 18+ & npm
- Python 3.12+
- Docker & Docker Compose (optional, for containerized run)

### Backend Setup

```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -e ".[dev]"
copy .env.example .env    # On Windows (or cp on Linux/macOS)
alembic upgrade head
uvicorn claim_whats_yours.app:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Docker Compose

```bash
docker-compose up --build
```

---

## Verification & Testing

- **Backend Tests**: `pytest backend/tests`
- **Linting & Formatting**: `ruff check backend` and `ruff format --check backend`
- **Frontend Tests**: `npm run test` (inside `frontend/`)
- **Frontend Build**: `npm run build` (inside `frontend/`)

---

## Documentation

Full architectural specifications, data governance policies, and API contracts can be found in the [`docs/`](./docs) folder:
- [Architecture & Request Flow](docs/backend/ARCHITECTURE.md)
- [API Contract](docs/backend/API_CONTRACT.md)
- [Rule Engine](docs/backend/RULE_ENGINE.md)
- [Data Governance](docs/backend/DATA_GOVERNANCE.md)
- [Privacy & Security](docs/backend/PRIVACY_SECURITY.md)

---

## License

All rights reserved.
