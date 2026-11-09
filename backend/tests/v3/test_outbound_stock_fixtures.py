"""Small exact identity arithmetic, independent of any warehouse engine."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.outbound_stock_models import StockHU
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload, WorkloadPolicy
from tests.v3.test_workload_fixtures import hand_source


def workload(inbound: int = 2, outbound: int = 6) -> TimedWorkload:
    source = hand_source()
    source = replace(source, outbound_weights=source.inbound_weights)
    return materialize_workload(source, WorkloadPolicy(12, inbound, outbound, "normal"))


def initial() -> tuple[StockHU, ...]:
    return tuple(
        StockHU(
            "initial-HU-" + sku,
            sku,
            "SMALL_CARTON",
            "initial-lot-" + sku,
            tuple(f"initial-HU-{sku}:unit:{i:04d}" for i in range(1, 25)),
            24,
            F(".94"),
            "slot-" + sku,
            None,
            None,
        )
        for sku in ("A", "B")
    )
