"""Planning transport identities are distinct from actual execution and CPU observations."""

from dataclasses import dataclass
from pathlib import Path

from app.v3.forecast_placement_models import VERSION as DECISION_VERSION
from app.v3.forecast_stock_models import VERSION as STOCK_VERSION
from app.v3.offer_forecast_models import FLOAT_POLICY, FORECAST_VERSION, TEMPORAL_POLICY
from app.v3.offer_history_models import HISTORY_VERSION, OfferHistoryChoices
from app.v3.offer_projection_models import VERSION as PROJECTION_VERSION
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.outbound_placement_models import PlacementChoices

VERSION = "qoima-offer-planning-bundle-0.1.0"
REQUEST_VERSION = "qoima-offer-planning-request-0.1.0"
RAW_NAMES = (
    "history.csv",
    "history-choices.json",
    "projection-choices.json",
    "placement-choices.json",
)
STAGES = ("history", "forecast", "projection", "stock", "decision")
REQUEST_FIELDS = {
    "version",
    "model",
    "producer_versions",
    "raw_inputs",
    "operational_admission",
    "actual_test_stream",
}
SEMANTIC_FIELDS = {
    "request",
    "artifacts",
    "producer_versions",
    "plan_id",
    "status",
    "selection_reason",
    "unallocated_offers",
    "engine_calls",
    "operational_admission",
    "actual_test_stream",
    "full_n1_acceptance",
}


@dataclass(frozen=True, slots=True)
class PlanningFiles:
    history: Path
    history_choices: Path
    projection_choices: Path
    placement_choices: Path


@dataclass(frozen=True, slots=True)
class PlanningChoices:
    history: OfferHistoryChoices
    projection: OfferProjectionChoices
    placement: PlacementChoices


def versions() -> dict[str, str]:
    return {
        "history": HISTORY_VERSION,
        "forecast": FORECAST_VERSION,
        "projection": PROJECTION_VERSION,
        "stock": STOCK_VERSION,
        "decision": DECISION_VERSION,
        "temporal_policy": TEMPORAL_POLICY,
        "float_policy": FLOAT_POLICY,
    }
