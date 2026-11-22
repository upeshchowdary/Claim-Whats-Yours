# API Integration

Backend source of truth: `docs/backend/API_CONTRACT.md`. This file records what the frontend currently uses and where code and contract disagree.

## Client

- Client: `frontend/src/lib/api/client.ts`.
- Error mapping: `frontend/src/lib/api/errors.ts`.
- Base URL: `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Implemented backend endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health/live` | Liveness |
| GET | `/health/ready` | Readiness; body differs from contract (see below) |
| GET | `/api/v1/schemes` | Paged: `{items, page, page_size, total}` |
| GET | `/api/v1/schemes/{scheme_id}` | Single scheme |

Not implemented in code (contract only): eligibility, tracking, categories, admin.

## Frontend data

- Data fetching: @tanstack/react-query.
- Pages using live data: none yet. Scheme list and detail pages are placeholders.

## Demo fixture rule

- `VITE_USE_FIXTURES` switches to fixture data for demo and offline work.
- Fixtures must come from imported source records with a source reference. No scheme values are invented.
- Fixture-backed screens must not present demo data as real scheme data.

## Mismatches: contract vs backend code

1. `/health/ready` body: code returns `{"status":"ok"}`; contract says `{"status":"ready","database":"ok"}`.
2. Repeatable filters `government_level`, `category`, `beneficiary_group`: contract says repeatable; code accepts a single value.
3. Profile field names: differ between the contract and `backend/data/profile_fields.json`.

Resolution: the spec wins until changed explicitly (per CLAUDE.md). Do not code the frontend against the mismatched fields until resolved.

## Privacy rules for the client

- Do not collect Aadhaar, PAN, bank account numbers, passwords or other government ID numbers.
- Do not log request bodies or profile answers.
- Eligibility evaluation is stateless; the client must not persist profile answers server-side.
