# Data Governance

1. Source hierarchy: (1) original central ministry or department pages; (2) state/UT government portals; (3) official guidelines, notifications, government orders, Gazette; (4) official application portals and FAQs; (5) myscheme.gov.in for discovery only; (6) data.gov.in supplementary only. Third-party mirrors and community datasets are never authoritative. Do not invent a myScheme API.
2. Source record fields: id, title, publisher, url (https only), source_type, official_status, access_date, publication_date (optional), section (optional).
3. Lifecycle: draft -> needs_review -> verified -> published -> archived. Import creates draft. Automatic transition to verified is forbidden.
4. Publication gate: valid schema, valid geographic scope, supported rule fields and operators, at least one official source, source_refs on every leaf criterion, verification status and last_verified_at present, https application_url if given, no amount or deadline without a source.
5. Verification states: needs_review, verified, stale. Verify via POST /api/v1/admin/schemes/{scheme_id}/verify with reviewer and verified_at.
6. Version history: a change to rules, benefits, sources or deadline of a verified or published scheme creates a scheme_versions row. Prior versions are never deleted.
7. Freshness: SCHEME_REVIEW_MAX_AGE_DAYS, default 180, internal threshold and not a legal expiry. Stale records are never shown as freshly verified and never yield LIKELY_ELIGIBLE.
8. Quality checks (scripts/validate_schemes.py): missing sources, non-https URLs, missing evidence refs, unsupported fields or operators, expired effective_to, stale verification, duplicate ids and slugs, invalid jurisdiction combinations, empty application_steps on published schemes, status mismatches.
9. Test-only records carry "synthetic": true and live only under backend/tests/fixtures/. Never in backend/data/schemes/. The backend must run with zero published schemes.
