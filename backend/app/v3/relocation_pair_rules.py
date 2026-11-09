"""N1 permits relocation job changes only, independently of any measured benefit."""

from dataclasses import replace
from typing import Literal

from app.v3.adaptation_authority import require_same_authority
from app.v3.relocation_models import BoundRelocation
from app.v3.relocation_run_inputs import HandRelocationInputs


class IncomparableRelocationPair(ValueError):
    """The supplied arms do not represent the same offered N1 world."""


def scenario_name(value: object) -> Literal["N1"]:
    if type(value) is not str or value != "N1":
        raise IncomparableRelocationPair("UNSUPPORTED_RELOCATION_PAIR_SCENARIO")
    return "N1"


def input_family(inputs: BoundRelocation) -> Literal["source_bound", "analytical"]:
    if type(inputs) is BoundRelocation:
        return "source_bound"
    if type(inputs) is HandRelocationInputs:
        return "analytical"
    raise IncomparableRelocationPair("EXACT_RELOCATION_PAIR_INPUT_FAMILY_REQUIRED")


def require_same_family(baseline: BoundRelocation, candidate: BoundRelocation) -> None:
    if input_family(baseline) != input_family(candidate):
        raise IncomparableRelocationPair("RELOCATION_PAIR_INPUT_FAMILY_MISMATCH")


def require_n1_pair(baseline: BoundRelocation, candidate: BoundRelocation) -> None:
    """Both retained inputs must already have passed independent run-input verification."""
    require_same_family(baseline, candidate)
    if baseline.choices.jobs:
        raise IncomparableRelocationPair("N1_BASELINE_RELOCATION_JOBS_MUST_BE_EMPTY")
    if len(candidate.choices.jobs) > 1:
        raise IncomparableRelocationPair("N1_CANDIDATE_RELOCATION_JOB_LIMIT")
    if baseline.common_inputs != candidate.common_inputs:
        raise IncomparableRelocationPair("N1_COMMON_INPUT_BYTES_DIFFER")
    _same(
        replace(baseline.choices, jobs=()),
        replace(candidate.choices, jobs=()),
        "N1_NONJOB_CHOICES_DIFFER",
    )
    _same(baseline.profile.places, candidate.profile.places, "N1_PLACES_DIFFER")


def _same(left: object, right: object, code: str) -> None:
    try:
        require_same_authority(left, right)
    except ValueError as exc:
        raise IncomparableRelocationPair(code) from exc
