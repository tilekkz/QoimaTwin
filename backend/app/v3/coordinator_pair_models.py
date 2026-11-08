"""Immutable paired evidence; scenario support never implies full warehouse acceptance."""

from dataclasses import dataclass
from typing import Any, Literal

from app.storage.canonical_json import parse_json
from app.v3.coordinator_profile import CompiledCoordinatorProfile

PAIR_VERSION = "qoima-coordinator-pair-0.1.0"
PairScenario = Literal["N0", "N4"]


class UnsupportedPairScenario(ValueError):
    """The requested scenario has no executable paired contract in this slice."""


class IncomparableCoordinatorPair(ValueError):
    """The proposed pair differs outside the authorized role plan or is not N0/N4."""


@dataclass(frozen=True, slots=True)
class PreparedCoordinatorPair:
    scenario: PairScenario
    baseline: CompiledCoordinatorProfile
    candidate: CompiledCoordinatorProfile
    common_input_hash: str


@dataclass(frozen=True, slots=True)
class CoordinatorPairResult:
    report_bytes: bytes
    baseline_run_bytes: bytes
    candidate_run_bytes: bytes
    baseline_inputs: bytes
    candidate_inputs: bytes

    @property
    def report(self) -> dict[str, Any]:
        return _object(self.report_bytes)

    @property
    def baseline_run(self) -> dict[str, Any]:
        return _object(self.baseline_run_bytes)

    @property
    def candidate_run(self) -> dict[str, Any]:
        return _object(self.candidate_run_bytes)


def _object(raw: bytes) -> dict[str, Any]:
    value = parse_json(raw)
    if not isinstance(value, dict):
        raise ValueError("Paired evidence must decode to an object")
    return value
