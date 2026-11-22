# Rule Engine

Status: Phase 1 canonical reference.
Related: [DATA_MODEL.md](DATA_MODEL.md) (rule storage, profile fields), [API_CONTRACT.md](API_CONTRACT.md) (evaluation endpoint and response shape), [ARCHITECTURE.md](ARCHITECTURE.md) (where evaluation runs), [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md) (sources and verification).

The rule engine decides, for one scheme and one profile, whether the scheme is applicable, which criteria pass, fail, or cannot be determined, and which decision category applies. It is a closed interpreter over a fixed JSON grammar. It never evaluates strings as code.

## 1. Principles

- **Declarative.** Rules are JSON trees. No `eval`, `exec`, template expansion, or dynamic import is used anywhere in evaluation.
- **Closed vocabulary.** Only the groups, leaf fields, and operators in this document are accepted. Anything else is an unsupported construct.
- **Tri-state.** Every node yields `PASS`, `FAIL`, or `UNKNOWN`. There is no fourth state and no numeric confidence score.
- **Unknown is not failure.** Missing data never causes a rejection. It produces `UNKNOWN` and, where useful, a follow-up question.
- **Auditable.** Every leaf carries an explanation and source references so a result can be traced to official text.

## 2. Grammar

A rule node is exactly one of:

```json
{ "all": [ node, ... ] }
{ "any": [ node, ... ] }
{ "not": node }
leaf
```

A group must contain at least one child. `not` takes exactly one child. Nesting depth is capped at 6. A rule with more than 60 leaves is rejected by the validation script.

### 2.1 Leaf

```json
{
  "criterion_id": "c_age_min_18",
  "field": "age_years",
  "operator": "gte",
  "value": 18,
  "mandatory": true,
  "explanation": "Applicant must be at least 18 years old on the date of application.",
  "source_refs": ["src_1"]
}
```

| Key | Required | Rule |
|---|---|---|
| `criterion_id` | yes | Unique within the scheme. Pattern `c_<snake_case>`. |
| `field` | yes | Must exist in `data/profile_fields.json`. |
| `operator` | yes | One of the operators in section 3. |
| `value` | depends | Required for all operators except `exists`. Type must match the field. |
| `mandatory` | yes | Boolean. See section 5. |
| `explanation` | yes | Plain-language text shown to the user. |
| `source_refs` | yes | Non-empty array of source ids defined in the scheme's `sources`. |

## 3. Operators

| Operator | Applies to field types | Value type | Semantics |
|---|---|---|---|
| `eq` | all | scalar | Equal. |
| `ne` | all | scalar | Not equal. |
| `in` | enum, string | array | Field value is one of the listed values. |
| `not_in` | enum, string | array | Field value is none of the listed values. |
| `gt` | int, number | number | Strictly greater. |
| `gte` | int, number | number | Greater or equal. |
| `lt` | int, number | number | Strictly less. |
| `lte` | int, number | number | Less or equal. |
| `contains` | array-valued fields | scalar | Array field includes the value. |
| `exists` | all | none | Field has a non-null, non-absent value that is not `prefer_not_to_say`. |

Any operator or field outside this table is an unsupported construct (section 9).

## 4. Tri-state evaluation

### 4.1 Leaf

For a leaf with field `f`, operator `op`, and value `v`:

1. If the profile does not contain `f`, or the value is `null`, or the value is the sentinel `"prefer_not_to_say"`, the result is `UNKNOWN`.
2. Otherwise apply `op`. True gives `PASS`; false gives `FAIL`.

For `exists`, a present non-null value (other than `prefer_not_to_say`) gives `PASS`. A missing, null, or declined value gives `UNKNOWN`, not `FAIL`, because the engine cannot distinguish "does not have" from "did not say". `exists` is therefore only useful for fields the user answers explicitly.

### 4.2 Groups and negation

| Node | Result rule |
|---|---|
| `all` | Any child `FAIL` -> `FAIL`. All children `PASS` -> `PASS`. Otherwise -> `UNKNOWN`. |
| `any` | Any child `PASS` -> `PASS`. All children `FAIL` -> `FAIL`. Otherwise -> `UNKNOWN`. |
| `not` | `PASS` becomes `FAIL`, `FAIL` becomes `PASS`, `UNKNOWN` stays `UNKNOWN`. |

### 4.3 Worked examples

Profile: `age_years = 17`, `annual_household_income_inr` absent, `is_farmer = true`.

| Expression | Evaluation | Result |
|---|---|---|
| `age_years gte 18` | 17 >= 18 is false | FAIL |
| `income lte 200000` | income absent | UNKNOWN |
| `all [age gte 18, income lte 200000]` | one FAIL | FAIL |
| `all [income lte 200000, is_farmer eq true]` | one UNKNOWN, none FAIL | UNKNOWN |
| `any [age gte 18, is_farmer eq true]` | second PASS | PASS |
| `any [age gte 18, income lte 200000]` | first FAIL, second UNKNOWN | UNKNOWN |
| `not [income lte 200000]` | UNKNOWN stays | UNKNOWN |
| `not [age gte 18]` | FAIL becomes PASS | PASS |
| `all [not [age gte 18], is_farmer eq true]` | PASS and PASS | PASS |

## 5. Mandatory criteria and decisions

`mandatory` marks a criterion whose failure excludes the user from likely eligibility. Non-mandatory criteria contribute explanations and follow-up questions but do not change the decision category.

Decision categories:

| Decision | Condition (evaluated in order) |
|---|---|
| `VERIFICATION_REQUIRED` | The scheme's sources are incomplete, its `verification.status` is not `verified`, or `review_due_at` is in the past (stale). Checked first and overrides all others. |
| `NOT_LIKELY_ELIGIBLE` | Geography is `PASS` and at least one mandatory leaf is `FAIL`. |
| `LIKELY_ELIGIBLE` | Geography is `PASS`, every mandatory leaf is `PASS`, sources are verified and current, and no mandatory self-check is unresolved. |
| `NEEDS_MORE_INFORMATION` | Otherwise: no mandatory `FAIL`, and at least one mandatory `UNKNOWN`. |

Invariants (must hold for every evaluation; tested):
- A scheme that is unverified or stale is never `LIKELY_ELIGIBLE`.
- A scheme with a mandatory `FAIL` is never `LIKELY_ELIGIBLE`.
- A scheme whose geography is `FAIL` is not applicable and produces no decision (section 6).
- The engine never emits a decision without at least one explanation entry per evaluated leaf.

Non-mandatory `FAIL` results are reported as "does not match this criterion" but do not change the decision; `NOT_LIKELY_ELIGIBLE` requires a mandatory failure.

## 6. Geography

Geography is evaluated before rules and is a separate gate. It uses `jurisdictions` from the scheme and `state_code` / `district_code` from the profile.

| Scheme scope | Profile input | Result |
|---|---|---|
| `all_india` | any | PASS |
| `state` | `state_code` in `state_codes` | PASS |
| `state` | `state_code` present, not in `state_codes` | FAIL (scheme not applicable) |
| `state` | `state_code` absent | UNKNOWN |
| `ut` | same as `state`, against `state_codes` holding UT codes | same as `state` |
| `district` | `district_code` in `district_codes` | PASS |
| `district` | `district_code` present, not listed | FAIL (not applicable) |
| `district` | `district_code` absent | UNKNOWN |

Rules:
- A geography `FAIL` removes the scheme from results. It is listed only in the count of excluded schemes, not individually.
- A geography `UNKNOWN` lets the scheme be evaluated but caps the decision at `NEEDS_MORE_INFORMATION`. `state_code` is then a follow-up question.
- A profile with `district_code` but no `state_code` is rejected with a validation error, because the district cannot be placed.

Worked example: scheme scope `state`, `state_codes = ["IN-AP"]`. Profile `state_code = IN-TG`: geography FAIL, scheme excluded. Profile without `state_code`: geography UNKNOWN, criteria still evaluated, decision cannot exceed `NEEDS_MORE_INFORMATION`.

## 7. Explanations and follow-up questions

### 7.1 Explanation object

Each evaluated scheme returns an explanation with these parts:

- `criteria`: list of `{criterion_id, result, mandatory, explanation, source_refs}`.
- `missing_fields`: deduplicated field ids behind `UNKNOWN` leaves.
- `passed`, `failed`, `unknown`: counts by result.
- `source_refs`: deduplicated source ids used in the evaluation.
- `verification_needed`: boolean, plus a reason code (`stale`, `unverified`, `incomplete_sources`, `disputed`).

The response shape is defined in API_CONTRACT.md. The engine produces the content; the API layer only serialises it.

### 7.2 Follow-up questions

Generated only from leaves that are `UNKNOWN`, across all applicable schemes:

1. Collect field ids from `UNKNOWN` leaves of applicable schemes. Deduplicate.
2. Rank each field by the number of schemes it would unlock, i.e. schemes where resolving the field could move the decision toward `LIKELY_ELIGIBLE`. Ties break by fewer `UNKNOWN` leaves remaining.
3. Each question carries: `field`, `label`, `permitted_values` (or range), and `why_needed` (the explanation of the first leaf that needs it).
4. Sensitive fields (`sensitivity = high`) are included only when a rule on an applicable scheme references them as a mandatory leaf. They are never added for convenience.
5. Fields with `ask_only_when_relevant = true` are never asked otherwise.

Question limit per response is configurable; default 5.

## 8. Publication-time validation

Before a rule can be published (DATA_GOVERNANCE.md section 5):

- Every `field` exists in the registry.
- Every `operator` is in section 3 and is compatible with the field type.
- Every `value` matches the field type and range.
- Every `source_refs` entry resolves in the scheme's `sources`.
- Every leaf has a non-empty explanation.
- Unique `criterion_id` across the scheme.
- Structural limits (depth, leaf count, non-empty groups) hold.

Any violation blocks publication. Unsupported fields or operators are a hard failure, not a warning.

## 9. Unsupported constructs

An unsupported construct is any field not in the registry, operator not in section 3, group key other than `all`, `any`, `not`, or a leaf key set outside section 2.1. Effects:

- At publication time: blocks publication; the record stays in `draft` or `needs_review`.
- At evaluation time (should not occur for published records): the scheme is excluded and an internal error is logged with the scheme id and the offending key. The user sees `VERIFICATION_REQUIRED` for that scheme only.

## 10. Edge cases

**Age boundary.** Rule `age_years gte 18`. Profile age 18: PASS. Age 17: FAIL. Age null: UNKNOWN. The engine does not compute age from date of birth; date of birth is not a profile field.

**Income ceiling at exact value.** Rule `annual_household_income_inr lte 300000`. Income exactly 300000: PASS. Income 300001: FAIL. Income 0: PASS (valid, nonnegative). Income absent: UNKNOWN, and the follow-up question for income is high-sensitivity, so it is asked only if this rule is mandatory on an applicable scheme.

**AND with unknown.** `all [age gte 18, income lte 300000]`, age 25, income unknown: UNKNOWN, decision `NEEDS_MORE_INFORMATION` (if otherwise eligible). Age 15: FAIL regardless of income, so the scheme cannot be `LIKELY_ELIGIBLE`; the unknown income is still listed as missing but not asked, because it cannot change the outcome.

**OR with unknown.** `any [is_farmer eq true, landholding_acres gt 0]`, `is_farmer = false`, landholding unknown: UNKNOWN. Landholding is asked. If the user later supplies 1.5 acres, the second leaf PASSes and the group PASSes.

**NOT with unknown.** `not [social_category in ["general"]]`, social category unknown: UNKNOWN, not PASS. Negation never converts an unknown into eligibility.

**Prefer not to say.** `gender = prefer_not_to_say` is treated as absent for any rule. A rule that depends on gender yields `UNKNOWN` and `NEEDS_MORE_INFORMATION` cannot be resolved by the user; the explanation says so, and the decision does not go to `LIKELY_ELIGIBLE` on that basis.

**Non-mandatory fail.** A failed non-mandatory leaf alongside all mandatory PASS yields `LIKELY_ELIGIBLE` with the failed leaf listed for transparency.

**Stale source with all PASS.** Every criterion passes but `review_due_at` has passed: `VERIFICATION_REQUIRED`. Freshness overrides eligibility.

**Empty applicable set.** If every scheme is geography FAIL, the response contains zero evaluated schemes and a count of excluded schemes. This is not an error.

## 11. Performance and determinism

- Evaluation is pure: same rules, same sources state, same profile, same output. No clock reads except the staleness check, which takes the request time as an input parameter so results are reproducible in tests.
- Rule trees are compiled once per scheme version into an in-memory form and cached by `(scheme_id, version)`.
- Evaluation of a single scheme is bounded by the leaf cap (60). Batch evaluation is linear in the number of applicable schemes.

## 12. Testing requirements

The rule engine test suite must cover at minimum: each operator for each field type; every row of the tri-state tables in section 4; every geography row in section 6; each decision invariant in section 5; each edge case in section 10; and rejection of each unsupported construct in section 9. Test fixtures are synthetic and follow DATA_GOVERNANCE.md section 8.
