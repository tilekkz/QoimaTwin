"""Discriminator validation must agree with the complete published JSON Schema."""

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from app.exporter.wire_schema import proposal_schema
from app.exporter.wire_validate import _compiled, validate_schema_fast
from tests.unit.test_proposal_export import proposal as proposal


def _cell_event() -> dict[str, Any]:
    return {
        "seq": 0,
        "at_tick": 0,
        "at_s": 0,
        "phase": 2,
        "kind": "cell_moved",
        "entity_id": "T001",
        "payload": {"cargo_id": "T001", "from": "C1", "to": "C2"},
    }


def _minimal(proposal: dict[str, Any]) -> dict[str, Any]:
    run = deepcopy(proposal)
    run.update(events=[_cell_event()], actions=[], snapshots=run["snapshots"][:1])
    return run


def _error(validator: Any, run: dict[str, Any]) -> ValidationError | None:
    try:
        validator(run)
    except ValidationError as exc:
        return exc
    return None


def test_valid_published_fixture_and_empty_events_match_standard(proposal: dict[str, Any]) -> None:
    standard = Draft202012Validator(proposal_schema())
    for run in [proposal, _minimal(proposal)]:
        standard.validate(run)
        validate_schema_fast(run)
    run = _minimal(proposal)
    run["events"] = []
    standard.validate(run)
    validate_schema_fast(run)


@pytest.mark.parametrize(
    "damage",
    [
        "kind",
        "kind_array",
        "event_scalar",
        "payload_extra",
        "missing_payload",
        "envelope_extra",
        "negative_tick",
        "quantity",
        "root_extra",
        "events_type",
        "snapshot_state",
        "action_operation",
    ],
)
def test_invalid_documents_match_standard(proposal: dict[str, Any], damage: str) -> None:
    run = _minimal(proposal)
    _damage(run, proposal, damage)
    expected = _error(Draft202012Validator(proposal_schema()).validate, run)
    actual = _error(validate_schema_fast, run)
    assert expected is not None and actual is not None
    assert list(actual.absolute_path) == list(expected.absolute_path)


def _damage(run: dict[str, Any], proposal: dict[str, Any], damage: str) -> None:
    event = run["events"][0]
    if damage == "kind":
        event["kind"] = "unknown_event"
    elif damage == "kind_array":
        event["kind"] = []
    elif damage == "event_scalar":
        run["events"] = [1]
    elif damage == "payload_extra":
        event["payload"]["typo"] = True
    elif damage == "missing_payload":
        del event["payload"]["cargo_id"]
    elif damage == "envelope_extra":
        event["unexpected"] = 1
    elif damage == "negative_tick":
        event["at_tick"] = -1
    elif damage == "quantity":
        event.update(
            kind="stock_transferred",
            payload={
                "cargo_id": "T1",
                "sku_id": "S",
                "lot_id": "L",
                "quantity": 0,
                "from": {"kind": "pickface", "ref": "S"},
                "to": {"kind": "tote", "ref": "T1"},
            },
        )
    elif damage == "root_extra":
        run["unexpected"] = 1
    elif damage == "events_type":
        run["events"] = "wrong"
    elif damage == "snapshot_state":
        run["snapshots"][0]["state"]["actors"][0]["state"] = "UNKNOWN"
    else:
        run["actions"] = [deepcopy(proposal["actions"][0])]
        run["actions"][0]["operation"] = "UNKNOWN"


def _sample(schema: dict[str, Any]) -> Any:
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return _sample(schema["anyOf"][0])
    kind = schema.get("type")
    if kind == "object":
        return {name: _sample(schema["properties"][name]) for name in schema.get("required", [])}
    if kind == "array":
        return [_sample(schema["items"]) for _ in range(schema.get("minItems", 0))]
    if kind in {"integer", "number"}:
        return schema.get("minimum", 0)
    if kind == "boolean":
        return True
    return "example"


@pytest.mark.parametrize("damage", ["valid", "missing", "extra", "null"])
def test_every_published_event_kind_matches_standard(proposal: dict[str, Any], damage: str) -> None:
    schema = proposal_schema()
    standard = Draft202012Validator(schema)
    for branch in schema["properties"]["events"]["items"]["allOf"]:
        event = _cell_event()
        event["kind"] = branch["if"]["properties"]["kind"]["const"]
        event["payload"] = _sample(branch["then"]["properties"]["payload"])
        first_key = next(iter(event["payload"]))
        if damage == "missing":
            del event["payload"][first_key]
        elif damage == "extra":
            event["payload"]["unexpected"] = 1
        elif damage == "null":
            event["payload"][first_key] = None
        run = _minimal(proposal)
        run["events"] = [event]
        expected, actual = _error(standard.validate, run), _error(validate_schema_fast, run)
        assert (expected is None) == (actual is None), event["kind"]
        if damage == "valid":
            assert actual is None


@pytest.mark.parametrize(
    "change", ["payload_limit", "closed_envelope", "typed_additional", "reference", "prefix"]
)
def test_schema_evolution_cannot_weaken_constraints(
    proposal: dict[str, Any], monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    schema = proposal_schema()
    run = _minimal(proposal)
    array = schema["properties"]["events"]
    item = array["items"]
    if change == "payload_limit":
        item["properties"]["payload"]["maxProperties"] = 2
    elif change == "closed_envelope":
        branch = next(
            b for b in item["allOf"] if b["if"]["properties"]["kind"]["const"] == "cell_moved"
        )
        branch["then"]["additionalProperties"] = False
    elif change == "typed_additional":
        item["properties"]["payload"]["additionalProperties"] = {"type": "integer"}
        branch = next(
            b for b in item["allOf"] if b["if"]["properties"]["kind"]["const"] == "cell_moved"
        )
        del branch["then"]["properties"]["payload"]["additionalProperties"]
    elif change == "reference":
        schema["$defs"] = {"event": item}
        array["items"] = {"$ref": "#/$defs/event"}
    else:
        array["prefixItems"] = [{"type": "integer"}]
        run["events"] = [42]
    monkeypatch.setattr("app.exporter.wire_schema.proposal_schema", lambda: schema)
    _compiled.cache_clear()
    try:
        expected = _error(Draft202012Validator(schema).validate, run)
        actual = _error(validate_schema_fast, run)
        assert (expected is None) == (actual is None)
        assert (actual is None) == (change in {"reference", "prefix"})
    finally:
        _compiled.cache_clear()
