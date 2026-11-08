"""Rehashed nested aliases retain strict types and exact frozen source binding."""

import json
from pathlib import Path
from shutil import copytree
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.flow_run import build_flow_run
from app.v3.flow_transport import read_flow_run, write_flow_run
from tests.v3.test_flow_run_fixtures import sample


@pytest.fixture(scope="module")
def published_hand(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("reader-nested-authority")
    inputs, outcome = sample(True)
    write_flow_run(build_flow_run(inputs, outcome), root, inputs=inputs.frozen_bytes)
    return root


def _nested_alias(body: dict[str, Any], part: str) -> None:
    if part == "catalog":
        assert body["actors"][0]["available_tick"] == 0
        body["actors"][0]["available_tick"] = False
    elif part == "events":
        event = next(row for row in body["items"] if row["operation"] and row["operation"]["route"])
        route = event["operation"]["route"]
        assert route["length_m"]["denominator"] == 1
        route["length_m"]["denominator"] = True
    else:
        checkpoint = body["at_horizon"] if part == "metadata" else body["items"][0]
        worker = next(w for w in checkpoint["state"]["workers"] if w["actor_id"] == "K01")
        assert worker["paid_ticks"] == 0
        worker["paid_ticks"] = False
        checkpoint["state_hash"] = sha256_hex(checkpoint["state"])


@pytest.mark.parametrize("part", ["metadata", "checkpoints", "events", "catalog"])
def test_rehashed_nested_alias_rejects_before_exposing_any_run(
    published_hand: Path, tmp_path: Path, part: str
) -> None:
    root = tmp_path / "artifact"
    copytree(published_hand, root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    key = "checkpoint_chunks" if part == "checkpoints" else "event_chunks"
    descriptor = manifest[part] if part in {"metadata", "catalog"} else manifest[key][0]
    path = root / descriptor["path"]
    body = json.loads(path.read_bytes())
    _nested_alias(body, part)
    raw = canonical_bytes(body)
    path.write_bytes(raw)
    descriptor.update(bytes=len(raw), sha256=sha256_hex(body))
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))
    message = "Immutable catalog/source" if part == "catalog" else "connected flow .* schema"
    with pytest.raises(ValueError, match=message):
        read_flow_run(root)
