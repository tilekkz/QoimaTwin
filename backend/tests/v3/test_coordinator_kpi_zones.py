"""Storage zones come from reverified source facts, never parsing a suggestive owner ID."""

from dataclasses import replace
from pathlib import Path

import pytest

from app.v3.coordinator_metrics_inventory import source_zones
from app.v3.inputs import load_v3_bundle
from tests.v3.test_coordinator_kpi_fixtures import profile


def test_source_zone_table_and_retained_source_digest_are_bound() -> None:
    bundle = load_v3_bundle(Path(__file__).resolve().parents[2] / "data/v3-proposal")
    value = profile()
    hashes = tuple((row.path, row.raw_sha256) for row in bundle.source_inventory)
    flow = replace(
        value.world.receipts.flow, source_revision=bundle.source_revision, source_hashes=hashes
    )
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=flow))
    )
    zones = source_zones(value)
    assert zones is not None
    assert len(zones) == 776  # Pinned storage-slots-v3.json counts.slots.
    assert zones["v3:slot:HEAVY_E:001:L1:B1"] == "HEAVY_E"
    bad = replace(flow, source_hashes=((hashes[0][0], "0" * 64), *hashes[1:]))
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=bad))
    )
    with pytest.raises(ValueError, match="source zone binding"):
        source_zones(value)
