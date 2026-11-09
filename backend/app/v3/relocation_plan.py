"""Pure five-step plans retain original unit identities and pay the complete return."""

from fractions import Fraction as F

from app.v3.light_flow_models import FlowActor
from app.v3.light_flow_state import HumanStep
from app.v3.relocation_capacity import validate_capacity
from app.v3.relocation_models import (
    RelocationChoices,
    RelocationJob,
    RelocationPlace,
    RelocationPlan,
    RelocationProfile,
)
from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_time import operation_ticks
from app.v3.staff_registry_values import text, tick, typed_tuple
from app.v3.stock_models import Container, ContainerRecipe, StockSeed, UnitToken
from app.v3.stock_validation import (
    exact,
    require,
    validate_container,
    validate_seed,
    validate_unit,
    vector,
)
from app.v3.whole_profile_geometry import ROUTE_POLICY


def validate_choices(choices: RelocationChoices) -> None:
    require(type(choices) is RelocationChoices, "Exact relocation choices required")
    text(choices.profile_id)
    text(choices.provenance)
    typed_tuple(choices.jobs, RelocationJob)
    require(len(choices.jobs) <= 1, "Relocation supports zero or one job")
    require(type(choices.permitted_actor_ids) is tuple, "Exact permission tuple required")
    for actor in choices.permitted_actor_ids:
        require(text(actor) in {"S01", "S02"}, "Only existing S01/S02 relocation permission")
    require(
        len(set(choices.permitted_actor_ids)) == len(choices.permitted_actor_ids),
        "Duplicate permission",
    )
    require(choices.route_policy == ROUTE_POLICY, "Explicit manual route policy required")
    exact(choices.min_width_m, positive=True)
    exact(choices.min_height_m, positive=True)
    for job in choices.jobs:
        for value in (job.job_id, job.hu_id, job.from_slot_id, job.to_slot_id, job.actor_id):
            text(value)
        tick(job.arrival_tick)
        require(tick(job.take_ticks) > 0 and tick(job.place_ticks) > 0, "Positive handling ticks")
        require(job.actor_id in choices.permitted_actor_ids, "Explicit relocation actor permission")
        require(job.from_slot_id != job.to_slot_id, "Distinct relocation addresses required")


def plan_relocations(profile: RelocationProfile) -> tuple[RelocationPlan, ...]:
    require(type(profile) is RelocationProfile, "Exact relocation profile required")
    validate_choices(
        RelocationChoices(
            profile.profile_id,
            profile.provenance,
            profile.jobs,
            profile.permitted_actor_ids,
            profile.route_policy,
            profile.min_width_m,
            profile.min_height_m,
        )
    )
    typed_tuple(profile.places, RelocationPlace)
    require(
        len({p.owner_id for p in profile.places}) == len(profile.places),
        "Duplicate relocation place",
    )
    for place in profile.places:
        _place_types(place)
    return tuple(_plan(profile, job) for job in profile.jobs)


def _place_types(place: RelocationPlace) -> None:
    for value in (place.owner_id, place.module_id, place.node_id):
        text(value)
    vector(place.dimensions)
    exact(place.max_gross_kg, positive=True)
    exact(place.clearance_m)
    exact(place.module_max_gross_kg, positive=True)
    require(type(place.module_max_hus) is int and place.module_max_hus > 0, "Module HU capacity")


def _work_ids(profile: RelocationProfile, job: RelocationJob) -> None:
    common = profile.coordinator
    flow = common.world.receipts.flow
    ids = {x.order_id for x in flow.orders} | {x.job_id for x in common.world.orders}
    ids |= {x.definition.receipt_id for x in common.world.receipts.receipts}
    ids |= {x.intent_id for x in common.intents}
    require(job.job_id not in ids, "Relocation work identity overlaps existing work")
    require(
        not any(x.source_hu == job.hu_id for x in flow.orders),
        "N1 unit-order HU overlap unsupported",
    )
    require(
        job.to_slot_id not in {r.slot_owner_id for r in common.world.receipts.receipts},
        "Relocation destination reserved for receipt",
    )


def _actor(profile: RelocationProfile, job: RelocationJob) -> FlowActor:
    matches = [
        a for a in profile.coordinator.world.receipts.flow.actors if a.actor_id == job.actor_id
    ]
    require(len(matches) == 1 and type(matches[0]) is FlowActor, "Unique existing actor required")
    actor = matches[0]
    text(actor.home)
    exact(actor.speed_m_s, positive=True)
    exact(actor.max_gross_kg, positive=True)
    tick(actor.available_tick)
    workers = [w for w in profile.coordinator.registry.workers if w.actor_id == job.actor_id]
    require(
        len(workers) == 1 and "ship" in workers[0].eligible_roles,
        "Declared ship capability required",
    )
    return actor


def _original(
    profile: RelocationProfile, job: RelocationJob
) -> tuple[Container, tuple[UnitToken, ...], F]:
    stock = profile.coordinator.world.receipts.flow.stock
    matches = [c for c in stock.containers if c.container_id == job.hu_id]
    require(
        len(matches) == 1 and type(matches[0]) is Container, "Unique original source HU required"
    )
    container = matches[0]
    require(container.owner_id == job.from_slot_id, "Original HU source binding mismatch")
    units = tuple(u for u in stock.units if u.origin_hu == job.hu_id)
    typed_tuple(units, UnitToken)
    owners = {o.owner_id: o for o in stock.owners}
    validate_container(container, owners)
    for unit in units:
        validate_unit(unit, {job.hu_id: container})
    validate_seed(StockSeed(units, (container,), stock.owners), {job.hu_id: container}, owners)
    require(
        container.recipe.allowed_archetypes in (("SMALL_CARTON",), ("STANDARD_CARTON",)),
        "Manual SMALL/STANDARD HU only",
    )
    require(
        len({u.unit_id for u in units}) == len(units), "Unique original unit identities required"
    )
    mass = container.recipe.tare_kg + sum((u.recipe.gross_mass_kg for u in units), F(0))
    require(mass == container.recipe.max_gross_kg, "Intact original HU mass required")
    return container, tuple(sorted(units, key=lambda u: u.ordinal)), mass


def _places(
    profile: RelocationProfile, job: RelocationJob, cargo: ContainerRecipe
) -> tuple[RelocationPlace, RelocationPlace]:
    places = {p.owner_id: p for p in profile.places}
    require(
        job.from_slot_id in places and job.to_slot_id in places, "Bound relocation places required"
    )
    source, target = places[job.from_slot_id], places[job.to_slot_id]
    stock = profile.coordinator.world.receipts.flow.stock
    owners = {o.owner_id: o for o in stock.owners}
    for place in (source, target):
        require(
            place.owner_id in owners
            and owners[place.owner_id].kind == "slot"
            and owners[place.owner_id].capacity == 1,
            "Exclusive source slot owner required",
        )
        require(cargo.max_gross_kg <= place.max_gross_kg, "Relocation slot payload")
        require(
            all(
                size + 2 * place.clearance_m <= room
                for size, room in zip(cargo.outer, place.dimensions, strict=True)
            ),
            "Relocation slot dimensions",
        )
    require(
        not any(c.owner_id == target.owner_id for c in stock.containers),
        "Relocation destination occupied",
    )
    return source, target


def _travel(
    profile: RelocationProfile,
    actor: FlowActor,
    job: RelocationJob,
    cargo: ContainerRecipe,
    start: str,
    end: str,
    kind: str,
    *,
    loaded: bool,
) -> HumanStep:
    flow = profile.coordinator.world.receipts.flow
    margin = flow.path_clearance_m
    require(margin is not None, "Explicit relocation path clearance required")
    assert margin is not None
    exact(margin)
    requirements = RouteRequirements(
        mode="pedestrian",
        cargo=cargo.allowed_archetypes[0] if loaded else None,
        min_clear_width_m=max(profile.min_width_m, cargo.outer[0] + 2 * margin)
        if loaded
        else profile.min_width_m,
        min_clear_height_m=max(profile.min_height_m, cargo.outer[1] + margin)
        if loaded
        else profile.min_height_m,
    )
    route = flow.graph.shortest_path(start, end, requirements)
    require(route is not None, "Missing directed relocation route")
    assert route is not None
    return HumanStep(
        kind,
        end,
        operation_ticks(route.length_m / actor.speed_m_s),
        route,
        job.hu_id if loaded else None,
    )


def _plan(profile: RelocationProfile, job: RelocationJob) -> RelocationPlan:
    _work_ids(profile, job)
    actor = _actor(profile, job)
    container, units, mass = _original(profile, job)
    require(mass <= min(F(15), actor.max_gross_kg), "Relocation manual/actor mass limit")
    source, target = _places(profile, job, container.recipe)
    validate_capacity(profile, source, target, mass)
    return RelocationPlan(
        job,
        actor,
        source,
        target,
        container.recipe,
        tuple(u.unit_id for u in units),
        units[0].sku_id,
        units[0].lot_id,
        mass,
        _steps(profile, job, actor, source, target, container.recipe),
    )


def _steps(
    profile: RelocationProfile,
    job: RelocationJob,
    actor: FlowActor,
    source: RelocationPlace,
    target: RelocationPlace,
    cargo: ContainerRecipe,
) -> tuple[HumanStep, ...]:
    return (
        _travel(
            profile,
            actor,
            job,
            cargo,
            actor.home,
            source.node_id,
            "relocation_approach",
            loaded=False,
        ),
        HumanStep("relocation_take", source.node_id, job.take_ticks, carrying_id=job.hu_id),
        _travel(
            profile,
            actor,
            job,
            cargo,
            source.node_id,
            target.node_id,
            "relocation_carry",
            loaded=True,
        ),
        HumanStep("relocation_place", target.node_id, job.place_ticks, carrying_id=job.hu_id),
        _travel(
            profile,
            actor,
            job,
            cargo,
            target.node_id,
            actor.home,
            "relocation_return",
            loaded=False,
        ),
    )
