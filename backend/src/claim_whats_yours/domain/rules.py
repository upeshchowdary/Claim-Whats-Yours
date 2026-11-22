"""Tri-state evaluator for declarative eligibility rules. Pure and deterministic."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from claim_whats_yours.domain.fields import load_registry


class Tri(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


SUPPORTED_OPERATORS: frozenset[str] = frozenset(
    {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "contains", "exists"}
)
GROUP_KEYS: frozenset[str] = frozenset({"all", "any", "not"})
LEAF_KEYS: frozenset[str] = frozenset(
    {"criterion_id", "field", "operator", "value", "mandatory", "explanation", "source_refs"}
)
ORDERING_OPERATORS: frozenset[str] = frozenset({"gt", "gte", "lt", "lte"})
PREFER_NOT_TO_SAY = "prefer_not_to_say"

MAX_RULE_DEPTH: int = 6
"""Maximum nesting depth of a rule tree. The root node is depth 1 and each group level adds one,
so a bare leaf is depth 1 and all[leaf] is depth 2. Deeper trees fail with rule_too_deep."""
MAX_RULE_LEAVES: int = 50
"""Maximum number of leaf criteria in one rule tree. More fail with too_many_leaves."""

_NUMERIC_OPERATORS: frozenset[str] = frozenset(
    {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "exists"}
)
_CATEGORY_OPERATORS: frozenset[str] = frozenset({"eq", "ne", "in", "not_in", "exists"})
# Operators allowed per catalogue field type. Ordering needs numbers; contains needs strings.
OPERATORS_BY_FIELD_TYPE: dict[str, frozenset[str]] = {
    "int": _NUMERIC_OPERATORS,
    "number": _NUMERIC_OPERATORS,
    "bool": _CATEGORY_OPERATORS,
    "enum": _CATEGORY_OPERATORS,
    "string": _CATEGORY_OPERATORS | {"contains"},
}

_PREFIX: dict[Tri, str] = {Tri.PASS: "Passed", Tri.FAIL: "Failed", Tri.UNKNOWN: "Unknown"}


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str | None
    status: Tri
    mandatory: bool
    explanation: str
    source_refs: tuple[str, ...]
    children: tuple[CriterionResult, ...]


# ---------------------------------------------------------------- validation


@dataclass(frozen=True)
class RuleError:
    """One structured validation error. path is JSON-path-like, for example "$.all[0].value"."""

    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def check_rule(node: Any) -> list[RuleError]:
    """Return structured validation errors for a rule tree. An empty list means valid.

    Never raises. Stable codes: invalid_node, unsupported_group, invalid_attribute, unknown_key,
    unknown_field, invalid_operator, missing_value, invalid_operand_type, unknown_value,
    rule_too_deep, too_many_leaves.
    """
    errors: list[RuleError] = []
    leaf_count = [0]
    _check_node(node, "$", 1, errors, leaf_count)
    if leaf_count[0] > MAX_RULE_LEAVES:
        errors.append(
            RuleError("too_many_leaves", "$", f"rule has more than {MAX_RULE_LEAVES} leaves")
        )
    return errors


def validate_rule(node: Any) -> list[str]:
    """Return one message per validation error, as "path: message". Never raises.

    Text form of check_rule, kept for callers that only need strings.
    """
    return [f"{error.path}: {error.message}" for error in check_rule(node)]


def _check_node(
    node: Any, path: str, depth: int, errors: list[RuleError], leaf_count: list[int]
) -> None:
    if depth > MAX_RULE_DEPTH:
        errors.append(
            RuleError("rule_too_deep", path, f"rule nests deeper than {MAX_RULE_DEPTH} levels")
        )
        return
    if not isinstance(node, dict):
        errors.append(RuleError("invalid_node", path, "node must be an object"))
        return
    group_keys = sorted(k for k in node if k in GROUP_KEYS)
    if len(group_keys) > 1:
        errors.append(
            RuleError(
                "unsupported_group",
                path,
                f"node has more than one group key: {', '.join(group_keys)}",
            )
        )
        return
    if group_keys:
        _check_group(group_keys[0], node, path, depth, errors, leaf_count)
        return
    unknown = sorted(set(node) - LEAF_KEYS)
    if unknown and "field" not in node and "operator" not in node:
        errors.append(
            RuleError("unsupported_group", path, f"unknown group key: {', '.join(unknown)}")
        )
        return
    leaf_count[0] += 1
    _check_leaf(node, path, errors)


def _check_group(
    key: str,
    node: dict[str, Any],
    path: str,
    depth: int,
    errors: list[RuleError],
    leaf_count: list[int],
) -> None:
    extra = sorted(set(node) - {key})
    if extra:
        errors.append(
            RuleError(
                "unsupported_group",
                path,
                f"group '{key}' has unexpected keys: {', '.join(extra)}",
            )
        )
    value = node[key]
    child_path = f"{path}.{key}"
    if key == "not":
        if not isinstance(value, dict):
            errors.append(
                RuleError("unsupported_group", child_path, "'not' must wrap a single node object")
            )
            return
        _check_node(value, child_path, depth + 1, errors, leaf_count)
        return
    if not isinstance(value, list) or not value:
        errors.append(
            RuleError(
                "unsupported_group",
                child_path,
                f"'{key}' must be a non-empty list of nodes",
            )
        )
        return
    for index, child in enumerate(value):
        _check_node(child, f"{child_path}[{index}]", depth + 1, errors, leaf_count)


def _check_leaf(node: dict[str, Any], path: str, errors: list[RuleError]) -> None:
    for key in sorted(set(node) - LEAF_KEYS):
        errors.append(RuleError("unknown_key", f"{path}.{key}", f"unknown key: {key}"))
    if not _is_non_empty_str(node.get("criterion_id")):
        errors.append(
            RuleError(
                "invalid_attribute",
                f"{path}.criterion_id",
                "'criterion_id' must be a non-empty string",
            )
        )
    if not _is_non_empty_str(node.get("explanation")):
        errors.append(
            RuleError(
                "invalid_attribute",
                f"{path}.explanation",
                "'explanation' must be a non-empty string",
            )
        )
    if "mandatory" in node and not isinstance(node["mandatory"], bool):
        errors.append(
            RuleError("invalid_attribute", f"{path}.mandatory", "'mandatory' must be a bool")
        )
    refs = node.get("source_refs", [])
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        errors.append(
            RuleError(
                "invalid_attribute",
                f"{path}.source_refs",
                "'source_refs' must be a list of strings",
            )
        )
    field_def = _field_definition(node, path, errors)
    operator = node.get("operator")
    if not isinstance(operator, str) or operator not in SUPPORTED_OPERATORS:
        errors.append(
            RuleError("invalid_operator", f"{path}.operator", f"unsupported operator: {operator!r}")
        )
        return
    if field_def is None:
        return
    field_type = str(field_def["type"])
    if operator not in OPERATORS_BY_FIELD_TYPE.get(field_type, frozenset()):
        errors.append(
            RuleError(
                "invalid_operator",
                f"{path}.operator",
                f"operator '{operator}' is not allowed for field type '{field_type}'",
            )
        )
        return
    if operator != "exists":
        _check_operand(operator, field_def, node, path, errors)


def _field_definition(
    node: dict[str, Any], path: str, errors: list[RuleError]
) -> Mapping[str, Any] | None:
    field = node.get("field")
    registry = load_registry()
    if not _is_non_empty_str(field) or field not in registry:
        errors.append(
            RuleError(
                "unknown_field", f"{path}.field", "field id is missing or not in the catalogue"
            )
        )
        return None
    return registry[field]


def _check_operand(
    operator: str,
    field_def: Mapping[str, Any],
    node: dict[str, Any],
    path: str,
    errors: list[RuleError],
) -> None:
    value_path = f"{path}.value"
    if "value" not in node:
        errors.append(
            RuleError("missing_value", value_path, f"'value' is required for operator '{operator}'")
        )
        return
    value = node["value"]
    if operator in {"in", "not_in"}:
        if not isinstance(value, list):
            errors.append(
                RuleError(
                    "invalid_operand_type",
                    value_path,
                    f"operator '{operator}' requires a list value",
                )
            )
            return
        for index, item in enumerate(value):
            errors.extend(_check_scalar(field_def, item, f"{value_path}[{index}]"))
        return
    errors.extend(_check_scalar(field_def, value, value_path))


def _check_scalar(field_def: Mapping[str, Any], value: Any, path: str) -> list[RuleError]:
    field_type = str(field_def["type"])
    if not _operand_matches_type(field_type, value):
        return [
            RuleError(
                "invalid_operand_type",
                path,
                f"value must match field type '{field_type}'",
            )
        ]
    allowed = field_def.get("allowed_values")
    if allowed is not None and value not in allowed:
        return [RuleError("unknown_value", path, "value is not one of the allowed options")]
    return []


def _operand_matches_type(field_type: str, value: Any) -> bool:
    if field_type in ("int", "number"):
        return _is_number(value)
    if field_type == "bool":
        return isinstance(value, bool)
    return isinstance(value, str)


# ---------------------------------------------------------------- evaluation


def evaluate_rule(node: dict[str, Any], profile: Mapping[str, Any]) -> CriterionResult:
    """Evaluate a validated rule node against a profile. Raises ValueError on type mismatch."""
    group_keys = [k for k in node if k in GROUP_KEYS]
    if not group_keys:
        return _evaluate_leaf(node, profile)
    key = group_keys[0]
    if key == "not":
        child = evaluate_rule(node["not"], profile)
        return _group_result(_negate(child.status), (child,), "not")
    return _evaluate_list_group(key, node[key], profile)


def _evaluate_list_group(
    key: str, nodes: list[dict[str, Any]], profile: Mapping[str, Any]
) -> CriterionResult:
    if not nodes:
        raise ValueError(f"'{key}' must be a non-empty list of nodes")
    children = tuple(evaluate_rule(child, profile) for child in nodes)
    statuses = [c.status for c in children]
    status = _combine_all(statuses) if key == "all" else _combine_any(statuses)
    return _group_result(status, children, key)


def _combine_all(statuses: list[Tri]) -> Tri:
    if Tri.FAIL in statuses:
        return Tri.FAIL
    if all(s is Tri.PASS for s in statuses):
        return Tri.PASS
    return Tri.UNKNOWN


def _combine_any(statuses: list[Tri]) -> Tri:
    if Tri.PASS in statuses:
        return Tri.PASS
    if all(s is Tri.FAIL for s in statuses):
        return Tri.FAIL
    return Tri.UNKNOWN


def _negate(status: Tri) -> Tri:
    if status is Tri.PASS:
        return Tri.FAIL
    if status is Tri.FAIL:
        return Tri.PASS
    return Tri.UNKNOWN


def _group_result(status: Tri, children: tuple[CriterionResult, ...], key: str) -> CriterionResult:
    refs = tuple(dict.fromkeys(ref for c in children for ref in c.source_refs))
    return CriterionResult(
        criterion_id=None,
        status=status,
        mandatory=any(c.mandatory for c in children),
        explanation=f"Group '{key}': {status.value}",
        source_refs=refs,
        children=children,
    )


def _evaluate_leaf(node: dict[str, Any], profile: Mapping[str, Any]) -> CriterionResult:
    status = _leaf_status(node, profile)
    return CriterionResult(
        criterion_id=node["criterion_id"],
        status=status,
        mandatory=bool(node.get("mandatory", False)),
        explanation=f"{_PREFIX[status]}: {node['explanation']}",
        source_refs=tuple(node.get("source_refs", [])),
        children=(),
    )


def _leaf_status(node: dict[str, Any], profile: Mapping[str, Any]) -> Tri:
    field = node["field"]
    operator = node["operator"]
    raw = profile.get(field)
    if operator == "exists":
        if field not in profile:
            return Tri.UNKNOWN
        return Tri.UNKNOWN if _is_missing(raw) else Tri.PASS
    if _is_missing(raw):
        return Tri.UNKNOWN
    expected = node["value"]
    _check_types(operator, raw, expected)
    return Tri.PASS if _compare(operator, raw, expected) else Tri.FAIL


def _compare(operator: str, raw: Any, expected: Any) -> bool:
    if operator == "eq":
        return bool(raw == expected)
    if operator == "ne":
        return bool(raw != expected)
    if operator == "in":
        return raw in expected
    if operator == "not_in":
        return raw not in expected
    if operator == "contains":
        return expected in raw
    if operator == "gt":
        return bool(raw > expected)
    if operator == "gte":
        return bool(raw >= expected)
    if operator == "lt":
        return bool(raw < expected)
    if operator == "lte":
        return bool(raw <= expected)
    raise ValueError(f"unsupported operator: {operator!r}")


def _check_types(operator: str, raw: Any, expected: Any) -> None:
    if operator in ORDERING_OPERATORS:
        if not (_is_number(raw) and _is_number(expected)):
            raise ValueError(f"operator '{operator}' requires numeric values")
    elif operator in {"eq", "ne"}:
        if _kind(raw) != _kind(expected):
            raise ValueError(f"operator '{operator}' compares mismatched types")
    elif operator in {"in", "not_in"}:
        if not isinstance(expected, list):
            raise ValueError(f"operator '{operator}' requires a list value")
        if any(_kind(item) != _kind(raw) for item in expected):
            raise ValueError(f"operator '{operator}' has mismatched item types")
    elif operator == "contains":
        if isinstance(raw, str) and not isinstance(expected, str):
            raise ValueError("operator 'contains' on a string requires a string value")
        if not isinstance(raw, (str, list)):
            raise ValueError("operator 'contains' requires a string or list profile value")


# ---------------------------------------------------------------- pruning


def prune_advisory(node: dict[str, Any]) -> dict[str, Any] | None:
    """Return the rule node with advisory leaves removed, or None if no mandatory leaf remains.

    A leaf is advisory when its `mandatory` flag is false (the default). Groups left with no
    children are removed; a `not` whose child is removed is removed too. The input is not
    mutated. Pure: used to build the decision expression, not the per-criterion output.
    """
    for key in ("all", "any"):
        if key in node:
            children = [
                pruned for child in node[key] if (pruned := prune_advisory(child)) is not None
            ]
            if not children:
                return None
            return {key: children}
    if "not" in node:
        inner = prune_advisory(node["not"])
        return None if inner is None else {"not": inner}
    return dict(node) if bool(node.get("mandatory", False)) else None


# ---------------------------------------------------------------- helpers


def _is_missing(raw: Any) -> bool:
    return raw is None or raw == PREFER_NOT_TO_SAY


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _kind(value: Any) -> str:
    if _is_number(value):
        return "number"
    return type(value).__name__
