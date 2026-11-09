"""Exact fixed calendar materialization, always completed before engine creation."""

import re
from fractions import Fraction

from app.v3.execution_types import TimedJob
from app.v3.profile_models import ManualProposal
from app.v3.runtime_time import operation_ticks

# Plain JSON-style decimal text: no fractions, underscores, whitespace or leading plus.
# The exponent is bounded so proposal text cannot force a huge exact integer.
DECIMAL_TEXT = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]{1,3})?")


def number(value: str, *, positive: bool = True) -> Fraction:
    if not isinstance(value, str) or DECIMAL_TEXT.fullmatch(value) is None:
        raise ValueError("synthetic numeric choice must be finite exact decimal text")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("synthetic numeric choice must be finite exact decimal text") from exc
    if result < 0 or (positive and result == 0):
        raise ValueError("synthetic numeric choice has invalid sign")
    return result


def calendar_tick(seconds: str) -> int:
    return operation_ticks(number(seconds, positive=False))


def materialize_jobs(proposal: ManualProposal) -> tuple[TimedJob, ...]:
    if proposal.calendar_policy != "fixed-explicit-arrivals-v1":
        raise ValueError("unknown calendar policy; no rate or RNG inference")
    if not 0 < proposal.horizon_tick <= proposal.end_tick:
        raise ValueError("require positive H and end >= H")
    for job in proposal.jobs:
        if any(not v.strip() for v in (job.job_id, job.hu_id, job.port_id, job.slot_id)):
            raise ValueError("job identifiers must be nonempty")
    jobs = tuple(
        TimedJob(
            j.job_id, calendar_tick(j.arrival_seconds), j.direction, j.hu_id, j.port_id, j.slot_id
        )
        for j in proposal.jobs
    )
    if len({j.job_id for j in jobs}) != len(jobs):
        raise ValueError("duplicate timed job ID")
    _chains(jobs)
    if any(j.arrival_tick >= proposal.horizon_tick for j in jobs):
        raise ValueError("arrival must precede frozen H")
    return tuple(sorted(jobs, key=lambda j: (j.arrival_tick, j.job_id)))


def _chains(jobs: tuple[TimedJob, ...]) -> None:
    """One job per HU and direction; a received HU may ship at or after its receipt tick."""
    by_direction: dict[tuple[str, str], TimedJob] = {}
    for job in jobs:
        if (job.hu_id, job.direction) in by_direction:
            raise ValueError("duplicate job: requires unique HU per direction")
        by_direction[job.hu_id, job.direction] = job
    for (hu_id, direction), job in by_direction.items():
        receipt = by_direction.get((hu_id, "inbound"))
        early = receipt is not None and job.arrival_tick < receipt.arrival_tick
        if direction == "outbound" and early:
            raise ValueError("outbound of a received HU arrives before its receipt")
