"""An outer planning-to-execution identity; existing native N1 schemas stay unchanged."""

from dataclasses import dataclass

from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.relocation_pair_inputs import PreparedRelocationPair

VERSION = "qoima-forecast-relocation-inputs-0.1.0"
SCOPE = "forecast_selected_manual_relocation_on_separate_actual_common_inputs"


@dataclass(frozen=True, slots=True)
class ForecastRelocationChoices:
    job_id: str
    arrival_tick: int


@dataclass(frozen=True, slots=True)
class ForecastRelocationInputs:
    decision: ForecastPlacementDecision
    common_inputs: bytes
    choices: ForecastRelocationChoices
    pair: PreparedRelocationPair
    frozen_bytes: bytes
    input_hash: str
