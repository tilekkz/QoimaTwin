"""Finite materials and source-bound replacement geometry constrain actual packing admission."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.belt_state import RunningCarrier
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.stock_models import Container
from tests.v3.test_coordinator_packing import packing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_full_empty_carrier_rack_never_admits_unbounded_helper_work() -> None:
    profile = packing_profile(candidate=True)
    flow = profile.world.receipts.flow
    extra = Container("C2", flow.materials[0].recipe, "empties")
    flow = replace(flow, materials=(*flow.materials, extra))
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    engine = CoordinatorEngine(profile, receipt_conveyor())
    result = engine.run(200 * SECOND, 200 * SECOND)
    assert result.status == "partial" and result.business_complete_tick is None
    assert result.staffing_status == "valid" and all(
        r.restored_tick == 160 * SECOND for r in result.at_end.roles
    )
    assert not engine.packing_states and not engine.belt.external and not engine.leases
    assert result.at_end.packing_waits == (("O1", "EMPTY_CARRIER_RACK_FULL"),)
    contents = {name: engine.ledger.contents(name) for name in ("HU1", "C1", "P1", "C2")}
    assert [len(contents[k].units) for k in contents] == [21, 3, 0, 0]
    assert result.at_end.balance.gross_mass_kg == F("1.39")
    assert contents["P1"].container.owner_id == "package-pool"
    assert contents["C2"].container.owner_id == "empties"


@pytest.mark.parametrize("limit,parcel_tare", [(F(".19"), F(".05")), (F(".30"), F(".25"))])
def test_helper_capacity_uses_actual_empty_carrier_and_complete_parcel_mass(
    limit: F, parcel_tare: F
) -> None:
    profile = packing_profile(candidate=True)
    flow = profile.world.receipts.flow
    actors = tuple(
        replace(a, max_gross_kg=limit) if a.actor_id == "P12" else a for a in flow.actors
    )
    materials = tuple(
        replace(c, recipe=replace(c.recipe, tare_kg=parcel_tare)) if c.container_id == "P1" else c
        for c in flow.materials
    )
    flow = replace(flow, actors=actors, materials=materials)
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    assert result.business_complete_tick == 308_254_552
    assert any(
        getattr(e, "packing_wait_reason", None) == "PACKER_GROSS_CAPACITY" for e in result.events
    )
    assert result.at_end.packing[0].actor_id == "K06"
    assert next(r for r in result.at_end.roles if r.actor_id == "P12").restored_tick == 160 * SECOND


class ExpansionProbe(CoordinatorEngine):
    conflict_rejected = False
    replaced_without_reset = False

    def _dispatch_round(self) -> None:
        super()._dispatch_round()
        packing = self.packing_states.get("O1")
        if packing is not None and packing.phase == "pack" and not self.conflict_rejected:
            self.conflict_rejected = not self.belt.reserve(
                "unadmitted-contender", packing.belt_resources
            )

    def station_finished(self, state: RunningCarrier, stage: str) -> None:
        if stage != "clear":
            super().station_finished(state, stage)
            return
        pose, prefix = state.pose, state.steps[: state.index + 1]
        assert state.job.payload.dimensions_xyz_m == (F(".32"), F(".24"), F(".24"))
        super().station_finished(state, stage)
        assert state.job.payload.dimensions_xyz_m == (F(".6"), F(".34"), F(".4"))
        assert state.job.hu_id == state.job.payload.payload_id == "P1"
        self.replaced_without_reset = pose == state.pose and prefix == state.steps[: len(prefix)]


def test_enlarged_parcel_replaces_only_at_actual_clear_without_resetting_pose_or_history() -> None:
    profile = packing_profile(candidate=True)
    flow = profile.world.receipts.flow
    carrier = replace(
        flow.materials[0].recipe,
        outer=(F(".32"), F(".24"), F(".24")),
        inner=(F(".30"), F(".20"), F(".20")),
    )
    package = replace(
        flow.materials[1].recipe,
        outer=(F(".6"), F(".34"), F(".4")),
        inner=(F(".56"), F(".30"), F(".36")),
    )
    flow = replace(
        flow,
        materials=(
            replace(flow.materials[0], recipe=carrier),
            replace(flow.materials[1], recipe=package),
        ),
    )
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    engine = ExpansionProbe(profile, receipt_conveyor())
    result = engine.run(300 * SECOND, 400 * SECOND)
    assert (
        result.status == "complete" and engine.conflict_rejected and engine.replaced_without_reset
    )
    assert result.at_end.balance.gross_mass_kg == F("1.19")
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
    old = [
        e.belt_event
        for e in result.events
        if e.belt_event is not None and e.belt_event.kind == "arrived"
    ]
    assert len(old) == 1 and old[0].hu_id == "C1"
