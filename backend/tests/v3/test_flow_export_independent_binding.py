"""Exact frozen physical facts cannot be matched using Python boolean/integer equality."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_run import frozen_inputs
from app.v3.flow_transport import read_flow_run, write_flow_run
from tests.v3.test_flow_export_independent_semantics import hand_run
from tests.v3.test_flow_run_fixtures import sample


def test_rehashed_catalog_boolean_cannot_match_frozen_integer_clock(tmp_path: Path) -> None:
    compiled, _ = sample()
    manifest = write_flow_run(hand_run(), tmp_path, inputs=compiled.frozen_bytes)
    path = tmp_path / manifest["catalog"]["path"]
    catalog = parse_json(path.read_bytes())
    actor = next(row for row in catalog["actors"] if row["actor_id"] == "P02")
    assert actor["available_tick"] == 0 and type(actor["available_tick"]) is int
    actor["available_tick"] = False
    raw = canonical_bytes(catalog)
    path.write_bytes(raw)
    manifest["catalog"].update(bytes=len(raw), sha256=sha256(raw).hexdigest())
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_flow_run(tmp_path)


def test_builder_rejects_type_changed_profile_with_value_equal_frozen_clock() -> None:
    compiled, _ = sample()
    actors = tuple(
        replace(actor, available_tick=False) if actor.actor_id == "P02" else actor
        for actor in compiled.profile.actors
    )
    altered = replace(compiled, profile=replace(compiled.profile, actors=actors))
    with pytest.raises(ValueError):
        frozen_inputs(altered)
