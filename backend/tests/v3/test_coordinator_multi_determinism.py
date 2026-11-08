"""Resource registration ordering is not a hidden scheduling priority."""

from dataclasses import replace

from app.storage.canonical_json import sha256_hex
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.run_values import record
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_resource_permutation_preserves_native_events_and_captured_state() -> None:
    profile = multi_profile(candidate=False, two_carts=True)
    resources = profile.unit_resources
    assert resources is not None
    reordered = replace(
        profile,
        unit_resources=replace(
            resources,
            stations=resources.stations[::-1],
            carts=resources.carts[::-1],
            pickers=resources.pickers[::-1],
            ports=resources.ports[::-1],
            assignments=resources.assignments[::-1],
        ),
    )
    first = CoordinatorEngine(profile, receipt_conveyor()).run(84 * SECOND, 84 * SECOND)
    second = CoordinatorEngine(reordered, receipt_conveyor()).run(84 * SECOND, 84 * SECOND)
    assert sha256_hex(record(first)) == sha256_hex(record(second))
    assert len(first.at_end.carts) == 2 and len(first.at_end.inventory.claims) == 2
