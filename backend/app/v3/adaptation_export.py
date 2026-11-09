"""Deterministic JSON view of a C11 planning comparison (exact terms as "n/d" strings)."""

from fractions import Fraction
from typing import Any

from app.v3.adaptation_models import ExactRoute, PlannedTransfer, PlanningComparison


def ratio(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _route(route: ExactRoute) -> dict[str, Any]:
    return {"graph": route.graph, "arc_ids": list(route.arc_ids), "length_m": ratio(route.length_m)}


def _transfer(transfer: PlannedTransfer) -> dict[str, Any]:
    return {
        "sequence": transfer.sequence,
        "handling_unit_id": transfer.hu_id,
        "from_slot_id": transfer.from_slot_id,
        "to_slot_id": transfer.to_slot_id,
        "transport_tag": transfer.transport_tag,
        "released_by_sequence": transfer.released_by_sequence,
        "loaded_route": _route(transfer.loaded_route),
        "reverse_route": _route(transfer.reverse_route),
        "relocation_proxy_s": ratio(transfer.relocation_proxy_s),
        "gross_proxy_s": ratio(transfer.gross_proxy_s),
        "net_proxy_s": ratio(transfer.net_proxy_s),
        "planned_only": True,
    }


def comparison_json(result: PlanningComparison) -> dict[str, Any]:
    reported = result.reported
    return {
        "periods": result.periods,
        "period_unit": result.period_unit,
        "no_op": result.no_op,
        "baseline_proxy_s": ratio(result.baseline_proxy_s),
        "adapted_proxy_s": ratio(result.adapted_proxy_s),
        "relocation_proxy_s": ratio(result.relocation_proxy_s),
        "net_proxy_s": ratio(result.net_proxy_s),
        "inventory": {
            "handling_units": result.inventory.handling_units,
            "units": result.inventory.units,
            "gross_mass_kg": ratio(result.inventory.gross_mass_kg),
        },
        "transfers": [_transfer(t) for t in result.transfers],
        "source_reported_diagnostics": {
            "baseline_s": reported.baseline_under_same_shifted_flow_cost_s,
            "adapted_s": reported.adapted_under_same_shifted_flow_cost_s,
            "relocation_s": reported.one_off_relocation_cost_s,
            "net_s": reported.net_transport_cost_reduction_s,
        },
        "actual_engine_run": False,
        "operational_admission": False,
    }
