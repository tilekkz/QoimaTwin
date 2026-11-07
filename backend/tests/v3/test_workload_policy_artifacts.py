"""The synthetic policy proposal is independently schema-valid and strictly decoded."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from app.v3.workload_policy import parse_workload_policy
from app.v3.workload_wire import policy_dict

ROOT = Path("docs/proposals/adaptive-v3")


def test_policy_example_validates_and_round_trips_without_hidden_defaults() -> None:
    schema = json.loads((ROOT / "workload-policy.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "workload-policy.example.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    assert policy_dict(parse_workload_policy(example)) == example
    assert example["horizon_tick"] == 60_000_000
    assert example["offered_hus"] == {"inbound": 10, "outbound": 10}


@pytest.mark.parametrize("case", ["extra", "version", "negative", "normal_windows", "empty_burst"])
def test_policy_schema_rejects_structurally_invalid_examples(case: str) -> None:
    schema = json.loads((ROOT / "workload-policy.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "workload-policy.example.json").read_text(encoding="utf-8"))
    if case == "extra":
        example["hourly_rate"] = 1500
    elif case == "version":
        example["schema_version"] = "source"
    elif case == "negative":
        example["offered_hus"]["inbound"] = -1
    elif case == "normal_windows":
        example["calendar"]["windows"] = [{"start_tick": 0, "end_tick": 1, "weight": [1, 1]}]
    else:
        example["calendar"]["kind"] = "burst"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(example)
