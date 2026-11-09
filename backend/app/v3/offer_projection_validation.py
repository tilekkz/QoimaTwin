"""Exact signal, explicit clock and complete source-permitted port composition."""

from collections.abc import Mapping
from fractions import Fraction

from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.workload_allocation import validate_weights
from app.v3.workload_models import DemandWeight, WorkloadSource
from app.v3.workload_policy import validate_policy
from app.v3.workload_validation import name


def _mix_mode(value: object) -> None:
    if type(value) is not str or value not in {"source_c10", "explicit"}:
        raise ValueError("EXPLICIT_PORT_MIX_MODE_REQUIRED")


def validate_choices(choices: OfferProjectionChoices) -> None:
    if type(choices) is not OfferProjectionChoices:
        raise ValueError("EXACT_OFFER_PROJECTION_CHOICES_REQUIRED")
    validate_policy(choices.policy)
    if choices.policy.inbound_hus != 0:
        raise ValueError("P0_REQUIRES_EXPLICIT_ZERO_INBOUND_BUDGET")
    _mix_mode(choices.port_mix_mode)
    validate_weights(choices.port_mix, 0)
    if any(type(row) is not DemandWeight for row in choices.port_mix):
        raise ValueError("EXACT_PORT_MIX_ROWS_REQUIRED")
    if choices.port_mix_mode == "source_c10" and choices.port_mix:
        raise ValueError("SOURCE_MIX_DOES_NOT_ACCEPT_OVERRIDES")


def validate_predictions(
    predictions: tuple[tuple[str, Fraction], ...], source: WorkloadSource
) -> dict[str, Fraction]:
    if type(predictions) is not tuple:
        raise ValueError("IMMUTABLE_PREDICTIONS_REQUIRED")
    result: dict[str, Fraction] = {}
    for row in predictions:
        if type(row) is not tuple or len(row) != 2:
            raise ValueError("EXACT_PREDICTION_ROW_REQUIRED")
        sku, weight = row
        name(sku)
        if type(weight) is not Fraction or weight < 0 or sku in result:
            raise ValueError("UNIQUE_NONNEGATIVE_EXACT_PREDICTIONS_REQUIRED")
        result[sku] = weight
    if result.keys() != {template.sku_id for template in source.templates}:
        raise ValueError("PREDICTIONS_MUST_RETAIN_EVERY_SOURCE_SKU")
    return result


def _permitted_pairs(
    source: WorkloadSource, ports: Mapping[str, frozenset[str]]
) -> set[tuple[str, str]]:
    for port, classes in ports.items():
        name(port)
        if type(classes) is not frozenset:
            raise ValueError("EXACT_PORT_CARGO_PERMISSIONS_REQUIRED")
        for cargo in classes:
            name(cargo)
    pairs = {
        (template.sku_id, port)
        for template in source.templates
        for port, classes in ports.items()
        if template.archetype_id in classes
    }
    if {sku for sku, _ in pairs} != {t.sku_id for t in source.templates}:
        raise ValueError("SOURCE_SKU_HAS_NO_PERMITTED_OUTGOING_PORT")
    return pairs


def resolve_mix(
    source: WorkloadSource,
    choices: OfferProjectionChoices,
    ports: Mapping[str, frozenset[str]],
) -> tuple[DemandWeight, ...]:
    pairs = _permitted_pairs(source, ports)
    if not {(r.sku_id, r.port_id) for r in source.outbound_weights} <= pairs:
        raise ValueError("SOURCE_OUTBOUND_MIX_CONFLICTS_WITH_PORT_RIGHTS")
    rows = choices.port_mix
    if choices.port_mix_mode == "source_c10":
        old = {(r.sku_id, r.port_id): r.weight for r in source.outbound_weights}
        totals = {
            sku: sum((v for (key, _), v in old.items() if key == sku), Fraction(0))
            for sku, _ in pairs
        }
        if any(total <= 0 for total in totals.values()):
            raise ValueError("SOURCE_PORT_MIX_HAS_NO_DECLARED_POSITIVE_TOTAL")
        rows = tuple(
            DemandWeight(sku, port, old.get((sku, port), Fraction(0)) / totals[sku])
            for sku, port in sorted(pairs)
        )
    if {(r.sku_id, r.port_id) for r in rows} != pairs:
        raise ValueError("MIX_MUST_COVER_EXACT_SOURCE_PERMITTED_SKU_PORT_PAIRS")
    for sku in {t.sku_id for t in source.templates}:
        if sum((r.weight for r in rows if r.sku_id == sku), Fraction(0)) != 1:
            raise ValueError("PORT_SHARES_MUST_SUM_TO_ONE_PER_SKU")
    return tuple(sorted(rows, key=lambda r: (r.sku_id, r.port_id)))
