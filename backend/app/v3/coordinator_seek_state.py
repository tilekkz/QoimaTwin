"""Immutable arbitrary-cut projection of one native journal; no new motion model."""

from app.v3.belt_state import snapshot as belt_snapshot
from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run_role_exposure import actor_roles, exposure
from app.v3.coordinator_run_validation import Journal
from app.v3.light_flow_models import FlowCartView


def _leases(journal: Journal) -> tuple[tuple[str, str], ...]:
    values = {**journal.resources.leases, **journal.roles.leases()}
    multiple = journal.inventory.profile.unit_resources is not None
    for cart, order in journal.motion.cart_orders.items():
        values["cart:" + cart if multiple else "cart"] = order
    return tuple(sorted(values.items())) + tuple(sorted(journal.belt.external.items()))


def snapshot(journal: Journal, tick: int, last_seq: int) -> CoordinatorSnapshot:
    profile, units = journal.inventory.profile, journal.units
    roles = tuple(journal.roles.views[key] for key in sorted(journal.roles.views))
    carts = tuple(
        FlowCartView(key, cart.node, cart.operation, journal.motion.cart_orders.get(key))
        for key, cart in sorted(journal.motion.carts.items())
    )
    bindings = tuple(
        sorted(
            (r.station_id, r.actor_id)
            for r in roles
            if r.status in {"outward", "active", "return_wait"}
        )
    )
    ledger, belt = journal.inventory.ledger, journal.belt
    return CoordinatorSnapshot(
        tick=tick,
        stock=ledger.snapshot(),
        balance=ledger.balance(),
        workers=tuple(w.view(tick) for _, w in sorted(journal.motion.workers.items())),
        orders=tuple(units.orders[key] for key in sorted(units.orders)),
        leases=_leases(journal),
        belt=belt_snapshot(belt.source, tuple(belt.states.values()), belt.leases, tick),
        last_seq=last_seq,
        cart=next(c for c in carts if c.cart_id == profile.world.receipts.flow.cart.cart_id),
        inventory=ledger.inventory_snapshot(),
        receipts=tuple(s.view(tick) for _, s in sorted(journal.goods.receipts.items())),
        whole_orders=tuple(s.view(tick) for _, s in sorted(journal.goods.whole.items())),
        roles=roles,
        actor_roles=actor_roles(profile, roles, tick),
        role_bindings=bindings,
        exposure=exposure(profile, roles, tick),
        unit_contexts=tuple(units.contexts[key] for key in sorted(units.contexts)),
        packing=tuple(units.packing[key] for key in sorted(units.packing)),
        packing_waits=tuple(sorted(units.waits.items())),
        carts=carts,
        cart_releases=tuple(
            (key, value)
            for (key, kind), value in sorted(units.marks.items())
            if kind == "cart_released"
        ),
        unit_progress=units.progress(),
    )
