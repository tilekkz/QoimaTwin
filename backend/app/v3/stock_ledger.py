"""Atomic SMALL unit moves; wrappers and material containers are never created by a move."""

from dataclasses import replace

from .stock_models import (
    Container,
    ContainerContents,
    Placement,
    StockBalance,
    StockDelta,
    StockOwner,
    StockSeed,
    StockSnapshot,
    UnitLocation,
)
from .stock_state import balances, check_state, contents_view
from .stock_validation import (
    require,
    validate_container,
    validate_owner,
    validate_seed,
    validate_unit,
)


class StockLedger:
    def __init__(
        self,
        seed: StockSeed,
        *,
        owners: tuple[StockOwner, ...] = (),
        materials: tuple[Container, ...] = (),
    ) -> None:
        all_owners, all_containers = seed.owners + owners, seed.containers + materials
        self._owners = {o.owner_id: o for o in all_owners}
        self._containers = {c.container_id: c for c in all_containers}
        self._tokens = {u.unit_id: u for u in seed.units}
        require(len(self._owners) == len(all_owners), "duplicate owner")
        require(len(self._containers) == len(all_containers), "duplicate container")
        require(len(self._tokens) == len(seed.units), "duplicate unit")
        require(all(c.recipe.kind == "source_wrapper" for c in seed.containers), "source seed kind")
        require(all(c.recipe.kind in {"carrier", "package"} for c in materials), "material kind")
        require(all(c.sealed_for is None for c in all_containers), "initial sealed container")
        for owner in all_owners:
            validate_owner(owner)
        for container in all_containers:
            validate_container(container, self._owners)
        for token in seed.units:
            validate_unit(token, self._containers)
        ancestry = {(u.origin_hu, u.ordinal) for u in seed.units}
        require(len(ancestry) == len(seed.units), "duplicate unit ancestry")
        validate_seed(seed, self._containers, self._owners)
        self._initial_owners = self._owners.copy()
        self._initial_containers = self._containers.copy()
        self._initial_tokens = self._tokens.copy()
        self._locations = {
            u.unit_id: UnitLocation(u.unit_id, u.origin_hu, None) for u in seed.units
        }
        self._revision = 0
        self._history: tuple[StockDelta, ...] = ()
        self.check_invariants()

    @property
    def history(self) -> tuple[StockDelta, ...]:
        return self._history

    def snapshot(self) -> StockSnapshot:
        return StockSnapshot(
            self._revision,
            tuple(self._containers[k] for k in sorted(self._containers)),
            tuple(self._locations[k] for k in sorted(self._locations)),
        )

    def contents(self, container_id: str) -> ContainerContents:
        return contents_view(self._container(container_id), self._locations, self._tokens)

    def balance(self) -> StockBalance:
        return balances(self._containers, self._locations, self._tokens, self._owners)

    def check_invariants(self) -> None:
        require(
            self._owners.keys() == self._initial_owners.keys()
            and all(self._owners[key] is owner for key, owner in self._initial_owners.items()),
            "immutable owner capacity violation",
        )
        require(
            self._tokens.keys() == self._initial_tokens.keys()
            and all(self._tokens[key] is token for key, token in self._initial_tokens.items()),
            "immutable ancestry violation",
        )
        require(self._containers.keys() == self._initial_containers.keys(), "material conservation")
        for key, container in self._containers.items():
            require(
                container.recipe is self._initial_containers[key].recipe, "material recipe changed"
            )
            if container.recipe.kind == "source_wrapper":
                allowed = container.owner_id == self._initial_containers[key].owner_id
                require(container.owner_id in self._owners, "unknown owner")
                require(
                    allowed or self._owners[container.owner_id].kind == "disposal",
                    "source wrapper moved without admission",
                )
        check_state(self._containers, self._locations, self._tokens, self._owners)

    def pick(
        self,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
    ) -> StockDelta:
        return self._move(
            "pick", transaction_id, expected_revision, source_id, target_id, placements
        )

    def transfer(
        self,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
    ) -> StockDelta:
        return self._move(
            "transfer", transaction_id, expected_revision, source_id, target_id, placements
        )

    def pack(
        self,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
        *,
        order_id: str,
    ) -> StockDelta:
        require(bool(order_id.strip()), "order identity required")
        return self._move(
            "pack",
            transaction_id,
            expected_revision,
            source_id,
            target_id,
            placements,
            order_id=order_id,
        )

    def _move(
        self,
        operation: str,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
        *,
        order_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        source, target = self._movable(source_id), self._movable(target_id)
        require(source_id != target_id, "same container")
        source_kind = "source_wrapper" if operation == "pick" else "carrier"
        target_kind = "package" if operation == "pack" else "carrier"
        require(source.recipe.kind == source_kind, "unsupported source kind")
        require(target.recipe.kind == target_kind, "unsupported target kind")
        require(source.sealed_for is None and target.sealed_for is None, "sealed container")
        ids = tuple(p.unit_id for p in placements)
        require(bool(ids) and len(set(ids)) == len(ids), "empty or duplicate transfer")
        locations = self._locations.copy()
        for placement in placements:
            require(placement.unit_id in self._tokens, "unknown unit")
            token = self._tokens[placement.unit_id]
            require(token.recipe.archetype_id == "SMALL_CARTON", "unsupported unit picking class")
            require(
                locations[placement.unit_id].container_id == source_id,
                "wrong source or already picked",
            )
            locations[placement.unit_id] = UnitLocation(
                placement.unit_id, target_id, placement.position
            )
        containers = self._containers.copy()
        if operation == "pack":
            require(not self.contents(target_id).units, "package must be empty material")
            containers[target_id] = replace(target, sealed_for=order_id)
        return self._commit(
            transaction_id, operation, ids, (source_id, target_id), containers, locations
        )

    def ship(
        self,
        transaction_id: str,
        expected_revision: int,
        package_id: str,
        owner_id: str,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        package = self._movable(package_id)
        require(package.recipe.kind == "package" and bool(package.sealed_for), "unsealed package")
        require(bool(self.contents(package_id).units), "empty shipment")
        self._owner_kind(owner_id, {"shipped"})
        return self._reown(transaction_id, "ship", package_id, owner_id)

    def relocate(
        self,
        transaction_id: str,
        expected_revision: int,
        container_id: str,
        owner_id: str,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        container = self._movable(container_id)
        require(
            container.recipe.kind in {"carrier", "package"}, "source wrapper relocation unsupported"
        )
        self._owner_kind(owner_id, {"material", "workstation"})
        return self._reown(transaction_id, "relocate", container_id, owner_id)

    def dispose_empty_wrapper(
        self,
        transaction_id: str,
        expected_revision: int,
        container_id: str,
        owner_id: str,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        container = self._movable(container_id)
        require(container.recipe.kind == "source_wrapper", "only original wrapper disposition")
        require(not self.contents(container_id).units, "wrapper is not empty")
        self._owner_kind(owner_id, {"disposal"})
        return self._reown(transaction_id, "dispose_empty_wrapper", container_id, owner_id)

    def _reown(
        self, transaction_id: str, operation: str, container_id: str, owner_id: str
    ) -> StockDelta:
        containers = self._containers.copy()
        containers[container_id] = replace(containers[container_id], owner_id=owner_id)
        ids = tuple(u.token.unit_id for u in self.contents(container_id).units)
        return self._commit(
            transaction_id, operation, ids, (container_id,), containers, self._locations
        )

    def _commit(
        self,
        transaction_id: str,
        operation: str,
        ids: tuple[str, ...],
        affected: tuple[str, ...],
        containers: dict[str, Container],
        locations: dict[str, UnitLocation],
    ) -> StockDelta:
        check_state(containers, locations, self._tokens, self._owners)
        before = tuple(self.contents(key) for key in affected)
        after = tuple(contents_view(containers[key], locations, self._tokens) for key in affected)
        delta = StockDelta(transaction_id, self._revision + 1, operation, ids, before, after)
        self._containers, self._locations = containers, locations
        self._revision += 1
        self._history += (delta,)
        return delta

    def _begin(self, transaction_id: str, expected_revision: int) -> None:
        require(bool(transaction_id.strip()), "transaction identity required")
        require(
            type(expected_revision) is int and expected_revision == self._revision, "stale revision"
        )
        require(
            all(d.transaction_id != transaction_id for d in self._history), "duplicate transaction"
        )
        self.check_invariants()

    def _container(self, container_id: str) -> Container:
        require(container_id in self._containers, "unknown container")
        return self._containers[container_id]

    def _movable(self, container_id: str) -> Container:
        container = self._container(container_id)
        require(
            self._owners[container.owner_id].kind not in {"shipped", "disposal"},
            "terminal container",
        )
        return container

    def _owner_kind(self, owner_id: str, allowed: set[str]) -> None:
        require(owner_id in self._owners, "unknown owner")
        require(self._owners[owner_id].kind in allowed, "unsupported destination owner")
