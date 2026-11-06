"""Fail-fast checks of the settled mutable state (ADR 0003, 0005, 0006)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.engine import Engine

TOTE_IDS = frozenset(f"T{i:03d}" for i in range(1, 97))


class InvariantViolation(RuntimeError):
    """A settled state violates stock, ownership or finite capacity constraints."""


def check_invariants(engine: Engine) -> None:
    """Check independently tracked pools; reservations never add physical stock."""
    issues = engine.ctx.ledger.check_conservation()
    issues.extend(_totes(engine))
    issues.extend(_cells(engine))
    issues.extend(_capacities(engine))
    issues.extend(_pallets(engine))
    if issues:
        raise InvariantViolation(f"tick={engine.ctx.now}: " + "; ".join(issues))


def _totes(engine: Engine) -> list[str]:
    free = engine.picking.free_totes
    allocated = engine.picking.allocated_totes
    if len(set(free)) != len(free):
        return ["duplicate free tote"]
    if set(free) & allocated:
        return ["free and allocated tote pools overlap"]
    if set(free) | allocated != TOTE_IDS:
        return ["tote pool must contain exactly T001..T096"]
    return []


def _cells(engine: Engine) -> list[str]:
    occupancy = engine.conveyor.occupancy
    issues = []
    # A mapping enforces at most one occupant per cell; also prohibit cargo cloning.
    if len(set(occupancy.values())) != len(occupancy):
        issues.append("cargo occupies more than one cell")
    if any(cell not in engine.ctx.topology.successors for cell in occupancy):
        issues.append("occupancy references an unknown cell")
    if any(cargo not in engine.conveyor.cargo for cargo in occupancy.values()):
        issues.append("cell occupant is absent from the cargo registry")
    return issues


def _capacities(engine: Engine) -> list[str]:
    config = engine.ctx.config
    limits = [
        ("shipping", len(engine.shipping.buffer), config.shipping_buffer_capacity),
        ("sealed", len(engine.shipping.sealed_queue), config.sealed_pallet_queue_capacity),
        ("receiving", len(engine.receiving.area), config.receiving_queue_capacity),
        ("reserve", engine.receiving.staging_used, config.reserve_staging_capacity),
    ]
    issues = []
    for station in engine.packing.stations.values():
        limits.append((station.pack_id, len(station.waiting), station.capacity))
        if station.reserved_wip < 0:
            issues.append(f"{station.pack_id}: reserved_wip is negative")
    for name, count, limit in limits:
        if not 0 <= count <= limit:
            issues.append(f"{name}: capacity {limit}, found {count}")
    return issues


def _pallets(engine: Engine) -> list[str]:
    pallets = [*engine.shipping.sealed_queue, *engine.outbound.tasks]
    if engine.shipping.open_pallet is not None:
        pallets.append(engine.shipping.open_pallet)
    if engine.outbound.current_pallet is not None:
        pallets.append(engine.outbound.current_pallet)
    return [
        f"pallet {p.pallet_id}: invalid placed/reserved slots"
        for p in {p.pallet_id: p for p in pallets}.values()
        if p.reserved < 0 or len(p.parcels) + p.reserved > engine.shipping.capacity
    ]
