"""Strict part validation visits each captured state once without weakening public checks."""

from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_run import build_flow_run
from app.v3.flow_run_schema import validate_schema
from app.v3.flow_transport import read_flow_run, write_flow_run
from tests.v3.test_flow_run_fixtures import sample


def test_catalog_can_be_validated_as_a_strict_standalone_part() -> None:
    inputs, outcome = sample(True)
    run = build_flow_run(inputs, outcome)
    validate_schema(run["catalog"], "catalog")
    malformed = {**run["catalog"], "unexpected": True}
    with pytest.raises(ValueError):
        validate_schema(malformed, "catalog")


def test_unknown_schema_part_cannot_silently_select_full_run() -> None:
    inputs, outcome = sample(True)
    run = build_flow_run(inputs, outcome)
    with pytest.raises(ValueError):
        validate_schema(run, "unsupported-part")


def test_reader_visits_each_captured_state_schema_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, outcome = sample(True)
    expected = build_flow_run(inputs, outcome)
    write_flow_run(expected, tmp_path, inputs=inputs.frozen_bytes)
    visits: Counter[int] = Counter()
    descend = Draft202012Validator.descend

    def observe(
        validator: Draft202012Validator,
        instance: Any,
        schema: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[ValidationError]:
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if isinstance(instance, dict) and {"stock", "workers", "orders"} <= properties.keys():
            visits[id(instance)] += 1
        yield from descend(validator, instance, schema, *args, **kwargs)

    monkeypatch.setattr(Draft202012Validator, "descend", observe)
    actual = read_flow_run(tmp_path)
    assert actual == expected
    assert len(visits) == len(actual["checkpoints"]) + 2
    assert set(visits.values()) == {1}
