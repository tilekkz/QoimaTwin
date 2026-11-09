"""Private request-owned native facts; never a public admission token or shared cache."""

from dataclasses import dataclass

from app.storage.canonical_json import parse_json
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run_inputs import RunInputs
from app.v3.interface import Json


@dataclass(frozen=True, slots=True)
class _NativeReadContext:
    run_bytes: bytes
    inputs: RunInputs
    outcome: CoordinatorOutcome

    def run(self) -> Json:
        """Return a detached view of the one canonically validated native snapshot."""
        return dict(parse_json(self.run_bytes))
