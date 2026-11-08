"""Exact C11 planning comparison for unclocked horizons 1/2/4/8 (ADR 0054).

All terms are recomputed from exact arc facts, adaptation-input move weights and declared
cost assumptions. Source-reported floats are kept only as separate diagnostics. Nothing here
runs an engine, executes or pays a relocation, or mutates a StockLedger.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.v3.adaptation_authority import require_same_authority, verify_package
from app.v3.adaptation_decode import decode_horizon, exact
from app.v3.adaptation_export import comparison_json
from app.v3.adaptation_models import (
    HorizonDoc,
    LegDoc,
    PlannedTransfer,
    PlanningComparison,
    RowDoc,
    TransferDoc,
)
from app.v3.adaptation_pin import HORIZONS, INPUT_PATH, PERIOD_UNIT
from app.v3.adaptation_replay import PlanningFacts, Projection, inventory_totals
from app.v3.adaptation_routes import PlanningGraphs, exact_route, transport_for
from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package

DIAGNOSTIC_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class PlanningContext:
    facts: PlanningFacts
    graphs: PlanningGraphs
    ports: Mapping[str, str]
    skus: Mapping[str, Mapping[str, Any]]
    speeds: Mapping[str, Fraction]
    handling: Mapping[str, Fraction]
    h1_costs: Mapping[str, Fraction]


def _facts(package: AdaptationPackage, source: Any) -> PlanningFacts:
    storage = package.base_document("storage-slots-v3.json")
    catalog = package.base_document("cargo-catalog-v3.json")
    baseline = package.base_document("baseline-assignment-v3.json")["assignments"]
    family = {
        hu: sku["home_storage_type"] for sku in source["skus"] for hu in sku["handling_unit_ids"]
    }
    return PlanningFacts(
        {s["slot_id"]: s for s in storage["slots"]},
        {m["module_id"]: m for m in storage["modules"]},
        {c["archetype_id"]: c for c in catalog["records"]},
        {row["handling_unit_id"]: row for row in baseline},
        family,
    )


def _context(package: AdaptationPackage) -> PlanningContext:
    source = package.document(INPUT_PATH)
    assumptions = source["cost_assumptions"]
    ports = {
        p["port_id"]: p["service_node_id"]
        for name in ("ports-v3.inbound.json", "ports-v3.outbound.json")
        for p in package.base_document(name)["ports"]
    }
    partial = PlanningContext(
        _facts(package, source),
        PlanningGraphs.from_links(package.base_document("layout-links-v3.json")),
        ports,
        {sku["sku_id"]: sku for sku in source["skus"]},
        {tag: exact(row["speed_m_s"], tag) for tag, row in assumptions.items()},
        {tag: exact(row["handling_allowance_s"], tag) for tag, row in assumptions.items()},
        {},
    )
    h1 = decode_horizon(package.horizon_document(1), 1)
    if h1.transfers or {r.hu_id: r.slot_id for r in h1.rows} != {
        hu: row["slot_id"] for hu, row in partial.facts.baseline.items()
    }:
        raise ValueError("the one-period horizon must keep every baseline placement")
    costs = {row.hu_id: _row_cost(partial, row, 1) for row in h1.rows}
    return replace(partial, h1_costs=costs)


def _moves(context: PlanningContext, row: RowDoc, leg: LegDoc, periods: int) -> Fraction:
    sku = context.skus[row.sku_id]
    mix = sku[f"{leg.direction}_port_mix"]
    if leg.port_id not in mix:
        raise ValueError(f"{row.hu_id}: leg port {leg.port_id} is not in the declared mix")
    total = exact(sku[f"expected_{leg.direction}_HU_moves"], row.sku_id)
    share = exact(mix[leg.port_id], row.sku_id)
    moves = total / len(sku["handling_unit_ids"]) * share * periods
    if abs(float(moves) - leg.reported_moves) > DIAGNOSTIC_TOLERANCE:
        raise ValueError(f"{row.hu_id}: reported move weight differs from {periods} periods")
    return moves


def _row_cost(context: PlanningContext, row: RowDoc, periods: int) -> Fraction:
    if row.slot_id not in context.facts.slots or (
        row.module_id != context.facts.slots[row.slot_id]["module_id"]
    ):
        raise ValueError("Planning row module differs from its verified source slot")
    slot = context.facts.slots[row.slot_id]["access"]
    sku = context.skus[row.sku_id]
    expected = {
        (d, p) for d in ("inbound", "outbound") for p, s in sku[f"{d}_port_mix"].items() if s
    }
    if {(leg.direction, leg.port_id) for leg in row.legs} != expected or len(row.legs) != len(
        expected
    ):
        raise ValueError(f"{row.hu_id}: planning legs differ from the declared port mix")
    total = Fraction(0)
    for leg in row.legs:
        transport = transport_for(row.archetype_id, leg.route.graph)
        node = slot["cart_stop_id"] if leg.route.graph == "walk" else slot["vehicle"]
        port = context.ports[leg.port_id]
        ends = (port, node) if leg.direction == "inbound" else (node, port)
        route = exact_route(context.graphs, leg.route, transport=transport,
                            archetype=row.archetype_id, endpoints=ends)  # fmt: skip
        total += _moves(context, row, leg, periods) * route.length_m / context.speeds[transport]
    return total


def _planned(
    context: PlanningContext,
    transfer: TransferDoc,
    released: int | None,
    adapted: Fraction,
    periods: int,
) -> PlannedTransfer:
    access = context.facts.slots
    graph = "walk" if transfer.transport_tag == "manual_cart" else "vehicle"
    key = "cart_stop_id" if graph == "walk" else "vehicle"
    start, end = (
        access[transfer.from_slot_id]["access"][key],
        access[transfer.to_slot_id]["access"][key],
    )
    loaded = exact_route(context.graphs, transfer.loaded, transport=transfer.transport_tag,
                         archetype=transfer.archetype_id, endpoints=(start, end))  # fmt: skip
    reverse = exact_route(context.graphs, transfer.reverse, transport=transfer.transport_tag,
                          archetype=transfer.archetype_id, endpoints=(end, start))  # fmt: skip
    if set(loaded.arc_ids) & set(reverse.arc_ids):
        raise ValueError(f"{transfer.hu_id}: reverse route must use separate directed arcs")
    if transfer.handling_allowance_s != context.handling[transfer.transport_tag]:
        raise ValueError(f"{transfer.hu_id}: handling allowance differs from cost assumptions")
    speed = context.speeds[transfer.transport_tag]
    relocation = (loaded.length_m + reverse.length_m) / speed + transfer.handling_allowance_s
    gross = periods * context.h1_costs[transfer.hu_id] - adapted
    return PlannedTransfer(
        transfer.sequence,
        transfer.hu_id,
        transfer.archetype_id,
        transfer.from_slot_id,
        transfer.to_slot_id,
        transfer.transport_tag,
        loaded,
        reverse,
        relocation,
        gross,
        gross - relocation,
        released,
    )


def _evaluate(context: PlanningContext, plan: HorizonDoc) -> PlanningComparison:
    projection = Projection.start(context.facts)
    released = [projection.apply(t) for t in plan.transfers]
    rows = {row.hu_id: row for row in plan.rows}
    if {hu: row.slot_id for hu, row in rows.items()} != projection.slot_of:
        raise ValueError("adapted placements differ from the sequential planning projection")
    costs = {hu: _row_cost(context, row, plan.periods) for hu, row in rows.items()}
    moved = {t.hu_id for t in plan.transfers}
    if any(costs[hu] != plan.periods * context.h1_costs[hu] for hu in rows if hu not in moved):
        raise ValueError("an unmoved HU cost is not periods x its one-period cost")
    transfers = tuple(_planned(context, t, r, costs[t.hu_id], plan.periods)
                      for t, r in zip(plan.transfers, released, strict=True))  # fmt: skip
    if any(t.net_proxy_s <= 0 for t in transfers):
        raise ValueError("an accepted planning transfer has no positive net proxy saving")
    baseline = plan.periods * sum(context.h1_costs.values(), Fraction(0))
    adapted = sum(costs.values(), Fraction(0))
    relocation = sum((t.relocation_proxy_s for t in transfers), Fraction(0))
    result = PlanningComparison(
        plan.periods,
        PERIOD_UNIT,
        not transfers,
        transfers,
        baseline,
        adapted,
        relocation,
        baseline - adapted - relocation,
        inventory_totals(plan.rows, context.facts),
        plan.reported,
    )
    _check_diagnostics(result)
    return result


def _check_diagnostics(result: PlanningComparison) -> None:
    reported = result.reported
    pairs = (
        (result.baseline_proxy_s, reported.baseline_under_same_shifted_flow_cost_s),
        (result.adapted_proxy_s, reported.adapted_under_same_shifted_flow_cost_s),
        (result.relocation_proxy_s, reported.one_off_relocation_cost_s),
        (result.net_proxy_s, reported.net_transport_cost_reduction_s),
    )
    if any(abs(float(exact_value) - value) > DIAGNOSTIC_TOLERANCE for exact_value, value in pairs):
        raise ValueError("source-reported summary disagrees with the exact recomputation")


def plan_horizon(
    package: AdaptationPackage,
    periods: int,
    *,
    document: object | None = None,
    context: PlanningContext | None = None,
) -> PlanningComparison:
    """Evaluate one horizon on a fresh disposable projection; `document` overrides for review."""
    verify_package(package)
    verified_context = _context(package)
    if context is not None:
        require_same_authority(context, verified_context)
    source = package.horizon_document(periods) if document is None else document
    return _evaluate(verified_context, decode_horizon(source, periods))


@dataclass(frozen=True, slots=True)
class C11PlanningSet:
    source_revision: str
    comparisons: tuple[PlanningComparison, ...]
    comparison_inputs_sha256_verified: bool = False

    def horizon(self, periods: int) -> PlanningComparison:
        if type(periods) is not int or periods not in HORIZONS:
            raise ValueError("C11 comparison requires an exact supported integer period count")
        return next(c for c in self.comparisons if c.periods == periods)

    def as_json(self) -> dict[str, Any]:
        return {
            "source_revision": self.source_revision,
            "period_unit": PERIOD_UNIT,
            "actual_engine_run": False,
            "operational_admission": False,
            "comparison_inputs_sha256_verified": self.comparison_inputs_sha256_verified,
            "horizons": [comparison_json(c) for c in self.comparisons],
        }


def load_c11_planning(package_path: Path, base_path: Path) -> C11PlanningSet:
    package = load_adaptation_package(package_path, base_path)
    context = _context(package)
    comparisons = tuple(
        _evaluate(context, decode_horizon(package.horizon_document(p), p)) for p in HORIZONS
    )
    return C11PlanningSet(package.source_revision, comparisons)
