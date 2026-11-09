"""Authenticate original C10 stock independently of predicted offer volume."""

from pathlib import Path

from app.v3.adaptation_authority import require_same_authority
from app.v3.inputs import load_v3_bundle
from app.v3.offer_projection_models import OfferProjectionInputs
from app.v3.outbound_shift_models import BaselinePlacement
from app.v3.outbound_stock_models import StockHU
from app.v3.outbound_stock_source import _original_stock_from_bundle, _placements_from_bundle
from app.v3.workload_source import load_workload_source


def _original_stock(
    projection: OfferProjectionInputs,
) -> tuple[tuple[StockHU, ...], tuple[BaselinePlacement, ...]]:
    """Internal seam: caller has verified projection; independently reload original bytes."""
    root = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    bundle = load_v3_bundle(root)
    require_same_authority(projection.source, load_workload_source(bundle))
    require_same_authority(projection.initial_hus, bundle.handling_units)
    return _original_stock_from_bundle(bundle), _placements_from_bundle(bundle)
