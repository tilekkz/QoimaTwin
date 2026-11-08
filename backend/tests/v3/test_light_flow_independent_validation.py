"""Known material references and complete carried mass are admission prerequisites."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_missing_declared_parcel_rejects_before_any_paid_operation() -> None:
    profile = hand_profile()
    materials = tuple(c for c in profile.materials if c.container_id != "P1")
    with pytest.raises(ValueError):
        LightFlowEngine(replace(profile, materials=materials), source_catalog())


@pytest.mark.parametrize("role", ["picker", "shipper", "cart"])
def test_complete_load_including_tare_must_fit_declared_handler_capacity(role: str) -> None:
    profile = hand_profile()
    if role == "cart":
        # Three units alone.105 fit, but the loaded carrier.305 does not.
        profile = replace(profile, cart=replace(profile.cart, max_gross_kg=F(1, 5)))
    else:
        identity = profile.picker_id if role == "picker" else profile.shipper_id
        limit = F(1, 5) if role == "picker" else F(3, 25)
        actors = tuple(
            replace(a, max_gross_kg=limit) if a.actor_id == identity else a for a in profile.actors
        )
        profile = replace(profile, actors=actors)
        # Shipper limit.120 exceeds units.105 but is less than sealed parcel.155.
    with pytest.raises(ValueError):
        LightFlowEngine(profile, source_catalog())
