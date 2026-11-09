"""Strict typed decoding of one pinned C11 horizon document; rejects, never repairs."""

import math
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from app.v3.adaptation_models import (
    HorizonDoc,
    LegDoc,
    ReportedSummary,
    RouteDoc,
    RowDoc,
    TransferDoc,
)
from app.v3.adaptation_pin import (
    ADAPTED_SCHEMA,
    HORIZONS,
    PERIOD_UNIT,
    SCENARIO_ID,
    SCHEMA_VERSION,
    SOURCE_KIND,
    TRANSPORT_GRAPH,
)

MAXIMUM_TRANSFERS = 8


def text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: nonempty string required")
    return value


def integer(value: object, where: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{where}: integer required (booleans are not integers)")
    return value


def number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: JSON number required")
    if not math.isfinite(value):
        raise ValueError(f"{where}: finite number required")
    return float(value)


def exact(value: object, where: str) -> Fraction:
    """Exact decimal value of a JSON number, e.g. 1.4 -> 7/5 (never the binary float)."""
    number(value, where)
    return Fraction(str(value))


def false(value: object, where: str) -> bool:
    if value is not False:
        raise ValueError(f"{where}: must be the boolean false")
    return False


def mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where}: object required")
    return value


def route(value: object, where: str) -> RouteDoc:
    row = mapping(value, where)
    if row.get("graph") not in set(TRANSPORT_GRAPH.values()):
        raise ValueError(f"{where}: unsupported graph {row.get('graph')!r}")
    arcs = row.get("arc_ids")
    if not isinstance(arcs, list) or not arcs:
        raise ValueError(f"{where}: nonempty arc list required")
    return RouteDoc(
        row["graph"],
        text(row.get("from_node_id"), where),
        text(row.get("to_node_id"), where),
        tuple(text(arc, where) for arc in arcs),
        number(row.get("length_m"), where + "/length_m"),
    )


def _leg(value: object, where: str) -> LegDoc:
    row = mapping(value, where)
    if row.get("direction") not in {"inbound", "outbound"}:
        raise ValueError(f"{where}: unsupported leg direction")
    moves = number(row.get("expected_HU_moves"), where)
    return LegDoc(
        row["direction"], text(row.get("port_id"), where), moves, route(row["route"], where)
    )


def _row(value: object, where: str) -> RowDoc:
    row = mapping(value, where)
    false(row.get("operational_admission"), where)
    if integer(row.get("model_scale_factor"), where) != 1:
        raise ValueError(f"{where}: model scale must stay 1")
    legs = row.get("planning_legs")
    if not isinstance(legs, list) or not legs:
        raise ValueError(f"{where}: planning legs required")
    return RowDoc(
        text(row.get("handling_unit_id"), where),
        text(row.get("sku_id"), where),
        text(row.get("lot_id"), where),
        text(row.get("archetype_id"), where),
        integer(row.get("quantity_units"), where),
        text(row.get("slot_id"), where),
        text(row.get("module_id"), where),
        text(row.get("orientation_id"), where),
        tuple(_leg(leg, f"{where}/leg{i}") for i, leg in enumerate(legs)),
        number(row.get("planning_transport_cost_s"), where),
    )


def _transfer(value: object, where: str) -> TransferDoc:
    row = mapping(value, where)
    false(row.get("operational_admission"), where)
    tag = text(row.get("transport_tag"), where)
    if tag not in TRANSPORT_GRAPH:
        raise ValueError(f"{where}: unsupported transport tag {tag!r}")
    return TransferDoc(
        integer(row.get("sequence"), where),
        text(row.get("handling_unit_id"), where),
        text(row.get("sku_id"), where),
        text(row.get("archetype_id"), where),
        text(row.get("from_slot_id"), where),
        text(row.get("from_module_id"), where),
        text(row.get("to_slot_id"), where),
        text(row.get("to_module_id"), where),
        tag,
        exact(row.get("handling_allowance_s"), where),
        route(row.get("loaded_route"), where + "/loaded"),
        route(row.get("conservative_reverse_route"), where + "/reverse"),
        number(row.get("relocation_cost_s"), where),
        number(row.get("gross_route_saving_s"), where),
        number(row.get("net_saving_s"), where),
    )


def _summary(value: object, periods: int) -> ReportedSummary:
    row = mapping(value, "summary")
    if integer(row.get("evaluation_horizon_periods"), "summary/periods") != periods:
        raise ValueError(f"declared evaluation period count differs from horizon {periods}")
    if type(row.get("no_op")) is not bool:
        raise ValueError("summary/no_op: boolean required")
    return ReportedSummary(
        number(row.get("baseline_under_same_shifted_flow_cost_s"), "summary"),
        number(row.get("adapted_under_same_shifted_flow_cost_s"), "summary"),
        number(row.get("one_off_relocation_cost_s"), "summary"),
        number(row.get("net_transport_cost_reduction_s"), "summary"),
        integer(row.get("relocation_count"), "summary"),
        row["no_op"],
    )


def _header(document: Mapping[str, Any]) -> None:
    expected = (ADAPTED_SCHEMA, SCHEMA_VERSION, SCENARIO_ID, SOURCE_KIND)
    found = tuple(
        document.get(k) for k in ("schema_id", "schema_version", "scenario_id", "source_kind")
    )
    if found != expected:
        raise ValueError(f"foreign or unsupported planning document {found!r}")
    false(document.get("actual_engine_run"), "actual_engine_run")
    false(document.get("operational_admission"), "operational_admission")
    staffing = mapping(document.get("staffing"), "staffing")
    false(staffing.get("allocation_changes_allowed"), "staffing/allocation_changes_allowed")
    false(staffing.get("availability_simulated"), "staffing/availability_simulated")


def _unique(values: list[Any], what: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {what}")


def decode_horizon(document: object, periods: int) -> HorizonDoc:
    """Typed view of one horizon document for an expected unclocked period count."""
    if integer(periods, "requested periods") not in HORIZONS:
        raise ValueError("unsupported requested planning period count")
    root = mapping(document, "document")
    _header(root)
    reported = _summary(root.get("summary"), periods)
    rows = tuple(_row(r, f"assignments/{i}") for i, r in enumerate(root.get("assignments", [])))
    transfers = tuple(
        _transfer(t, f"transfers/{i}") for i, t in enumerate(root.get("transfers", []))
    )
    _unique([r.hu_id for r in rows], "HU row")
    _unique([r.slot_id for r in rows], "occupied slot")
    _unique([t.hu_id for t in transfers], "transferred HU (each HU moves at most once)")
    if [t.sequence for t in transfers] != list(range(1, len(transfers) + 1)):
        raise ValueError("transfer sequences must be 1..n in order")
    count = len(transfers)
    if count > MAXIMUM_TRANSFERS or (reported.relocation_count, reported.no_op) != (
        count,
        count == 0,
    ):
        raise ValueError("transfer count disagrees with the declared summary or limit")
    return HorizonDoc(periods, PERIOD_UNIT, rows, transfers, reported, False, False)
