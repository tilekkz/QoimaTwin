"""Explicit promises over the same physical units; no implicit claimant context."""

from dataclasses import dataclass

from .stock_models import Container, UnitLocation
from .stock_validation import require


def identity(value: str) -> None:
    require(type(value) is str and bool(value.strip()), "exact nonempty identity required")


@dataclass(frozen=True, slots=True)
class StockClaim:
    claim_id: str
    job_id: str
    container_id: str
    unit_ids: tuple[str, ...]
    whole_hu: bool


class StockClaims:
    def __init__(self) -> None:
        self._values: dict[str, StockClaim] = {}
        self.generation = 0

    def snapshot(self) -> tuple[StockClaim, ...]:
        return tuple(self._values[key] for key in sorted(self._values))

    def reserve(self, claim: StockClaim) -> StockClaim:
        for value in (claim.claim_id, claim.job_id, claim.container_id, *claim.unit_ids):
            identity(value)
        require(type(claim.whole_hu) is bool, "exact claim kind required")
        require(type(claim.unit_ids) is tuple and bool(claim.unit_ids), "claim units required")
        require(len(set(claim.unit_ids)) == len(claim.unit_ids), "duplicate claim unit")
        require(claim.claim_id not in self._values, "duplicate claim identity")
        self.authorize(claim.container_id, claim.unit_ids, None, container_move=claim.whole_hu)
        self._values[claim.claim_id] = claim
        self.generation += 1
        return claim

    def authorize(
        self,
        container_id: str,
        unit_ids: tuple[str, ...],
        claim_id: str | None,
        *,
        whole: bool = False,
        container_move: bool = False,
    ) -> None:
        if claim_id is not None:
            identity(claim_id)
            require(claim_id in self._values, "unknown claim")
            own = self._values[claim_id]
            require(own.container_id == container_id, "wrong claim container")
            require(set(own.unit_ids) == set(unit_ids), "claim must authorize exact units")
            require(own.whole_hu == whole, "wrong claim kind")
        for existing in self._values.values():
            if existing.claim_id == claim_id:
                continue
            same_container = existing.container_id == container_id
            conflict = bool(set(existing.unit_ids).intersection(unit_ids))
            conflict |= same_container and (existing.whole_hu or container_move)
            require(not conflict, "inventory already reserved by another claim")

    def release(self, claim_id: str, job_id: str) -> None:
        identity(claim_id)
        identity(job_id)
        require(claim_id in self._values, "unknown claim")
        require(self._values[claim_id].job_id == job_id, "claim belongs to another job")
        self.consume(claim_id)

    def consume(self, claim_id: str | None) -> None:
        if claim_id is not None:
            del self._values[claim_id]
            self.generation += 1

    def check(self, containers: dict[str, Container], locations: dict[str, UnitLocation]) -> None:
        require(type(self.generation) is int and self.generation >= 0, "invalid claim generation")
        for key, claim in self._values.items():
            require(key == claim.claim_id, "claim identity mismatch")
            require(claim.container_id in containers, "claim container vanished")
            for unit_id in claim.unit_ids:
                require(unit_id in locations, "claim unit vanished")
                require(locations[unit_id].container_id == claim.container_id, "claimed unit moved")
