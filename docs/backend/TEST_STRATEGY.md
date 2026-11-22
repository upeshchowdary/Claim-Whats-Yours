# Test Strategy

Status: normative for how the backend is tested.

Endpoint contracts and error codes are defined in [API_CONTRACT.md](API_CONTRACT.md). Module layout, layering, and configuration are defined in [ARCHITECTURE.md](ARCHITECTURE.md). Privacy and security rules that tests must enforce are in [PRIVACY_SECURITY.md](PRIVACY_SECURITY.md). Decision logic is in RULE_ENGINE.md, and data governance is in DATA_GOVERNANCE.md. This document says what must be tested and where. It does not restate the contracts.

The host is Windows. Commands in this document are written for PowerShell. Paths in test code use `pathlib` so they work on Windows and POSIX alike.

## 1. Test pyramid and tools

- Unit tests make up the base. They exercise `domain/` directly with plain Python objects: no database, no HTTP, no FastAPI.
- Integration tests sit above. They drive the FastAPI application through `httpx` against an in-process app, backed by an SQLite file database created per test session.
- End-to-end browser tests are out of scope for this phase.
- Tools: `pytest` for all tests, `httpx` for HTTP clients, `ruff` for lint and format checks. `mypy` is optional and run only when configured in `backend/pyproject.toml`.
- Definition of done from CLAUDE.md applies: `ruff check` and `ruff format --check` pass, and every new behaviour has at least one negative test.
- No test requires a network connection, a paid API key, or an external service. The suite must pass with the network disabled.

## 2. Unit tests (`backend/tests/unit/`)

### 2.1 Rules engine (`test_rules.py`)

- Tri-state truth tables. Each of `all`, `any`, and `not` is tested against every combination of `TRUE`, `FALSE`, and `UNKNOWN` inputs, expressed as a parametrised table.
- `all` returns `UNKNOWN` when no input is `FALSE` and at least one is `UNKNOWN`. `any` returns `UNKNOWN` when no input is `TRUE` and at least one is `UNKNOWN`. `not` maps `UNKNOWN` to `UNKNOWN`.
- Each operator in the fixed operator set listed in RULE_ENGINE.md gets one row for a passing value, one for a failing value, and one for a missing value that yields `UNKNOWN`.
- Boundary cases for numeric comparisons:
  - `age_years` exactly at the minimum passes; one below fails; one above passes.
  - `landholding_acres` exactly at a maximum passes; a value one step above fails.
  - Income exactly at the ceiling passes; one rupee above fails.
- Unknown operators and malformed rule trees raise a validation error. They never fall through to a default result.
- Rule data is never passed to `eval`, `exec`, `compile`, or `ast` evaluation. A test asserts that rule text containing Python expressions is rejected as invalid data.

### 2.2 Geography (`test_geography.py`)

- Scope cases, each in a table: `all_india` matches any location; `state` matches only its state; `ut` matches only its union territory; `district` matches only its district within its state.
- Wrong state: a district scope in one state does not match a district with the same name in another state.
- Missing state: a state-scoped criterion evaluated with no state returns `UNKNOWN`, never `TRUE`.
- Invalid code: an unknown state or UT code is rejected at validation time with a stable error code.
- Registry completeness: the registry contains exactly 28 state entries and exactly 8 union territory entries. Codes are unique and non-empty. Every code appears once.
- A geographic mismatch never produces a positive decision, even when every other criterion passes.

### 2.3 Profile field validation (`test_profile_fields.py`)

- Table-driven checks for each catalogue field, including `age_years` and `landholding_acres`.
- `age_years`: integers in range are accepted; negative values, non-integers, and values above the configured maximum are rejected.
- `landholding_acres`: zero and positive decimals are accepted; negative values are rejected.
- Unknown keys yield `UNKNOWN_FIELD`. Forbidden keys from PRIVACY_SECURITY.md section 3 yield `FORBIDDEN_FIELD`, and each forbidden key is tested in both spellings (`bank_account`, `Bank-Account`).
- A declined optional field is accepted, and the criteria that depend on it evaluate to `UNKNOWN`.

### 2.4 Data validation (`test_data_validation.py`)

- The data-validation cases in section 6 each have a table row. Each row asserts the rejected or accepted state and the stable error or status code.

## 3. Integration tests (`backend/tests/integration/`)

- Each test module creates its own app instance and database. Tests do not share mutable state.
- Every response is checked for status code, error code where applicable, and the envelope shape defined in API_CONTRACT.md.

### 3.1 Health (`test_health.py`)

- The health endpoint returns success with no database write and no external call.
- It responds when `DATABASE_URL` points at a file that does not yet exist, and when no environment variables beyond defaults are set.

### 3.2 Schemes API (`test_schemes_api.py`)

- Filters are tested one at a time and in combination, using a table of query strings and expected scheme identifiers.
- Pagination boundaries: `page_size=0` returns 422; `page_size=1` succeeds; `page_size=100` succeeds; `page_size=101` returns 422.
- Only published schemes are listed. Draft, needs-review, verified-but-unpublished, and archived records never appear.
- An unknown scheme identifier returns the not-found shape defined in API_CONTRACT.md.

### 3.3 Eligibility API (`test_eligibility_api.py`)

- Each of the four decisions (`LIKELY_ELIGIBLE`, `NEEDS_MORE_INFORMATION`, `NOT_LIKELY_ELIGIBLE`, `VERIFICATION_REQUIRED`) is reached by at least one fixture from section 4.
- Running the same request twice returns byte-identical bodies, apart from `request_id`.
- The response for a scheme that is not published does not reveal its existence beyond the not-found shape.
- Evaluation writes nothing: row counts for every table are unchanged before and after the call.

### 3.4 Tracking API (`test_tracking_api.py`)

- Creation returns a token once. A second read of the same record does not return the token.
- A wrong token and a non-existent token produce identical responses.
- Only the SHA-256 hex digest of the token is stored. The test reads the raw row and asserts the plain token string appears nowhere in any column.
- Comparison uses `hmac.compare_digest`. A test patches the comparison function and asserts it is called.
- Tracking status changes accept only values in the fixed tracking set; anything else returns 422.

### 3.5 Admin security (`test_admin_security.py`)

- Table-driven: missing header, empty header, wrong header, and correct header against each admin endpoint.
- With `ADMIN_API_TOKEN` empty, every admin endpoint returns 403 `ADMIN_DISABLED`, including when the correct-looking header is sent.
- With a test-set token, the correct header succeeds and every wrong variant is rejected with the status defined in API_CONTRACT.md.
- Status changes by admins record the acting label and a UTC timestamp.

### 3.6 Privacy (`test_privacy.py`)

- Forbidden fields in a request body (each key from PRIVACY_SECURITY.md section 3, at top level and nested) return 422 `FORBIDDEN_FIELD`.
- The error response does not contain the submitted value.
- After an evaluation request with a full synthetic profile, no table in the database contains any profile answer. The test scans every text column for a sentinel value that was in the profile.
- Captured log output contains none of: the sentinel value, the tracking token, the `X-Admin-Token` value, or a request body.
- Forced internal errors return a 500 envelope with no traceback text, no exception class name, and no file path.
- CORS: a request from an origin not in `CORS_ORIGINS` receives no allow-origin header.
- Oversized body (above the configured limit) returns 413.

## 4. Synthetic profile fixtures (`backend/tests/fixtures/`)

- Each fixture is a JSON file, one scenario per file, with a top-level `"synthetic": true` key. The loader asserts the flag is present.
- Fixtures contain no real person, no real identifier, and no forbidden field.
- The fixtures are test scenarios for exercising code paths. They are not eligibility claims. Nothing in a fixture indicates that a real person would receive any benefit, and no test asserts a scheme outcome as a statement about the real world.
- Scenario files:
  - `student_urban.json`
  - `student_rural_hostel.json`
  - `farmer_smallholder.json`
  - `farmer_large_landholding.json`
  - `senior_citizen_alone.json`
  - `senior_citizen_with_family.json`
  - `unemployed_youth.json`
  - `salaried_middle_income.json`
  - `self_employed_artisan.json`
  - `women_led_household.json`
  - `person_with_disability.json`
  - `rural_household_large_family.json`
  - `urban_low_income.json`
  - `unorganised_worker_daily_wage.json`
  - `single_member_household.json`
  - `declined_optional_questions.json`
  - `incomplete_profile.json`
- Family size and income vary across scenarios, including the zero-income and income-at-ceiling boundaries.

## 5. Core reliability invariants

Each invariant has at least one parametrised test. Each test name starts with the invariant it checks.

- Unknown never becomes `PASS`. A criterion whose input is missing is `UNKNOWN` at every level of the rule tree.
- An unverified or stale scheme is never `LIKELY_ELIGIBLE`. Such a scheme yields `VERIFICATION_REQUIRED`.
- A failed mandatory criterion is never `LIKELY_ELIGIBLE`. It yields `NOT_LIKELY_ELIGIBLE`.
- A geographic mismatch is never a positive decision.
- The same input produces the same output on repeated calls, across process restarts, and regardless of dictionary key order in the request.
- The API works with zero external services. Tests run with outbound network blocked.
- Zero published schemes does not crash. Listing returns an empty page, and evaluation returns an empty result set with no error.

## 6. Data-validation tests (`test_data_validation.py`)

Each row is a parametrised case that imports or validates a synthetic scheme record and asserts the outcome.

- Missing source reference: rejected.
- Invalid source URL syntax: rejected. The test asserts no network call was attempted.
- Unverified record: loads as `draft` or `needs_review`, never `published`.
- Stale date (last verified date older than the freshness limit in DATA_GOVERNANCE.md): flagged, and never yields `LIKELY_ELIGIBLE`.
- Missing evidence for a criterion: rejected at validation time.
- Invalid rule syntax: rejected, with the rule rejected rather than partly loaded.
- Duplicate scheme identifier: rejected, and the existing record is untouched.
- Archived record: excluded from listing and evaluation.
- Invalid effective dates: an end date before a start date is rejected; a missing start date is stored as unknown, not guessed.

## 7. Acceptance criteria

Each row maps one acceptance criterion to the test file that proves it. Tests are table-driven and parametrised wherever the criterion has more than one input.

| # | Acceptance criterion | Source section | Test file(s) | Parametrised cases |
|---|---|---|---|---|
| 1 | All/any/not follow tri-state logic | 2.1 | `backend/tests/unit/test_rules.py` | Full truth tables |
| 2 | Each operator handles pass, fail, and missing inputs | 2.1 | `backend/tests/unit/test_rules.py` | One row per operator |
| 3 | Numeric boundaries are exact | 2.1 | `backend/tests/unit/test_rules.py` | Minimum, one below, one above, ceiling, ceiling plus one rupee |
| 4 | Rule text is never executed | 2.1 | `backend/tests/unit/test_rules.py` | Python-expression strings |
| 5 | Decision mapping returns the four canonical decisions | 3.3 | `backend/tests/unit/test_decisions.py`, `backend/tests/integration/test_eligibility_api.py` | One fixture per decision |
| 6 | Geographic scope matches correctly | 2.2 | `backend/tests/unit/test_geography.py` | Scope, wrong state, missing state, invalid code |
| 7 | Registry holds 28 states and 8 UTs | 2.2 | `backend/tests/unit/test_geography.py` | Registry count and uniqueness |
| 8 | Profile fields validate ranges and reject unknown keys | 2.3 | `backend/tests/unit/test_profile_fields.py` | Per field, valid and invalid |
| 9 | Forbidden keys are rejected in both spellings | 2.3, 3.6 | `backend/tests/unit/test_profile_fields.py`, `backend/tests/integration/test_privacy.py` | Each forbidden key |
| 10 | Scheme data validation rules hold | 2.4, 6 | `backend/tests/unit/test_data_validation.py` | One row per validation case |
| 11 | Health works with zero external services | 3.1 | `backend/tests/integration/test_health.py` | Fresh database, default environment |
| 12 | Scheme listing filters and paginates correctly | 3.2 | `backend/tests/integration/test_schemes_api.py` | Filter table; page_size 0, 1, 100, 101 |
| 13 | Only published schemes are listed | 3.2 | `backend/tests/integration/test_schemes_api.py` | Each non-published status |
| 14 | Evaluation is deterministic and stateless | 3.3 | `backend/tests/integration/test_eligibility_api.py` | Repeated call; row-count diff |
| 15 | Tracking token is shown once and only its hash is stored | 3.4 | `backend/tests/integration/test_tracking_api.py` | Create, re-read, raw-row scan |
| 16 | Wrong or unknown tracking token is rejected uniformly | 3.4 | `backend/tests/integration/test_tracking_api.py` | Wrong and unknown token |
| 17 | Admin endpoints reject missing, wrong, and disabled access | 3.5 | `backend/tests/integration/test_admin_security.py` | Header variants; empty token |
| 18 | Profile content is absent from logs and the database | 3.6 | `backend/tests/integration/test_privacy.py` | Sentinel scan of tables and logs |
| 19 | Errors carry no stack traces | 3.6 | `backend/tests/integration/test_privacy.py` | Forced 500 |
| 20 | CORS allows only listed origins | 3.6 | `backend/tests/integration/test_privacy.py` | Listed and unlisted origin |
| 21 | Unknown never becomes PASS; stale and mandatory-failed schemes never positive | 5 | `backend/tests/unit/test_decisions.py` | Invariant tables |
| 22 | Geographic mismatch is never positive | 5 | `backend/tests/unit/test_geography.py`, `backend/tests/unit/test_decisions.py` | Mismatch fixtures |
| 23 | Same input gives same output | 5 | `backend/tests/integration/test_eligibility_api.py` | Repeated and key-reordered requests |
| 24 | Zero published schemes does not crash | 5 | `backend/tests/integration/test_schemes_api.py`, `backend/tests/integration/test_eligibility_api.py` | Empty database |
