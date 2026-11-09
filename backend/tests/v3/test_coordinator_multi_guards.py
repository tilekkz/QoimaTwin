"""Concurrent assignments must bind actual workers, carts and stock custody."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Literal

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


class DamagedConcurrentWorld(CoordinatorEngine):
    fault: Literal["cart_lease", "cart_operation", "picker_assignment", "picked_tick", "cart_spec"]

    def _check(self) -> None:
        if self.tick == (87 if self.fault == "picked_tick" else 84) * SECOND:
            if self.fault == "cart_lease":
                del self.leases["cart:CART02"]
            elif self.fault == "cart_operation":
                self.carts["CART02"].operation = None
            elif self.fault == "picked_tick":
                self.unit_states["O2"].picked_tick = True
            elif self.fault == "cart_spec":
                cart = self.carts["CART02"]
                cart.spec = replace(cart.spec, width_m=F(".1"))
            else:
                self.workers["P02"].order_id = "O1"
        super()._check()


@pytest.mark.parametrize(
    "fault", ["cart_lease", "cart_operation", "picker_assignment", "picked_tick", "cart_spec"]
)
def test_concurrent_physical_assignment_cannot_drift(
    fault: Literal["cart_lease", "cart_operation", "picker_assignment", "picked_tick", "cart_spec"],
) -> None:
    engine = DamagedConcurrentWorld(
        multi_profile(candidate=False, two_carts=True), receipt_conveyor()
    )
    engine.fault = fault
    with pytest.raises(RuntimeError):
        cap = (87 if fault == "picked_tick" else 84) * SECOND
        engine.run(cap, cap)
