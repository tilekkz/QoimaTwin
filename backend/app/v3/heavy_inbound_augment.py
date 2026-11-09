"""Pure finite augmentation usable by hand tests; never authenticates source authority."""

from collections.abc import Mapping
from fractions import Fraction

from app.v3.adaptation_authority import require_same_authority
from app.v3.heavy_inbound_models import (
    BoundHeavyReceipt,
    HeavyInboundAugmentation,
    HeavyInboundDelta,
    HeavyInboundReceipt,
)
from app.v3.heavy_inbound_validation import bind_receipt, identity_registry, validate_additions
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload


def _deltas(
    baseline: TimedWorkload, receipts: tuple[BoundHeavyReceipt, ...]
) -> tuple[HeavyInboundDelta, ...]:
    keys = sorted({(r.offer.archetype_id, r.offer.port_id) for r in receipts})
    results = []
    for archetype, port in keys:
        before = sum(
            j.direction == "inbound" and j.archetype_id == archetype and j.port_id == port
            for j in baseline.jobs
        )
        added = [
            r for r in receipts if (r.offer.archetype_id, r.offer.port_id) == (archetype, port)
        ]
        mass = sum((r.template.gross_mass_kg for r in added), Fraction(0))
        results.append(
            HeavyInboundDelta(archetype, port, before, len(added), before + len(added), mass)
        )
    return tuple(results)


def augment_offers(
    baseline: TimedWorkload,
    additions: tuple[HeavyInboundReceipt, ...],
    inbound_ports: Mapping[str, frozenset[str]],
) -> HeavyInboundAugmentation:
    """Validate an analytical baseline and add rows; caller source facts remain untrusted."""
    if type(baseline) is not TimedWorkload:
        raise ValueError("EXACT_BASELINE_WORKLOAD_REQUIRED")
    require_same_authority(baseline, materialize_workload(baseline.source, baseline.policy))
    validate_additions(additions, baseline.policy.horizon_tick)
    occupied, lots = identity_registry(baseline)
    templates = {t.sku_id: t for t in baseline.source.templates}
    receipts = []
    for row in sorted(additions, key=lambda r: r.job_id):
        template = templates.get(row.sku_id)
        if template is None:
            raise ValueError("UNKNOWN_HEAVY_RECEIPT_SOURCE_SKU")
        receipts.append(bind_receipt(row, template, inbound_ports, occupied, lots))
    bound = tuple(receipts)
    jobs = tuple(
        sorted(
            (*baseline.jobs, *(r.offer for r in bound)),
            key=lambda j: (j.arrival_tick, j.direction, j.job_id),
        )
    )
    return HeavyInboundAugmentation(bound, _deltas(baseline, bound), jobs)
