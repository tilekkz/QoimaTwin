"""Authenticate both worlds; map only the selected job without using actual future demand."""

from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.coordinator_profile import CompiledCoordinatorProfile, load_coordinator_inputs
from app.v3.flow_profile_wire import record
from app.v3.forecast_placement_decision import load_forecast_placement_decision
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.forecast_relocation_models import (
    SCOPE,
    VERSION,
    ForecastRelocationChoices,
    ForecastRelocationInputs,
)
from app.v3.materialize import number
from app.v3.outbound_placement_models import PlacementCandidate
from app.v3.outbound_placement_validation import buffer_choice
from app.v3.profile_models import BufferChoice
from app.v3.receipt_profile_geometry import _buffer
from app.v3.relocation_binding import bind_relocation_source
from app.v3.relocation_models import RelocationChoices, RelocationJob
from app.v3.relocation_pair_inputs import PreparedRelocationPair, prepare_relocation_pair
from app.v3.staff_registry_values import object_fields, text, tick
from app.v3.stock_models import UnitToken
from app.v3.stock_validation import require


def _choices(value: ForecastRelocationChoices) -> None:
    require(type(value) is ForecastRelocationChoices, "Exact forecast relocation choices required")
    text(value.job_id)
    tick(value.arrival_tick)


def _source(decision: ForecastPlacementDecision, common: CompiledCoordinatorProfile) -> None:
    source = decision.stock.projection.source
    flow = common.profile.world.receipts.flow
    require_same_authority(flow.source_revision, source.source_revision)
    hashes = dict(flow.source_hashes)
    require(all(name in hashes for name, _ in source.raw_fingerprints), "Missing common source pin")
    require_same_authority(
        tuple((name, hashes[name]) for name, _ in source.raw_fingerprints), source.raw_fingerprints
    )
    raw_source = parse_json(common.frozen_bytes)["source"]
    require_same_authority(raw_source["layout_content_hash"], source.layout_content_hash)
    require(
        common.horizon_tick == decision.stock.projection.choices.policy.horizon_tick,
        "Forecast and actual common horizon differ",
    )
    _stock(decision, common)


def _stock(decision: ForecastPlacementDecision, common: CompiledCoordinatorProfile) -> None:
    stock = common.profile.world.receipts.flow.stock
    containers = {c.container_id: c for c in stock.containers}
    units: dict[str, list[UnitToken]] = defaultdict(list)
    for unit in stock.units:
        units[unit.origin_hu].append(unit)
    original = decision.stock.original_stock
    require_same_authority(tuple(sorted(containers)), tuple(sorted(h.hu_id for h in original)))
    for hu in original:
        container, tokens = containers[hu.hu_id], units[hu.hu_id]
        actual = (
            container.owner_id,
            container.recipe.allowed_archetypes,
            tuple(sorted(u.unit_id for u in tokens)),
            len(tokens),
            container.recipe.tare_kg + sum((u.recipe.gross_mass_kg for u in tokens), Fraction(0)),
        )
        expected = (
            hu.initial_owner_id,
            (hu.archetype_id,),
            tuple(sorted(hu.unit_ids)),
            hu.quantity_units,
            hu.gross_mass_kg,
        )
        require_same_authority(actual, expected)
        require_same_authority(container.recipe.max_gross_kg, hu.gross_mass_kg)
        require(
            all((u.sku_id, u.lot_id) == (hu.sku_id, hu.lot_id) for u in tokens),
            "Original HU SKU/lot identity differs",
        )
    require_same_authority(
        tuple(sorted((p.hu_id, p.sku_id, p.slot_id) for p in decision.stock.initial_placements)),
        tuple(sorted((h.hu_id, h.sku_id, h.initial_owner_id) for h in original)),
    )


def _actor(candidate: PlacementCandidate, common: CompiledCoordinatorProfile) -> None:
    flow = common.profile.world.receipts.flow
    actors = [a for a in flow.actors if a.actor_id == candidate.actor.actor_id]
    require(len(actors) == 1, "Selected actor is absent from actual common inputs")
    actual, expected = actors[0], candidate.actor
    require_same_authority(
        (actual.actor_id, actual.home, actual.speed_m_s, actual.max_gross_kg),
        (expected.actor_id, expected.home_node_id, expected.speed_m_s, expected.max_gross_kg),
    )


def _customer(candidate: PlacementCandidate, common: CompiledCoordinatorProfile) -> None:
    customer = candidate.customer
    require(customer is not None, "Selected forecast customer binding is absent")
    assert customer is not None
    world = common.profile.world
    ports = [p for p in world.ports if p.port_id == customer.port_id]
    require(len(ports) == 1, "Actual common customer port configuration is absent")
    port = ports[0]
    require(candidate.actor.actor_id in port.shipper_ids, "Selected actor cannot serve common port")
    require_same_authority(
        (world.pickup_tick, world.place_tick), (customer.pickup_ticks, customer.place_ticks)
    )
    container = next(
        c for c in world.receipts.flow.stock.containers if c.container_id == candidate.hu_id
    )
    require_same_authority(
        dict(port.service_ticks).get(container.recipe.allowed_archetypes[0]), customer.service_ticks
    )
    wanted = buffer_choice(customer)
    require(wanted.place_id in port.buffer_ids, "Forecast buffer absent from common port")
    rows = parse_json(common.frozen_bytes)["choices"]["whole_buffers"]
    matching = [row for row in rows if row["owner_id"] == wanted.place_id]
    require(len(matching) == 1, "Common connector authority missing")
    require_same_authority(_buffer_facts(_buffer(matching[0])), _buffer_facts(wanted))


def _buffer_facts(value: BufferChoice) -> tuple[Any, ...]:
    return (
        value.place_id,
        value.port_id,
        value.zone_id,
        tuple(number(n, positive=False) for n in value.bounds_xz),
        tuple((number(x, positive=False), number(z, positive=False)) for x, z in value.path_xz),
        number(value.height_m),
        number(value.max_payload_kg),
    )


def _relocation_choices(
    decision: ForecastPlacementDecision,
    common: CompiledCoordinatorProfile,
    choices: ForecastRelocationChoices,
) -> RelocationChoices:
    selected, policy = decision.selected, decision.choices
    jobs: tuple[RelocationJob, ...] = ()
    if selected is not None:
        _actor(selected, common)
        _customer(selected, common)
        require_same_authority(
            common.profile.world.receipts.flow.path_clearance_m, policy.path_clearance_m
        )
        jobs = (
            RelocationJob(
                choices.job_id,
                choices.arrival_tick,
                selected.hu_id,
                selected.from_slot_id,
                selected.to_slot_id,
                selected.actor.actor_id,
                selected.take_ticks,
                selected.place_ticks,
            ),
        )
    return RelocationChoices(
        "forecast-selected-manual-relocation",
        "ADR0093; forecast provenance belongs to the outer input identity",
        jobs,
        policy.permitted_actor_ids,
        policy.route_policy,
        policy.min_width_m,
        policy.min_height_m,
    )


def _plans(decision: ForecastPlacementDecision, pair: PreparedRelocationPair) -> None:
    if decision.selected is None:
        return
    evaluations = [e for e in decision.evaluations if e.candidate == decision.selected]
    require(
        len(evaluations) == 1 and evaluations[0].cost is not None,
        "Selected evaluation is not uniquely priced",
    )
    cost = evaluations[0].cost
    assert cost is not None
    require(len(pair.candidate.plans) == 1, "Selected relocation must have one admitted plan")
    expected = tuple((op.kind, op.ticks, op.route) for op in cost.relocation)
    actual = tuple((step.kind, step.duration, step.route) for step in pair.candidate.plans[0].steps)
    require_same_authority(actual, expected)


def _wire(value: ForecastRelocationInputs) -> dict[str, Any]:
    decision, pair = value.decision, value.pair
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "forecast_id": decision.forecast_id,
        "projection_id": decision.projection_id,
        "stock_input_hash": decision.stock_input_hash,
        "decision_hash": decision.input_hash,
        "common_input_hash": sha256(value.common_inputs).hexdigest(),
        "pair_input_hash": pair.input_hash,
        "choices": record(value.choices),
        "decision_inputs": parse_json(decision.frozen_bytes),
        "common_inputs": parse_json(value.common_inputs),
        "pair_inputs": parse_json(pair.frozen_bytes),
        "full_n1_acceptance": False,
        "operational_admission": False,
    }


def prepare_forecast_relocation(
    decision_bytes: bytes, common_inputs: bytes, choices: ForecastRelocationChoices
) -> ForecastRelocationInputs:
    _choices(choices)
    require(
        type(decision_bytes) is bytes and type(common_inputs) is bytes,
        "Exact immutable decision and common bytes required",
    )
    decision = load_forecast_placement_decision(decision_bytes)
    common = load_coordinator_inputs(common_inputs)
    _source(decision, common)
    candidate_choices = _relocation_choices(decision, common, choices)
    baseline = bind_relocation_source(common_inputs, replace(candidate_choices, jobs=()))
    candidate = bind_relocation_source(common_inputs, candidate_choices)
    pair = prepare_relocation_pair(baseline, candidate, scenario="N1")
    _plans(decision, pair)
    value = ForecastRelocationInputs(decision, common_inputs, choices, pair, b"", "")
    raw = canonical_bytes(_wire(value))
    return replace(value, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def load_forecast_relocation(raw: bytes) -> ForecastRelocationInputs:
    require(type(raw) is bytes, "Exact immutable forecast relocation bytes required")
    value = object_fields(
        parse_json(raw),
        "schema_version scope forecast_id projection_id stock_input_hash "
        "decision_hash common_input_hash pair_input_hash choices decision_inputs "
        "common_inputs pair_inputs full_n1_acceptance operational_admission",
    )
    require(
        value["schema_version"] == VERSION and value["scope"] == SCOPE,
        "Unsupported forecast relocation namespace",
    )
    fields = object_fields(value["choices"], "job_id arrival_tick")
    expected = prepare_forecast_relocation(
        canonical_bytes(value["decision_inputs"]),
        canonical_bytes(value["common_inputs"]),
        ForecastRelocationChoices(**fields),
    )
    require(
        expected.frozen_bytes == raw, "Forecast relocation differs from reconstructed authority"
    )
    return expected


def verify_forecast_relocation(value: ForecastRelocationInputs) -> ForecastRelocationInputs:
    require(type(value) is ForecastRelocationInputs, "Exact ForecastRelocationInputs required")
    expected = load_forecast_relocation(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
