# Data Model

Status: Phase 1 canonical reference.
Related: [API_CONTRACT.md](API_CONTRACT.md) (request/response shapes), [ARCHITECTURE.md](ARCHITECTURE.md) (services and storage layout), [RULE_ENGINE.md](RULE_ENGINE.md) (rule semantics), [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md) (sourcing, publication, freshness).

This document defines the tables, the scheme JSON format, and the profile field registry. It does not define endpoints or evaluation logic; those live in the documents above.

## 1. Design principles

- **No citizen profile table.** Profile values are supplied per request and processed in memory. They are never persisted. See section 7.
- **Stable identifiers.** Scheme IDs are stable strings and never reused. Slugs are unique and human-readable but may change; the ID is the join key.
- **Versioned content.** Every revision of a scheme writes an immutable row to `scheme_versions`.
- **Rules are data.** Eligibility rules are JSON documents validated against the rule grammar in RULE_ENGINE.md. No code is stored or executed.
- **Tracking is anonymous.** Tracking records hold a token hash, not the token.

## 2. Entity overview

```
jurisdictions 1---* scheme_jurisdictions *---1 schemes 1---* scheme_versions
                                                  |
                                                  1---* scheme_sources
                                                  |
                                                  0---* tracking_records
```

## 3. Tables

### 3.1 jurisdictions

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT, PK | `IN` for all-India; `IN-AP` for a state; district codes nest under their state (for example `IN-AP-GNT`). |
| `name` | TEXT, NOT NULL | Official English name. |
| `level` | TEXT enum | `country`, `state`, `ut`, `district`. |
| `parent_code` | TEXT, FK -> jurisdictions.code, NULL | NULL only for `IN`. Districts point to their state or UT. |

Constraints:
- 28 states and 8 Union Territories are seeded from an official reference list. Their codes are fixed for the life of the dataset.
- `level = district` requires a non-null `parent_code` whose level is `state` or `ut`.
- Codes are never reused after deletion.

### 3.2 schemes

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT, PK | Stable string, for example `sch_pm_kisan_2019`. Never reused. |
| `slug` | TEXT, UNIQUE, NOT NULL | URL-safe, lowercase. |
| `name` | TEXT, NOT NULL | Official name. |
| `summary` | TEXT, NOT NULL | Plain-language summary, max 500 characters. |
| `government_level` | TEXT enum | `central`, `state`, `ut`, `local`. |
| `scope` | TEXT enum | `all_india`, `state`, `ut`, `district`. Must agree with `scheme_jurisdictions`. |
| `record_status` | TEXT enum | `draft`, `needs_review`, `verified`, `published`, `archived`. Lifecycle in DATA_GOVERNANCE.md section 6. |
| `verification_status` | TEXT enum | `needs_review`, `verified`, `stale`. |
| `last_verified_at` | TIMESTAMP, NULL | Date a human reviewer confirmed sources. |
| `review_due_at` | TIMESTAMP, NULL | `last_verified_at + SCHEME_REVIEW_MAX_AGE_DAYS` (default 180). |
| `effective_from` | DATE, NULL | Start of legal or programme validity, if documented. |
| `effective_to` | DATE, NULL | End of validity. Past dates block publication. |
| `eligibility_rule` | JSON, NOT NULL | Rule tree per RULE_ENGINE.md. |
| `current_version` | INTEGER, NOT NULL | Points to the latest row in `scheme_versions`. Starts at 1. |
| `created_at` | TIMESTAMP, NOT NULL | |
| `updated_at` | TIMESTAMP, NOT NULL | |

Constraints:
- `effective_to >= effective_from` when both are set.
- `record_status = published` requires `verification_status = verified` and a non-expired `review_due_at`. Full gate in DATA_GOVERNANCE.md section 5.

### 3.3 scheme_versions

| Column | Type | Notes |
|---|---|---|
| `scheme_id` | TEXT, FK -> schemes.id | |
| `version` | INTEGER | Starts at 1, increments by 1. |
| `snapshot` | JSON, NOT NULL | Full scheme document in the format of section 4, as it stood at this version. |
| `created_at` | TIMESTAMP, NOT NULL | Write time. |
| `change_note` | TEXT, NOT NULL | Required, non-empty. Human-readable reason. |

Constraints:
- Primary key or unique index on `(scheme_id, version)`.
- Rows are append-only. Updates and deletes are prohibited at the application layer.

### 3.4 scheme_jurisdictions

| Column | Type | Notes |
|---|---|---|
| `scheme_id` | TEXT, FK -> schemes.id | |
| `jurisdiction_code` | TEXT, FK -> jurisdictions.code | |

Constraints:
- Primary key `(scheme_id, jurisdiction_code)`.
- If `scope = all_india`, the only allowed row is `IN`.
- If `scope = state`, every row is a state code; no district rows.
- If `scope = ut`, every row is a UT code.
- If `scope = district`, every row is a district code whose parent is in the same scheme.
- Mixed state and district rows, or mixed state and UT rows, are invalid unless the scheme JSON uses an explicit multi-scope declaration reviewed under DATA_GOVERNANCE.md.

### 3.5 scheme_sources

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT, PK | Composite key `(scheme_id, id)` is used in JSON; this surrogate key is internal. |
| `scheme_id` | TEXT, FK -> schemes.id | |
| `source_key` | TEXT, NOT NULL | Source id as referenced by rules, for example `src_1`. Unique per scheme. |
| `title` | TEXT, NOT NULL | |
| `publisher` | TEXT, NOT NULL | Issuing body. |
| `url` | TEXT, NOT NULL | Absolute HTTPS URL. |
| `source_type` | TEXT enum | Values from the hierarchy in DATA_GOVERNANCE.md section 2. |
| `official_status` | TEXT enum | `official`, `official_portal`, `discovery_only`, `supplementary`. Mirrors are not representable. |
| `access_date` | DATE, NOT NULL | Date the reviewer read the page. |
| `publication_date` | DATE, NULL | Date printed on the source, if any. |
| `section` | TEXT, NULL | Clause, paragraph, or page reference. |

### 3.6 tracking_records

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER / UUID, PK | Internal. Never exposed. |
| `tracking_id` | TEXT, UNIQUE, NOT NULL | Public identifier shown to the user. |
| `access_token_hash` | TEXT, NOT NULL | SHA-256 hex digest of the secret access token, generated with `secrets.token_urlsafe(32)`. The raw token is shown once and never stored. Verified with `hmac.compare_digest`. |
| `scheme_id` | TEXT, FK -> schemes.id, NULL | Nullable so a tracking record can outlive a withdrawn scheme. |
| `status` | TEXT enum | Application progress state, defined in API_CONTRACT.md. |
| `progress_date` | DATE, NULL | Date of last status change reported by the user. |
| `reminder_date` | DATE, NULL | Optional, user-chosen. |
| `created_at` | TIMESTAMP, NOT NULL | |
| `updated_at` | TIMESTAMP, NOT NULL | |

Tracking records contain no name, contact, or identity fields. Personal details are not required to track progress.

## 4. Scheme JSON format (version "1.0")

The JSON below is the canonical document stored in `schemes` (split across columns) and in `scheme_versions.snapshot` (whole). Field names are fixed.

```json
{
  "schema_version": "1.0",
  "id": "sch_example_001",
  "slug": "example-scheme",
  "name": "Example Scheme",
  "summary": "One-sentence plain-language description.",
  "government_level": "central",
  "jurisdictions": {
    "scope": "state",
    "state_codes": ["IN-AP", "IN-TG"],
    "district_codes": []
  },
  "categories": ["agriculture"],
  "beneficiary_groups": ["farmer"],
  "benefits": {
    "description": "Annual cash transfer in two instalments.",
    "amount_min_inr": 6000,
    "amount_max_inr": 6000,
    "frequency": "annual"
  },
  "eligibility_rule": { "all": [] },
  "self_check": [],
  "documents": [],
  "application_steps": [],
  "application_url": "https://example.gov.in/apply",
  "deadline": { "type": "rolling", "date": null, "notes": "" },
  "sources": [
    {
      "id": "src_1",
      "title": "Scheme guidelines",
      "publisher": "Ministry of Example",
      "url": "https://example.gov.in/guidelines.pdf",
      "source_type": "guideline",
      "official_status": "official",
      "access_date": "2025-01-10",
      "publication_date": "2024-04-01",
      "section": "Clause 4.2"
    }
  ],
  "verification": {
    "status": "verified",
    "last_verified_at": "2025-01-10",
    "review_due_at": "2025-07-09"
  },
  "effective_from": "2019-02-01",
  "effective_to": null,
  "record_status": "published"
}
```

Field rules:
- `jurisdictions.scope` is one of `all_india`, `state`, `ut`, `district`. `state_codes` and `district_codes` must match scope (see section 3.4).
- `categories`, `beneficiary_groups`: arrays of controlled-vocabulary strings. Vocabulary is versioned with the schema.
- `benefits.amount_min_inr` and `amount_max_inr`: integers >= 0, `min <= max`. Use `null` when not a cash amount; `description` then carries the detail.
- `self_check`: array of plain-language questions tied to a `criterion_id` in `eligibility_rule`. Used by the UI for user prompts; it must not introduce criteria absent from the rule.
- `documents`: array of strings describing documents an applicant typically needs. Informational only.
- `application_steps`: ordered array of objects `{ "order": int, "text": string }`. Orders must be contiguous from 1.
- `application_url`: absolute HTTPS URL on an official domain, or `null`.
- `deadline.type`: `rolling`, `fixed`, `none`. `fixed` requires `date`.
- `sources[].id`: unique within the scheme. Every `source_refs` entry in a rule must resolve to one of these ids.
- `verification.status`: `needs_review`, `verified`, `stale`. Date fields are ISO 8601.
- `record_status`: mirrors the column in section 3.2.

Validation of this document is performed by the publication gate and the validation script; see DATA_GOVERNANCE.md sections 5 and 7.

## 5. Identifiers and naming

| Entity | Pattern | Example |
|---|---|---|
| Scheme id | `sch_` + snake_case slug + optional year | `sch_pm_kisan_2019` |
| Scheme slug | lowercase, hyphenated | `pm-kisan` |
| Jurisdiction code | ISO-style `IN`, `IN-<STATE>`, `IN-<STATE>-<DISTRICT>` | `IN-MH-PUN` |
| Source id | `src_` + integer, unique per scheme | `src_1` |
| Criterion id | `c_` + snake_case | `c_age_min_18` |
| Tracking id | opaque, 12 characters, URL-safe | `CYX7K2M9QH4B` |

IDs are never reused. A withdrawn scheme keeps its id with `record_status = archived`.

## 6. Profile field registry

The registry lives at `data/profile_fields.json`. Rules may reference only fields present in this registry. Each entry has the following shape:

| Key | Meaning |
|---|---|
| `id` | Field identifier used in rules, e.g. `annual_household_income_inr`. |
| `type` | `int`, `number`, `string`, `enum`, `bool`. |
| `allowed_values` / `range` | Enum list, or `{min, max}` for numbers. |
| `label` | Display text. |
| `description` | Why the field exists; shown in the UI. |
| `required` | Whether the field must be supplied for a full result. |
| `sensitivity` | `low`, `medium`, `high`. Governs follow-up question ordering (RULE_ENGINE.md section 7). |
| `ask_only_when_relevant` | If true, never asked unless a rule on an applicable scheme references it. |
| `validation` | Rules such as `min`, `max`, `integer`, `nonnegative`. |

Registered fields (Phase 1):

| Field | Type / range | Sensitivity |
|---|---|---|
| `age_years` | int, 0-120 | low |
| `state_code` | enum of jurisdiction state/UT codes | low |
| `district_code` | enum of district codes under `state_code` | medium |
| `residence` | enum: `rural`, `urban` | low |
| `annual_household_income_inr` | int, >= 0 | high |
| `occupation` | enum (controlled list) | medium |
| `education_level` | enum (controlled list) | low |
| `is_student` | bool | low |
| `gender` | enum incl. `prefer_not_to_say` | high |
| `social_category` | enum (controlled list) | high |
| `disability_status` | enum (controlled list) | high |
| `family_size` | int, 1-50 | low |
| `marital_status` | enum (controlled list) | medium |
| `is_farmer` | bool | medium |
| `landholding_acres` | number, >= 0 | medium |
| `is_unorganised_worker` | bool | medium |

Forbidden fields. The following identifiers are never accepted in any request, stored record, rule, or log: Aadhaar number, PAN, bank account number, password, any government ID number, and phone number. Any request containing one of these keys is rejected with HTTP 422 and error code `FORBIDDEN_FIELD`. The rejection names the offending key only, never its value. The list is enforced by the validation script (DATA_GOVERNANCE.md section 7) and at request parsing (API_CONTRACT.md).

## 7. Data minimisation

- Profile input is held in request memory for the duration of one evaluation and then discarded.
- No table in section 3 has a column for profile values. The only user-linked data is `tracking_records`, which holds no profile values.
- Logs record scheme ids, decision enums, and counts. They do not record field values.
- High-sensitivity fields are requested only when a rule on an applicable scheme needs them (RULE_ENGINE.md section 7).

## 8. Migrations and versioning of the schema

- `schema_version` in scheme JSON gates parsing. Version `1.0` is the baseline in this document.
- Any change to a column or JSON key requires a migration file and a new schema version entry in this document.
- Existing `scheme_versions` snapshots are never rewritten. Old snapshots are read through the parser for their recorded `schema_version`.

## 9. Synthetic data

Synthetic records are permitted for tests only. They must carry `"synthetic": true` at the top level, live under `backend/tests/fixtures/`, and never appear in `data/schemes/`. Governance rules are in DATA_GOVERNANCE.md section 8.
