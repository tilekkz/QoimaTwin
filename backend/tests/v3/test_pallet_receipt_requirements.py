"""Source counts and service assumptions, authored before implementation and not executed."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.inputs import load_v3_bundle
from app.v3.pallet_receipt_requirements import compile_pallet_receipt_requirements, reject_credit
from app.v3.pallet_receipt_types import PalletReceiptError, PalletReceiptRequest
from app.v3.stock_ledger import StockLedger
from app.v3.stock_source import source_seed

DATA = Path(__file__).resolve().parents[2] / "data"
BASE, VEHICLE = DATA / "v3-proposal", DATA / "v3-vehicle-proposal"


def request(port: str = "IN_W_BULK") -> PalletReceiptRequest:
    return PalletReceiptRequest(
        "new-pallet-R1",
        "new-pallet-HU1",
        "new-pallet-lot1",
        "v3:HU:initial:DEMO_172:01",
        port,
        "v3:slot:HEAVY_E:001:L1:B1",
        "R01",
        0,
        600_000_000,
        900_000_000,
    )


@pytest.mark.parametrize("port,capacity", [("IN_W_BULK", 2), ("IN_N_STANDARD", 4)])
def test_source_requirement_keeps_future_stock_uncredited(port: str, capacity: int) -> None:
    result = compile_pallet_receipt_requirements(BASE, VEHICLE, request(port))
    assert result.baseline_hus == 530 and result.baseline_units == 12_256
    assert result.receipt.quantity_units == 24 and result.gross_mass_kg == F(455)
    assert result.port.bay_capacity == 1 and result.port.buffer_capacity == capacity
    assert result.port.service_tick == 30_000_000
    assert result.driver_id == "F01" and result.vehicle_id == "FL01"
    assert result.receiver_ids == ("R01", "R02") and len(result.actor_ids) == 24
    assert result.route.node_ids[0] == "v3:service:" + port
    assert result.route.node_ids[-1] == "v3:module:HEAVY_E:001:B1:vehicle:node"
    assert result.route.arcs and result.route.root_length_m > 0
    assert result.route.resource_capacities
    assert all(capacity == 1 for _, capacity in result.route.resource_capacities)
    assert result.receipt_credit_allowed is False and result.operational_admission is False
    assert "STAGING_PICKUP_GEOMETRY_MISSING" in {b.code for b in result.blockers}
    assert "STAGING_VEHICLE_CONNECTOR_MISSING" in {b.code for b in result.blockers}


def test_credit_boundary_does_not_mutate_the_actual_source_ledger_or_leases() -> None:
    ledger = StockLedger(source_seed(load_v3_bundle(BASE)))
    before = ledger.inventory_snapshot()
    leases = {"worker:R01": "existing-job"}
    with pytest.raises(PalletReceiptError) as error:
        reject_credit(BASE, VEHICLE, request(), ledger, leases)
    assert error.value.code == "PALLET_RECEIPT_PROOF_CHAIN_INCOMPLETE"
    assert ledger.inventory_snapshot() == before and ledger.history == ()
    assert leases == {"worker:R01": "existing-job"}
    assert sum(dict(ledger.balance().units_by_sku).values()) == 12_256


@pytest.mark.parametrize(
    "change,code",
    [
        ("same_hu", "RECEIPT_ID_COLLISION"),
        ("wrong_port", "UNSUPPORTED_PALLET_PORT"),
        ("occupied", "TARGET_ALREADY_OCCUPIED"),
        ("class", "UNSUPPORTED_RECEIPT_TEMPLATE"),
        ("boolean", "INVALID_RECEIPT_CLOCK"),
    ],
)
def test_invalid_source_request_is_rejected_without_a_self_reported_pass(
    change: str,
    code: str,
) -> None:
    value = request()
    if change == "same_hu":
        value = replace(value, hu_id=value.template_hu_id)
    elif change == "wrong_port":
        value = replace(value, port_id="IN_E_PARCEL")
    elif change == "occupied":
        value = replace(value, slot_id="v3:slot:HEAVY_E:011:L1:B1")
    elif change == "class":
        value = replace(value, template_hu_id="v3:HU:initial:DEMO_001:01")
    else:
        object.__setattr__(value, "arrival_tick", False)
    with pytest.raises(PalletReceiptError) as error:
        compile_pallet_receipt_requirements(BASE, VEHICLE, value)
    assert error.value.code == code


def test_intake_duration_cannot_fit_a_shorter_horizon() -> None:
    value = replace(request(), horizon_tick=29_000_000, end_tick=100_000_000)
    with pytest.raises(PalletReceiptError) as error:
        compile_pallet_receipt_requirements(BASE, VEHICLE, value)
    assert error.value.code == "INTAKE_WINDOW_CANNOT_FIT"


def test_exact_service_finish_at_horizon_is_only_a_timing_prerequisite() -> None:
    value = replace(request(), horizon_tick=30_000_000, end_tick=100_000_000)
    result = compile_pallet_receipt_requirements(BASE, VEHICLE, value)
    assert result.port.service_tick == 30_000_000
    assert result.receipt_credit_allowed is False and result.blockers
