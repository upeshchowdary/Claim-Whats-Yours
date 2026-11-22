# Architecture — Claim What's Yours Backend

Status: Phase 1 specification. Rules for the project are in `CLAUDE.md`; endpoint details are in `API_CONTRACT.md`.

## 1. Style and boundaries

The backend is a single deployable **monolith** (one FastAPI process, one database). There are no separate services, queues, or workers in this phase.

Layers and allowed dependencies:

| Layer | Path | May import | Must not import |
|---|---|---|---|
| core | `core/` | stdlib, pydantic-settings | anything else in the package |
| domain | `domain/` | stdlib, `schemas.common` types | SQLAlchemy, FastAPI, services |
| db | `db/` | core, SQLAlchemy | domain, services, api |
| schemas | `schemas/` | pydantic, domain enums | db, services, api |
| services | `services/` | domain, db, schemas, core | api |
| api | `api/` | services, schemas, core | db models directly (except via services) |

`main.py` is the composition root: it builds the FastAPI app, registers the error handlers and middleware, and mounts the v1 router.

## 2. Package layout

```
backend/src/claim_whats_yours/
  main.py                  app factory, middleware, exception handlers
  core/
    config.py              Settings (env vars), cached accessor
    errors.py              AppError base + stable error codes
    logging.py             structured logs without bodies or answers
    security.py            admin token check (hmac.compare_digest), token hashing
  db/
    base.py                DeclarativeBase, naming conventions
    session.py             engine and session factory from DATABASE_URL
    models.py              ORM: schemes, scheme_versions, criteria, sources,
                           review_events, tracking_records
  schemas/
    common.py              Envelope[T], Pagination, ErrorBody, enums
    profile.py             answer payload model (validated against fields)
    scheme.py              scheme summary, detail, import payload
    eligibility.py         evaluate request/response
    tracking.py            tracking create/update/read models
  domain/
    fields.py              profile field catalogue (allowed keys, types, enums)
    geography.py           jurisdiction tree (India, states, UTs, districts)
    rules.py               declarative rule model + fixed evaluator
    decisions.py           scheme-level decision aggregation
  services/
    scheme_service.py      listing, detail, import drafts, validate, publish, archive
    eligibility_service.py orchestration of one evaluation (stateless)
    question_service.py    follow-up questions for missing fields
    source_service.py      source records, optional source adapters
    tracking_service.py    create, read, update tracking with token check
  api/
    deps.py                db session, request_id, admin guard, tracking guard
    v1/router.py           mounts endpoint routers under /api/v1
    v1/endpoints/
      health.py            /health/live, /health/ready
      meta.py              jurisdictions, profile fields
      schemes.py           public scheme listing and detail
      eligibility.py       evaluate
      tracking.py          create, read, update
      admin.py             import, review queue, validate, publish, archive, versions
```

Notification support is an abstract `NotificationAdapter` interface with a single **no-op** implementation. No email, SMS, or push provider is wired in this phase.

Source adapters (for pulling official scheme pages or feeds) are optional and isolated behind `source_service`. None are required. When disabled, the import path accepts only manually supplied payloads.

## 3. Domain model

- **Jurisdiction**: a node in the geography tree. Levels are `central`, `state`, `ut`, `district`. States use the 28-state code list; UTs use the 8-UT code list. Codes are stable strings.
- **Scheme**: identity, government level, jurisdiction, category, beneficiary groups, and a current status. Statuses: `draft`, `needs_review`, `verified`, `published`, `archived`.
- **SchemeVersion**: immutable snapshot created at each import or edit. Publishing points the scheme at one version.
- **Criterion**: one declarative condition from a version (field, operator, value, mandatory flag, source_refs).
- **Source**: a reference to an official document or page (title, URL, retrieved_on). Every criterion and document item links to at least one source.
- **Audit entry**: a version and audit record of who and when for validate, publish, and archive actions (actor label, action, timestamp, version).
- **TrackingRecord**: tracking_id, scheme_id, status, progress_date, reminder_date, token_hash. No profile data is stored.

## 4. Rules engine

- Each criterion has `field`, `op`, `value`, `mandatory`.
- Allowed operators: `eq`, `ne`, `in`, `not_in`, `gte`, `lte`, `between`, `is_true`, `is_false`.
- The evaluator is a fixed function over these operators. Input is a validated answer map.
- Result per criterion: `PASS`, `FAIL`, or `UNKNOWN` (field absent or not answerable). Never guess a missing value.
- Mandatory criteria failing yields a scheme decision of `NOT_LIKELY_ELIGIBLE`. Any mandatory `UNKNOWN` yields `NEEDS_MORE_INFORMATION`. All mandatory `PASS` yields `LIKELY_ELIGIBLE`. Decisions are guidance, not a determination.
- Rule text is never executed. Rules are stored as structured data only.

## 5. Eligibility request flow

`POST /api/v1/eligibility/evaluate` runs this sequence. No step writes profile data.

1. **Assign request id.** Middleware reads or creates `X-Request-ID`.
2. **Validate profile.** Pydantic validates `answers` against the field catalogue; unknown keys are rejected with `422`.
3. **Validate filters and locale.** `filters.categories`, `filters.government_levels`, and `locale` are checked against allowed values.
4. **Find published schemes.** Query only schemes with status `published` and a current version. Apply category and level filters.
5. **Geography.** Check the scheme's jurisdiction against `state_code` and `district_code` from answers. Out-of-jurisdiction schemes are excluded and counted in coverage metadata.
6. **Rules.** Evaluate each criterion of the current version with the fixed evaluator.
7. **Decision.** Aggregate criteria into a scheme decision (section 4).
8. **Questions.** For `UNKNOWN` mandatory fields, `question_service` returns follow-up questions from the field catalogue, ordered by criterion priority.
9. **Checklist and guidance.** Attach the document checklist and application guidance from the version. Items without a source reference are not returned.
10. **Respond.** Build the envelope with `request_id`, `evaluation_date`, per-scheme results, coverage metadata, and the disclaimer.

Steps 4 to 9 run per scheme and are independent; results are sorted by decision rank then scheme_id for determinism.

## 6. Scheme lifecycle

1. **Import** (`POST /admin/schemes/import`): creates a `draft` scheme and version. Source records are required. Nothing becomes public.
2. **Review queue** lists drafts and `needs_review` items.
3. **Validate** checks required fields, source presence, operator validity, and jurisdiction codes. It moves `draft` to `needs_review` on success and returns the list of errors on failure. **Verify** (`POST /api/v1/admin/schemes/{scheme_id}/verify`) moves `needs_review` to `verified`.
4. **Publish** is allowed only from `verified` with a passing validation. It sets the scheme to `published` and records a version and audit record of who and when.
5. **Archive** removes a scheme from public listing and evaluation while keeping history.
6. **Versions** lists all immutable snapshots.

Publishing is never triggered by import, by a scheduled job, or by an external source.

## 7. Security and privacy

- Admin routes require `X-Admin-Token`, compared with `hmac.compare_digest` to `ADMIN_API_TOKEN`. If the variable is empty, admin routes return `403`.
- Tracking routes require `X-Tracking-Token`. Tokens are random, shown once on create, and stored as SHA-256 hashes.
- No Aadhaar, PAN, bank, password, or government ID fields exist in the catalogue.
- Request bodies and profile answers are never logged. Logs record request_id, method, route template, status, and duration.
- Error responses use the stable envelope in `API_CONTRACT.md` and never include stack traces.
- Rate limiting (`429`) is applied per client on evaluation and tracking routes using an in-process limiter configured by env.

## 8. Configuration

Settings are read from environment variables (optionally a local `.env` that is not committed).

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./claim_whats_yours.db` |
| `ADMIN_API_TOKEN` | admin auth; empty disables admin | empty |
| `LOG_LEVEL` | logging level | `INFO` |
| `RATE_LIMIT_PER_MINUTE` | per-client limit on limited routes | `60` |
| `CORS_ORIGINS` | comma-separated allowed origins | empty |

## 9. Deployment

### Local (SQLite)

1. Create a virtual environment and install `backend/` with its dev extras.
2. Run `alembic upgrade head` (default SQLite file).
3. Start with `uvicorn claim_whats_yours.main:app --reload` from `backend/src`.
4. Check `GET /health/ready`.

### Production (PostgreSQL, Docker)

1. Build the image from `backend/Dockerfile` (Python 3.12 slim base, non-root user, no dev extras).
2. Set `DATABASE_URL` to a `postgresql+psycopg://` URL and set `ADMIN_API_TOKEN` from a secret store.
3. Run `alembic upgrade head` as a one-off job before rolling the app container.
4. Run uvicorn with multiple workers behind a reverse proxy that terminates TLS.
5. Use `/health/live` for liveness and `/health/ready` for readiness (readiness checks a DB round trip).

## 10. Testing strategy

- Unit tests for `domain/` (operators, decisions, geography) with no database.
- Service tests against an in-memory SQLite database.
- API tests with httpx against the app factory, covering success, validation errors, auth failures, and rate limits.
- Every hard rule in `CLAUDE.md` has at least one test that proves the negative case.

## 11. Non-goals for this phase

- No user accounts or login.
- No persistence of eligibility inputs.
- No automated scraping as a required path.
- No AI-generated content of any kind.
