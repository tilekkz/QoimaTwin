"""Rehashed malformed parts must reject before semantics, including public full-run callers."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_run import build_flow_run, validate_flow_run
from app.v3.flow_transport import read_flow_run, write_flow_run
from tests.v3.test_flow_run_fixtures import sample


def _target(run: dict[str, Any], section: str) -> dict[str, Any]:
    if section == "metadata":
        return run
    if section == "catalog":
        result: dict[str, Any] = run["catalog"]
        return result
    result = run["events" if section == "event" else "checkpoints"][0]
    return result


def _corrupt(target: dict[str, Any], section: str, defect: str) -> None:
    required = {
        "metadata": "schema_version",
        "catalog": "actors",
        "event": "tick",
        "checkpoint": "state",
    }
    if defect == "required":
        del target[required[section]]
    elif defect == "extra":
        target["unexpected"] = True
    else:
        target[required[section]] = [] if section in {"metadata", "event", "checkpoint"} else {}


@pytest.mark.parametrize("section", ["metadata", "catalog", "event", "checkpoint"])
@pytest.mark.parametrize("defect", ["required", "extra", "wrong_type"])
def test_malformed_rehashed_part_rejects_in_reader_and_public_validator(
    tmp_path: Path, section: str, defect: str
) -> None:
    inputs, outcome = sample(True)
    good = build_flow_run(inputs, outcome)
    manifest = write_flow_run(good, tmp_path, inputs=inputs.frozen_bytes)
    bad = deepcopy(good)
    _corrupt(_target(bad, section), section, defect)
    with pytest.raises(ValueError):
        validate_flow_run(bad)
    descriptor = (
        manifest[section]
        if section in {"metadata", "catalog"}
        else manifest["event_chunks" if section == "event" else "checkpoint_chunks"][0]
    )
    path = tmp_path / descriptor["path"]
    body = json.loads(path.read_bytes())
    _corrupt(body if section in {"metadata", "catalog"} else body["items"][0], section, defect)
    raw = canonical_bytes(body)
    path.write_bytes(raw)
    descriptor.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_flow_run(tmp_path)
