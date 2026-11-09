"""F3 sequential route/handling fixture: elapsed seconds and person-seconds are distinct."""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from app.v3.analytical_common import require_count, require_rational, require_tuple


@dataclass(frozen=True, slots=True)
class TravelFixture:
    allowed_outbound_legs_m: tuple[Fraction, ...]
    speed_m_s: Fraction

    def __post_init__(self) -> None:
        require_tuple(self.allowed_outbound_legs_m, "route")
        if not self.allowed_outbound_legs_m:
            raise ValueError("fixture route must contain at least one allowed leg")
        for distance in self.allowed_outbound_legs_m:
            require_rational(distance, "route leg")
        require_rational(self.speed_m_s, "speed")


@dataclass(frozen=True, slots=True)
class CrewFixture:
    people: int
    take_s: Fraction
    place_s: Fraction

    def __post_init__(self) -> None:
        require_count(self.people, "people")
        require_rational(self.take_s, "take duration", allow_zero=True)
        require_rational(self.place_s, "place duration", allow_zero=True)


@dataclass(frozen=True, slots=True)
class CycleCost:
    round_trip_m: Fraction
    travel_s: Fraction
    elapsed_s: Fraction
    labor_person_s: Fraction


@dataclass(frozen=True, slots=True)
class CrewComparison:
    baseline: CycleCost
    candidate: CycleCost
    source_kind: Literal["analytical_fixture"] = field(init=False, default="analytical_fixture")

    @property
    def elapsed_difference_s(self) -> Fraction:
        return self.candidate.elapsed_s - self.baseline.elapsed_s

    @property
    def labor_difference_person_s(self) -> Fraction:
        return self.candidate.labor_person_s - self.baseline.labor_person_s


def cycle_cost(travel: TravelFixture, crew: CrewFixture) -> CycleCost:
    """The same crew accompanies both legs and performs both sequential handling actions."""
    distance = 2 * sum(travel.allowed_outbound_legs_m, Fraction())
    travel_s = distance / travel.speed_m_s
    elapsed = travel_s + crew.take_s + crew.place_s
    return CycleCost(distance, travel_s, elapsed, elapsed * crew.people)


def compare_crews(
    travel: TravelFixture, baseline: CrewFixture, candidate: CrewFixture
) -> CrewComparison:
    return CrewComparison(cycle_cost(travel, baseline), cycle_cost(travel, candidate))
