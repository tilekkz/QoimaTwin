"""Compile the published event discriminator without weakening its JSON Schema constraints."""

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

type Json = dict[str, Any]


@dataclass(frozen=True)
class _Compiled:
    top: Draft202012Validator
    event: Draft202012Validator | None
    by_kind: dict[str, Draft202012Validator]


def _has_reference(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in value for key in ("$ref", "$dynamicRef")) or any(
            _has_reference(item) for item in value.values()
        )
    return isinstance(value, list) and any(_has_reference(item) for item in value)


def _branches(item: Json) -> dict[str, list[Any]] | None:
    branches: dict[str, list[Any]] = {}
    for branch in item.get("allOf", []):
        condition = branch.get("if", {})
        kind = condition.get("properties", {}).get("kind", {}).get("const")
        if (
            not isinstance(kind, str)
            or condition != {"properties": {"kind": {"const": kind}}}
            or set(branch) != {"if", "then"}
        ):
            return None
        branches.setdefault(kind, []).append(branch["then"])
    return branches


def _compatible_properties(left: Json, right: Json) -> bool:
    if "unevaluatedProperties" in left or "unevaluatedProperties" in right:
        return False
    left_names, right_names = set(left.get("properties", {})), set(right.get("properties", {}))
    return not (
        (left.get("additionalProperties", True) is not True and right_names - left_names)
        or (right.get("additionalProperties", True) is not True and left_names - right_names)
    )


def _intersect(left: Any, right: Any) -> Any:
    if left == right:
        return deepcopy(left)
    if not isinstance(left, dict) or not isinstance(right, dict):
        return {"allOf": [deepcopy(left), deepcopy(right)]}
    if not _compatible_properties(left, right):
        return {"allOf": [deepcopy(left), deepcopy(right)]}
    result = deepcopy(left)
    for key, value in right.items():
        if key not in result or result[key] == value:
            result[key] = deepcopy(value)
        elif key == "required":
            result[key] = list(dict.fromkeys([*result[key], *value]))
        elif key == "properties":
            for name, schema in value.items():
                result[key][name] = (
                    _intersect(result[key][name], schema)
                    if name in result[key]
                    else deepcopy(schema)
                )
        else:
            return {"allOf": [deepcopy(left), deepcopy(right)]}
    return result


@lru_cache(maxsize=1)
def _compiled() -> _Compiled:
    from app.exporter.wire_schema import proposal_schema

    schema = proposal_schema()
    Draft202012Validator.check_schema(schema)
    array = schema["properties"]["events"]
    item = array["items"]
    branches = _branches(item) if isinstance(item, dict) else None
    if (
        branches is None
        or _has_reference(item)
        or {"prefixItems", "unevaluatedItems"} & array.keys()
    ):
        return _Compiled(Draft202012Validator(schema), None, {})
    top = deepcopy(schema)
    del top["properties"]["events"]["items"]
    envelope = {key: value for key, value in item.items() if key != "allOf"}
    validators = {}
    for kind, constraints in branches.items():
        specialized = deepcopy(envelope)
        for constraint in constraints:
            specialized = _intersect(specialized, constraint)
        validators[kind] = Draft202012Validator(specialized)
    return _Compiled(Draft202012Validator(top), Draft202012Validator(item), validators)


def _validate_event(validator: Draft202012Validator, event: object, index: int) -> None:
    try:
        validator.validate(event)
    except ValidationError as exc:
        raise ValidationError(
            exc.message,
            validator=exc.validator,
            validator_value=exc.validator_value,
            instance=exc.instance,
            schema=exc.schema,
            path=["events", index, *exc.absolute_path],
            schema_path=["properties", "events", "items", *exc.absolute_schema_path],
            context=exc.context,
            cause=exc.cause,
        ) from exc


def validate_schema_fast(run: Json) -> None:
    """Validate the full public document, selecting the complete event schema by kind."""
    compiled = _compiled()
    compiled.top.validate(run)
    if compiled.event is None:
        return
    for index, event in enumerate(run["events"]):
        kind = event.get("kind") if isinstance(event, dict) else None
        validator = (
            compiled.by_kind.get(kind, compiled.event) if isinstance(kind, str) else compiled.event
        )
        _validate_event(validator, event, index)
