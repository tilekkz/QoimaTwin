"""Additive KPI view for validated C outcomes; no runtime or publication-policy mutation."""

from app.v3.coordinator_metrics_belt import belt
from app.v3.coordinator_metrics_distance import distances
from app.v3.coordinator_metrics_inventory import inventory
from app.v3.coordinator_metrics_materials import materials
from app.v3.coordinator_metrics_queues import queues
from app.v3.coordinator_metrics_stations import stations
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.interface import Json

OBSERVED_KPI_VERSION = "qoima-coordinator-observed-kpi-proposal-1"


def observed_kpis(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> Json:
    return {
        "version": OBSERVED_KPI_VERSION,
        "travel": distances(profile, outcome, point),
        "stations": stations(profile, outcome, point),
        "additional_queues": queues(profile, outcome, point),
        "belt": belt(outcome, point),
        "inventory": inventory(profile, outcome, point),
        "materials": materials(profile, outcome, point),
    }
