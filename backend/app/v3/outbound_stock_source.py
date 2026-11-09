"""Fresh pinned original HU, lot, unit and owner identities; no mutable stock ledger."""

from collections import defaultdict
from pathlib import Path

from app.v3.adaptation_authority import require_same_authority
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.outbound_shift_models import BaselinePlacement, OutboundShiftInputs
from app.v3.outbound_stock_models import StockHU
from app.v3.stock_source import source_seed
from app.v3.workload_source import load_workload_source


def _base_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "v3-proposal"


def original_stock(inputs: OutboundShiftInputs) -> tuple[StockHU, ...]:
    bundle = load_v3_bundle(_base_root())
    require_same_authority(inputs.scenario.baseline, load_workload_source(bundle))
    require_same_authority(inputs.scenario.initial_placements, _placements_from_bundle(bundle))
    return _original_stock_from_bundle(bundle)


def _placements_from_bundle(bundle: V3Bundle) -> tuple[BaselinePlacement, ...]:
    """Project immutable values from a bundle already authenticated by the caller."""
    return tuple(
        BaselinePlacement(hu.handling_unit_id, hu.sku_id, hu.slot_id, hu.module_id)
        for hu in sorted(bundle.handling_units, key=lambda hu: hu.handling_unit_id)
    )


def _original_stock_from_bundle(bundle: V3Bundle) -> tuple[StockHU, ...]:
    """Pure original-seed builder; the caller must establish fresh bundle authority."""
    hus = sorted(bundle.handling_units, key=lambda hu: hu.handling_unit_id)
    seed = source_seed(bundle)
    containers = {hu.container_id: hu for hu in seed.containers}
    tokens: dict[str, list[str]] = defaultdict(list)
    for token in seed.units:
        tokens[token.origin_hu].append(token.unit_id)
    return tuple(
        StockHU(
            hu.handling_unit_id,
            hu.sku_id,
            hu.archetype_id,
            hu.lot_id,
            tuple(tokens[hu.handling_unit_id]),
            hu.quantity_units,
            containers[hu.handling_unit_id].recipe.max_gross_kg,
            hu.slot_id,
            None,
            None,
        )
        for hu in hus
    )
