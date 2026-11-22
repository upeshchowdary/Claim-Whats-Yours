# CLAUDE.md — Claim What's Yours

Project: **Claim What's Yours**, an India-wide government benefits discovery platform covering 28 states, 8 Union Territories, and Central Government schemes.

This file is the operating guide for agents and contributors working in this repository. It is canonical for rules; specs live in `docs/backend/`.

## Repository layout

```
CLAUDE.md                 this file
docs/backend/             specs (ARCHITECTURE.md, API_CONTRACT.md)
backend/                  Python service
  pyproject.toml
  alembic/                migrations
  src/claim_whats_yours/  application package (see ARCHITECTURE.md)
  tests/                  pytest suite
```

## Stack

- Python 3.12+
- FastAPI, Pydantic v2
- SQLAlchemy 2 (typed ORM style), Alembic for migrations
- SQLite by default; PostgreSQL via `DATABASE_URL`
- pytest + httpx for tests
- ruff for lint and format

Configuration is read from environment variables only. No paid API keys are required to run, test, or deploy.

## Hard rules

These rules are non-negotiable. Reviewers reject changes that violate them.

1. **No runtime LLM or AI calls.** Eligibility and scheme logic is deterministic code and data. No model, embedding, or LLM client may be imported or invoked at request time.
2. **No `eval` or `exec` of rules.** Rules are declarative data (see ARCHITECTURE.md, domain/rules). They are interpreted by a fixed evaluator with an explicit operator set. Never compile rule text into Python.
3. **Never invent scheme data.** Every scheme record, criterion, amount, deadline, and document must come from an imported source record that carries a source reference. If a value is unknown, store it as unknown; do not guess.
4. **Never auto-verify schemes.** Verification is a human review step. Imports create drafts only. Only an explicit validate-then-publish admin action changes status, and it records who and when.
5. **Never collect sensitive identifiers.** Do not accept, store, or log Aadhaar, PAN, bank account numbers, passwords, or any government ID number. Profile fields are limited to the catalogue in `domain/fields.py`; reject unknown keys.
6. **Never log request bodies or profile answers.** Logs carry request_id, route, status code, and latency only. Error responses carry no stack traces.
7. **No paid API keys required.** Optional source adapters must be disabled by default and must never block startup or tests.
8. **Eligibility evaluation is stateless.** No user profile is persisted by `POST /api/v1/eligibility/evaluate`.
9. **Tracking tokens are shown once.** Only a SHA-256 hash of the token is stored.

## Coding conventions

- Source lives under `backend/src/claim_whats_yours/`. Tests live under `backend/tests/`. Do not add top-level modules.
- Layering: `api` calls `services`; `services` call `domain` and `db`; `domain` is pure (no SQLAlchemy, no FastAPI imports).
- Pydantic models for every request and response live in `schemas/`. ORM models live in `db/models.py` only.
- Public API identifiers are stable string codes (for example `PASS`, `FAIL`, `UNKNOWN`, `scheme_not_found`). Human text is never used for logic.
- Dates are ISO 8601 (`YYYY-MM-DD`) in UTC for timestamps. Store timestamps timezone-aware.
- Use `X-Request-ID` for correlation; generate one when absent.
- Keep functions small and typed. Avoid global mutable state outside `core/config.py`.

## Working rules for agents

- Read a file before editing it. Create new files only when the plan says so.
- After every edit run the linter for that file. Report what was changed; do not claim behaviour was tested unless tests were run.
- Do not restate specs in code comments; link to the spec section instead.
- Do not add dependencies without listing them in `backend/pyproject.toml`.
- Do not commit secrets, `.env` files, or local SQLite databases. Use `.env.example` for documented variables.

## Environments

- **Local:** SQLite file database, `uvicorn` dev server, no external services.
- **Production:** PostgreSQL via `DATABASE_URL`, containerised with a Dockerfile, migrations run with Alembic before the app starts.

Deployment details are in `docs/backend/ARCHITECTURE.md`, section "Deployment".

## Specs and source of truth

| Topic | Document |
|---|---|
| Components, layering, request flow, deployment | `docs/backend/ARCHITECTURE.md` |
| Endpoints, schemas, error codes, pagination | `docs/backend/API_CONTRACT.md` |

If code and spec disagree, the spec wins until it is explicitly changed. Update the spec in the same change as any contract change.

## Definition of done

- Behaviour matches the relevant spec section.
- No hard rule above is violated.
- `ruff check` and `ruff format --check` pass.
- Tests cover the new behaviour, including at least one negative case.
- No sensitive values appear in logs, fixtures, or examples.
