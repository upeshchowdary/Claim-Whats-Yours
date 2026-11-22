# API Contract — Claim What's Yours Backend

Status: Phase 1 specification. Architecture is in `ARCHITECTURE.md`; project rules are in `CLAUDE.md`.

## 1. Conventions

- Base path: `/api/v1`, except `/health/live` and `/health/ready`.
- Content type: `application/json; charset=utf-8`. Timestamps are ISO 8601 UTC. Dates are `YYYY-MM-DD`.
- Every response carries `X-Request-ID`. If the client sends one (max 64 chars, `[A-Za-z0-9-_]`), it is echoed; otherwise the server generates one.
- Sensitive headers: `X-Admin-Token`, `X-Tracking-Token`. Neither is echoed or logged.
- Request bodies are never logged.

### 1.1 Error envelope

```json
{"error": {"code": "SCHEME_NOT_FOUND", "message": "Scheme was not found.", "request_id": "b3f1c2d4"}}
```

- `code` is a stable uppercase string. Clients branch on `code`, never on `message`.
- `message` is English, for developers only. It is not localized.
- No stack traces, SQL, or internal paths are ever returned.

| HTTP | Used for | Example codes |
|---|---|---|
| 200 | successful read or action | — |
| 201 | resource created | — |
| 400 | malformed request (unparseable JSON, bad header format) | `BAD_REQUEST` |
| 401 | missing or invalid tracking token | `TRACKING_TOKEN_INVALID` |
| 403 | admin disabled or admin token invalid | `ADMIN_DISABLED`, `ADMIN_TOKEN_INVALID` |
| 404 | unknown resource | `SCHEME_NOT_FOUND`, `TRACKING_NOT_FOUND`, `VERSION_NOT_FOUND` |
| 409 | illegal state transition | `INVALID_STATE_TRANSITION`, `SCHEME_NOT_VALIDATED` |
| 422 | schema or business validation failed | `VALIDATION_ERROR`, `UNKNOWN_PROFILE_FIELD` |
| 429 | rate limit exceeded | `RATE_LIMITED` |
| 500 | unexpected failure | `INTERNAL_ERROR` |

401 is returned only for an invalid or missing tracking token. Missing admin token yields 403 (see section 6.1).

### 1.2 List envelope

```json
{"items": [], "page": 1, "page_size": 20, "total": 0}
```

## 2. Pagination and filter rules

- `page` is an integer `>= 1`, default `1`.
- `page_size` is an integer in `1..100`, default `20`. Out-of-range values return `422`.
- `total` is the count of all matching rows before paging.
- Filters combine with AND. Multi-valued filters are repeated query parameters (for example `category=health&category=education`) and combine with OR within the same parameter.
- Unknown query parameters return `422` with code `VALIDATION_ERROR`.
- Results are ordered by `scheme_id` ascending unless stated otherwise.

## 3. Health

### 3.1 `GET /health/live`

Process is up. No database access.

- Response `200`: `{"status": "ok"}`

### 3.2 `GET /health/ready`

Application can serve traffic. Performs one cheap database round trip.

- Response `200`: `{"status": "ready", "database": "ok"}`
- Response `503` is not part of the contract; a failed check returns `500` with code `INTERNAL_ERROR`.

## 4. Meta

### 4.1 `GET /api/v1/meta/jurisdictions`

Returns the geography catalogue: central, 28 states, 8 UTs, and districts that have at least one scheme.

- Query: `level` optional in `{central,state,ut,district}`; `parent_code` optional (for districts, the state code).
- Response `200`:

```json
{"items": [
  {"code": "IN", "name": "Central Government", "level": "central", "parent_code": null},
  {"code": "KA", "name": "Karnataka", "level": "state", "parent_code": "IN"}
], "page": 1, "page_size": 100, "total": 2}
```

Paged with the list envelope; `page_size` default `100` for this endpoint.

### 4.2 `GET /api/v1/meta/profile-fields`

Returns the profile field catalogue used by `answers` in eligibility. Only allowed fields are listed; sensitive identifiers never appear.

- Response `200`: list envelope of field descriptors:

```json
{"items": [
  {"key": "age", "type": "integer", "min": 0, "max": 120, "label_code": "field.age", "required": false},
  {"key": "state_code", "type": "enum_code", "enum": "state_or_ut", "label_code": "field.state_code", "required": false}
], "page": 1, "page_size": 100, "total": 2}
```

- `label_code` is a stable key for frontend translation.

## 5. Public schemes

### 5.1 `GET /api/v1/schemes`

Lists schemes. Only `published` schemes are visible unless `status` is given (see below).

- Query parameters:

| Name | Type | Rules |
|---|---|---|
| `q` | string | 1..100 chars; case-insensitive match on name and summary |
| `government_level` | enum, repeatable | `central`, `state`, `ut`, `district` |
| `state_code` | string | valid state or UT code |
| `district_code` | string | valid district code; requires `state_code` |
| `category` | string, repeatable | code from the category catalogue |
| `beneficiary_group` | string, repeatable | code such as `farmer`, `student`, `women` |
| `status` | enum | `published` (default) for public clients |
| `page` | int | `>= 1`, default `1` |
| `page_size` | int | `1..100`, default `20` |

- `status` other than `published` returns `403` for public use. Use the admin endpoints to view drafts.
- Response `200`: list envelope of scheme summaries.

Scheme summary item:

```json
{
  "scheme_id": "sch_0001",
  "name": "Example Farmer Support Scheme",
  "government_level": "state",
  "jurisdiction_code": "KA",
  "categories": ["agriculture"],
  "beneficiary_groups": ["farmer"],
  "status": "published",
  "verification_status": "verified",
  "version": 3,
  "last_verified_at": "2025-01-15"
}
```

Example request:

```
GET /api/v1/schemes?state_code=KA&category=agriculture&page=1&page_size=20
```

Status codes: `200`, `422`, `429`.

### 5.2 `GET /api/v1/schemes/{scheme_id}`

Returns full published detail.

- Path: `scheme_id` string, `1..64` chars.
- Response `200` adds: `description`, `criteria[]` (field, op, value, mandatory, source_refs), `document_checklist[]`, `application_guidance[]`, `source_refs[]`, `disclaimer`.
- Status codes: `200`, `404` (`SCHEME_NOT_FOUND`, also used for unpublished schemes), `429`.

Example response excerpt:

```json
{
  "scheme_id": "sch_0001",
  "name": "Example Farmer Support Scheme",
  "criteria": [
    {"criterion_id": "c1", "field": "land_holding_acres", "op": "lte", "value": 5, "mandatory": true, "source_refs": ["src_01"]}
  ],
  "document_checklist": [{"item_code": "land_record", "mandatory": true, "source_refs": ["src_01"]}],
  "source_refs": [{"source_id": "src_01", "title": "Official scheme notification", "url": "https://example.gov.in/scheme", "retrieved_on": "2025-01-15"}],
  "verification_status": "verified",
  "disclaimer": "Information is for guidance only and is not a guarantee of eligibility or benefit approval."
}
```

## 6. Eligibility

### 6.1 `POST /api/v1/eligibility/evaluate`

Stateless. Nothing from the request is stored.

Request body:

| Field | Type | Rules |
|---|---|---|
| `answers` | object | keys must be catalogue fields (section 4.2); values validated per field type; no sensitive identifiers |
| `filters.categories` | string[] | optional; category codes |
| `filters.government_levels` | string[] | optional; subset of `central,state,ut,district` |
| `locale` | string | optional, default `en`; BCP 47 short form such as `en`, `hi` |

Example request:

```json
{
  "answers": {"age": 34, "state_code": "KA", "occupation": "farmer", "land_holding_acres": 2.5},
  "filters": {"categories": ["agriculture"], "government_levels": ["state", "central"]},
  "locale": "en"
}
```

Response `200`:

| Field | Meaning |
|---|---|
| `request_id` | echo of `X-Request-ID` |
| `evaluation_date` | server date, `YYYY-MM-DD` |
| `results[]` | one per evaluated scheme (see below) |
| `coverage` | counts: `schemes_considered`, `excluded_by_geography`, `excluded_by_filters` |
| `disclaimer` | not a guarantee of eligibility or benefit approval |

Each `results[]` item:

- `scheme`: summary (as in 5.1)
- `decision`: `LIKELY_ELIGIBLE`, `NEEDS_MORE_INFORMATION`, or `NOT_LIKELY_ELIGIBLE`
- `criteria[]`: `{criterion_id, status (PASS|FAIL|UNKNOWN), explanation, source_refs, mandatory}`; `explanation` is a stable code plus English text, and `explanation_code` is the translatable key
- `missing_fields[]`: profile keys needed to decide
- `follow_up_questions[]`: `{field, question_code, input_type, options?}`
- `document_checklist[]`
- `application_guidance[]`: stable codes with source refs
- `source_refs[]`
- `verification_status`: `verified`, `pending`, or `unverified`
- `disclaimer`

Example response excerpt:

```json
{
  "request_id": "b3f1c2d4",
  "evaluation_date": "2025-06-01",
  "results": [{
    "scheme": {"scheme_id": "sch_0001", "name": "Example Farmer Support Scheme", "government_level": "state"},
    "decision": "NEEDS_MORE_INFORMATION",
    "criteria": [{"criterion_id": "c1", "status": "PASS", "explanation_code": "criterion.pass", "explanation": "Land holding is within the limit.", "source_refs": ["src_01"], "mandatory": true}],
    "missing_fields": ["annual_income"],
    "follow_up_questions": [{"field": "annual_income", "question_code": "q.annual_income", "input_type": "integer"}],
    "document_checklist": [{"item_code": "land_record", "mandatory": true}],
    "verification_status": "verified"
  }],
  "coverage": {"schemes_considered": 12, "excluded_by_geography": 4, "excluded_by_filters": 2},
  "disclaimer": "Information is for guidance only and is not a guarantee of eligibility or benefit approval."
}
```

Status codes: `200`, `400` (malformed JSON), `422` (`VALIDATION_ERROR`, `UNKNOWN_PROFILE_FIELD`), `429`, `500`.

## 7. Tracking

Tracking records hold only the scheme id, status, and dates. No profile answers are stored.

### 7.1 `POST /api/v1/tracking`

Creates a tracking record.

Request body: `{"scheme_id": "sch_0001", "status": "planned", "progress_date": "2025-06-01", "reminder_date": "2025-06-15"}`

- `status` default `planned`.
- `scheme_id` must reference a published scheme.
- Response `201`:

```json
{"tracking_id": "trk_7Hq2", "token": "fU2x...opaque...", "status": "planned", "scheme_id": "sch_0001", "created_at": "2025-06-01T09:30:00Z"}
```

- `token` is returned **only in this response**. It is never shown again. Store it client-side.
- Status codes: `201`, `400`, `422`, `429`.

### 7.2 `GET /api/v1/tracking/{tracking_id}`

- Header: `X-Tracking-Token` required.
- Response `200`: `{"tracking_id", "scheme_id", "status", "progress_date", "reminder_date", "updated_at"}`
- Status codes: `200`, `401` (`TRACKING_TOKEN_INVALID` when the header is missing or does not match), `404` (`TRACKING_NOT_FOUND`), `429`.

### 7.3 `PATCH /api/v1/tracking/{tracking_id}`

- Header: `X-Tracking-Token` required.
- Body (all optional, at least one required):

| Field | Rules |
|---|---|
| `status` | `planned`, `in_progress`, `submitted`, `approved`, `rejected`, `withdrawn` |
| `scheme_id` | must reference a published scheme |
| `progress_date` | `YYYY-MM-DD` |
| `reminder_date` | `YYYY-MM-DD`, not before `progress_date` when both given |

- Example: `{"status": "submitted", "progress_date": "2025-06-10"}`
- Response `200`: same shape as 7.2.
- Status codes: `200`, `400`, `401`, `404`, `409` (`INVALID_STATE_TRANSITION`, e.g. from `withdrawn`), `422`, `429`.

Allowed transitions: `planned` to `in_progress`, `submitted`, `withdrawn`; `in_progress` to `submitted`, `withdrawn`; `submitted` to `approved`, `rejected`, `withdrawn`; `rejected` to `in_progress`, `withdrawn`; `approved` and `withdrawn` are terminal.

## 8. Admin

All admin routes require `X-Admin-Token`. Comparison uses `hmac.compare_digest` against `ADMIN_API_TOKEN`.

- If `ADMIN_API_TOKEN` is empty, every admin route returns `403` with `ADMIN_DISABLED`.
- If the header is missing or wrong, the route returns `403` with `ADMIN_TOKEN_INVALID`.
- Admin routes are not listed in the public OpenAPI tag by default.

### 8.1 `POST /api/v1/admin/schemes/import`

Creates **draft** schemes and version 1 from supplied payloads. Never publishes.

- Body: `{"schemes": [{"name", "government_level", "jurisdiction_code", "categories", "beneficiary_groups", "criteria": [...], "document_checklist": [...], "application_guidance": [...], "sources": [{"source_id", "title", "url", "retrieved_on"}]}]}`
- Every scheme must include at least one source. Missing sources return `422`.
- Response `201`: `{"imported": 2, "scheme_ids": ["sch_0101", "sch_0102"], "status": "draft"}`
- Status codes: `201`, `400`, `403`, `422`, `429`.

### 8.2 `GET /api/v1/admin/schemes/review-queue`

- Query: `status` in `{draft,needs_review}` (default both), `page`, `page_size`.
- Response `200`: list envelope of scheme summaries with `status` and `validation_errors[]`.
- Status codes: `200`, `403`, `422`.

### 8.3 `POST /api/v1/admin/schemes/{scheme_id}/validate`

Checks required fields, source presence, operators, and jurisdiction codes. `draft` moves to `needs_review` on success.

- Response `200`: `{"scheme_id", "valid": true, "status": "needs_review", "errors": []}` or `{"valid": false, "status": "draft", "errors": [{"code", "path", "message"}]}`
- Status codes: `200`, `403`, `404`, `409`.

### 8.4 `POST /api/v1/admin/schemes/{scheme_id}/publish`

- Allowed only from `verified` with a passing validation for the current version.
- Request body: `{"actor": "reviewer-01", "note": "Checked against notification"}`. `actor` is a label, not personal data.
- Response `200`: `{"scheme_id", "status": "published", "version": 2}`
- Status codes: `200`, `403`, `404`, `409` (`SCHEME_NOT_VALIDATED`, `INVALID_STATE_TRANSITION`), `422`.

### 8.5 `POST /api/v1/admin/schemes/{scheme_id}/archive`

- Allowed from `published`. Removes the scheme from public listing and evaluation.
- Request body: `{"actor": "reviewer-01", "reason_code": "superseded"}`
- Response `200`: `{"scheme_id", "status": "archived"}`
- Status codes: `200`, `403`, `404`, `409`, `422`.

### 8.6 `GET /api/v1/admin/schemes/{scheme_id}/versions`

- Response `200`: list envelope of `{"version", "created_at", "status", "published_at", "actor"}`, newest first.
- Status codes: `200`, `403`, `404`.

## 9. Frontend integration notes

- Send `locale` on every evaluation. Render text from `label_code`, `question_code`, `explanation_code`, and `item_code` through your own translation table; use English `message` and `explanation` only as fallbacks.
- Branch on `error.code` and `status`, never on `message`.
- Keep the tracking token in memory or secure client storage. Send it only in `X-Tracking-Token`.
- Do not send Aadhaar, PAN, bank, or government ID numbers; the API rejects unknown answer keys.
- Show `disclaimer` wherever a decision or checklist is displayed.
- Read `X-Request-ID` from responses and include it in support reports.
- For lists, render `total` and use `page` and `page_size` from the response, not from your request.
- Expect `429` and back off; retry only after the `Retry-After` header value.
