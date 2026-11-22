# Backend progress ledger

## Done
- Domain rules, geography, decisions, and profile fields catalogue.
- DB models and Alembic migration 0001.
- Services layer.
- Public, admin, tracking, and eligibility routes.
- Request-size middleware (64 KB limit).
- Validation and import scripts.
- Unit and integration tests: 209 passing as of the last run.

## Verified
- SQLite and PostgreSQL 16 migration (upgrade, downgrade).
- pytest suite.
- `ruff check` and `ruff format --check` on src, tests, alembic, scripts.

## Open
- No real scheme data loaded; zero published schemes.
- 422 detail item shapes differ between request and answer errors.
- docs/backend API_CONTRACT and ARCHITECTURE status names are fixed; spec not yet updated to match.
- Dockerfile and backend README not written.
- Ruff version range pinned loosely (`>=0.4,<1.0`).
- PostgreSQL integration tests not in repo.
