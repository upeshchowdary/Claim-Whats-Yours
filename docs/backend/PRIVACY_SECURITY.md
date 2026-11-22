# Privacy and Security

Status: normative for privacy and security behaviour.

Endpoint shapes, error envelopes, status codes, and pagination are defined in [API_CONTRACT.md](API_CONTRACT.md). Components, layering, configuration, and deployment are defined in [ARCHITECTURE.md](ARCHITECTURE.md). This document states the rules those specs must respect. Where code and a spec disagree, the spec wins until it is explicitly changed.

Canonical names used here: record statuses `draft`, `needs_review`, `verified`, `published`, `archived`; decisions `LIKELY_ELIGIBLE`, `NEEDS_MORE_INFORMATION`, `NOT_LIKELY_ELIGIBLE`, `VERIFICATION_REQUIRED`; profile fields `age_years` and `landholding_acres`.

## 1. Data minimisation

- The platform collects only the answers defined in the profile field catalogue (`domain/fields.py`). Anything outside the catalogue is rejected, not stored.
- A profile field exists only because at least one scheme criterion reads it. A field with no reading criterion must not be added.
- Every profile question is optional unless a scheme needs it. A user who declines a question produces `UNKNOWN` for the criteria that depend on it. The platform never fills in a guessed value.
- The only catalogue content stored is scheme data, and every scheme record carries a source reference (see DATA_GOVERNANCE.md).
- No citizen documents are uploaded, stored, or parsed. Evaluation and browsing do not require sign-in.

## 2. Profile handling

- `POST /api/v1/eligibility/evaluate` is stateless. The request profile lives in memory for the duration of one request, is evaluated against published schemes, and is discarded when the response is sent.
- The evaluation path writes nothing to the database, cache, file system, or logs. No identifier is returned that could retrieve a past evaluation.
- The only persisted user-linked data is a tracking record. A tracking record holds the scheme reference, the status chosen by the user from the fixed tracking set, timestamps, and the hash of the tracking token. It holds no citizen profile and no profile answers.
- A client that wants to keep its answers keeps them on its own device. The server does not offer profile storage, profile export, or profile lookup.
- Caches, if added, may hold only scheme data. They must never key on or contain profile content.

## 3. Forbidden identifiers

Keys that identify a person or an account are refused at the request boundary. The forbidden set is:

- `aadhaar`
- `pan`
- `bank_account`
- `password`
- any government identity number, including voter ID, driving licence, and ration card numbers
- `phone`
- `email`

Rules:

- A forbidden key anywhere in a request body, at any nesting depth, is rejected with HTTP 422 and error code `FORBIDDEN_FIELD` (envelope per API_CONTRACT.md).
- The check runs before the body is bound to a model, so the value is never parsed, validated, or echoed.
- The error names the offending key only. It never repeats the value.
- Forbidden keys are checked before unknown keys, so a sensitive key is never reported as merely unknown.
- Matching is case-insensitive and ignores `-` and `_` separators, so `Bank-Account` and `bank_account` are treated alike.
- Unknown profile keys that are not forbidden are rejected with HTTP 422 and error code `UNKNOWN_FIELD`. Unknown keys are never silently dropped.
- Pydantic models for profile input use `extra="forbid"` as a second line of defence.

## 4. Authentication and authorisation

### 4.1 Admin endpoints

- Admin endpoints (import, validate, publish, archive; listed in API_CONTRACT.md) require the `X-Admin-Token` header.
- The presented value is compared with `ADMIN_API_TOKEN` using `hmac.compare_digest`. Plain `==` is never used for secrets.
- If `ADMIN_API_TOKEN` is empty or unset, every admin endpoint responds 403 `ADMIN_DISABLED`, whatever header is sent. An empty configured token never matches anything.
- A missing or wrong header on an enabled admin endpoint is rejected as unauthenticated, with the status and code defined in API_CONTRACT.md.
- No default credentials exist. No default token appears in code, configuration defaults, fixtures, migrations, documentation examples, or test data beyond values a test sets for itself.
- Admin status changes record the acting label supplied with the request and the UTC timestamp, as required by CLAUDE.md rule 4.

### 4.2 Tracking tokens

- At creation the server generates an opaque token with `secrets.token_urlsafe(32)` and returns it once, in the creation response.
- Only the SHA-256 hex digest of the token is stored. The digest is unsalted so that lookup is deterministic. The token carries 256 bits of randomness, so precomputed tables give an attacker nothing.
- On each use the server hashes the presented token and compares the digest with the stored digest using `hmac.compare_digest`.
- A wrong, expired, or unknown token receives the same response as a missing record. The API never reveals whether a token exists.
- Tokens are not logged, not placed in URLs, and not stored in plain text anywhere, including test snapshots. Transport and header placement follow API_CONTRACT.md.
- A lost token cannot be recovered. The user creates a new tracking record.

## 5. Secret handling

- Secrets come from environment variables only. `core/config.py` is the single reader of the environment.
- `.env` files are never committed. `.gitignore` excludes them, along with local SQLite database files.
- `.env.example` lists variable names with empty values. It holds placeholder names only, never a working secret.
- `DATABASE_URL` may embed credentials and is treated as a secret. It is never printed in full, including in startup messages.
- Secrets are never included in error responses, log lines, OpenAPI examples, or exception messages.
- Rotating `ADMIN_API_TOKEN` means changing the environment and restarting the service. Previously issued admin tokens stop working at restart.

## 6. Logging policy

- Each request produces one structured log record with: `request_id`, route template, HTTP method, status code, and latency in milliseconds.
- The route is logged as its template (for example `/api/v1/schemes/{scheme_id}`), never with the expanded path or query string.
- Never logged: request bodies, query values, profile answers, tracking tokens or their digests, and any header named `X-Admin-Token`, `Authorization`, or `Cookie`. Any header whose name contains `token`, `key`, or `secret` is also excluded.
- Error responses carry the stable error code, a human-readable message, and `request_id`. They carry no stack traces, no exception class names, no SQL text, and no file paths.
- An unexpected exception is logged with `request_id`, route, method, status 500, and latency only. The traceback is not written to logs, because it can contain request-derived values.
- Log retention and shipping are deployment concerns described in ARCHITECTURE.md. Logs are never used as a data store.

## 7. CORS

- Cross-origin browser requests are accepted only from origins listed in `CORS_ORIGINS`, a comma-separated environment variable.
- The default is an empty list, which means no cross-origin browser access.
- A wildcard origin is not accepted, and no wildcard is used as a default.
- Allowed methods and headers are the minimum the API needs. `X-Admin-Token` is allowed only through the same allow-list and never for unlisted origins.

## 8. Input safety

- Every request body is validated by a Pydantic model before any business logic runs. Validation failures return 422 with the error envelope from API_CONTRACT.md.
- The request body size limit defaults to 64 KB and is configurable through an environment variable named in ARCHITECTURE.md. Larger bodies are rejected with 413 before parsing.
- `page_size` must be between 1 and 100 inclusive. Values outside that range are rejected with 422. They are never silently clamped. Pagination shape is defined in API_CONTRACT.md.
- All database access uses bound parameters through SQLAlchemy. No SQL is built by string concatenation or interpolation of user input.
- Sort keys and filter keys come from fixed allow-lists. A client value that is not on the list is rejected.
- The server never fetches a URL supplied by a user or stored in a request. Source URLs on scheme records are validated for syntax only and are never requested at runtime.
- Source adapters that contact external government sites are disabled by default and run only inside import jobs, never on a request path.
- Free-text fields are length-limited and returned as JSON strings. The API never renders HTML.

## 9. Rate limiting

- Rate limiting is optional and disabled by default. It is enabled through configuration.
- When enabled, a client that exceeds the configured budget receives 429 with error code `RATE_LIMITED` and a `Retry-After` header.
- The limiter state is held in an object created at application startup. It is not module-level global state, and it stores no profile content.
- Enabling or disabling the limiter changes no response other than the 429 path.

## 10. Threat boundaries

| Threat | Boundary | Control |
|---|---|---|
| Citizen submits Aadhaar, PAN, phone, or email in a profile | HTTP request body into the API layer | Forbidden-key check before binding; 422 `FORBIDDEN_FIELD`; `extra="forbid"` |
| Unknown or extra profile keys smuggle data | HTTP request body into the API layer | 422 `UNKNOWN_FIELD`; no silent dropping |
| Oversized or malformed body exhausts resources | HTTP into the parser | 64 KB default limit; Pydantic validation; 413 |
| Guessing the admin token | Admin endpoints | `hmac.compare_digest`; no default credentials; empty token disables admin; optional rate limiting |
| Guessing a tracking token | Tracking endpoints | 256-bit random token; constant-time digest comparison; uniform not-found response |
| Database leak exposes live tracking tokens | Database at rest | Only SHA-256 digests stored; tokens cannot be recovered |
| Profile content leaks through logs | Logging sink | Logging policy in section 6; no bodies, answers, or secret headers |
| Stack traces reveal internals | Error handler to client | Generic error envelope; no traces, SQL, or paths |
| SQL injection through filters or sorting | Service to database | Bound parameters only; fixed allow-lists for keys |
| Server-side request forgery through source URLs | Import and source adapters | Syntax validation only; no runtime fetch; adapters off by default |
| Unverified scheme shown as eligible | Import and publish boundary | Imports create drafts only; explicit validate-then-publish; rules per RULE_ENGINE.md |
| Cross-origin abuse from a foreign site | Browser to API | `CORS_ORIGINS` allow-list; no wildcard |
| Secret committed to the repository | Source control | `.env` ignored; `.env.example` holds names only |

## 11. Third parties and runtime AI

- Profile answers are never sent to any third-party service. This includes analytics, error reporting, search, translation, CDNs, and messaging.
- No analytics or error-reporting SDK receives request content, headers, or response bodies.
- No runtime AI, LLM, or embedding call is made. Eligibility is deterministic rule data interpreted by a fixed evaluator with an explicit operator set (ARCHITECTURE.md, RULE_ENGINE.md).
- Any runtime dependency that transmits data outside the service requires a specification change before it is added to `backend/pyproject.toml`.
- Import-time source adapters may contact government sources, but they carry no profile data and are disabled unless an operator opts in.
