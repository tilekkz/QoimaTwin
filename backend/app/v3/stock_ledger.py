"""One stock authority: bounded unit moves and explicit whole-HU receipt accounting."""

from dataclasses import replace

from .stock_claims import StockClaim, StockClaims, identity
from .stock_commands import ReceiveHUCommand, ShipHUCommand, StockCommand, validate_command
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
    UnitToken,
)
from .stock_receipts import (
    InventorySnapshot,
    ReceiptDefinition,
    ReceiptDelta,
    receipt_recipes,
    receipt_tokens,
    validate_receipt,
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
        self._source_container_ids = frozenset(self._initial_containers)
        self._source_token_ids = frozenset(self._initial_tokens)
        self._registered_tokens = self._tokens.copy()
        self._registered_containers = self._containers.copy()
        self._authorized_containers = self._containers.copy()
        self._receipts: tuple[ReceiptDefinition, ...] = ()
        self._whole_shipments: frozenset[str] = frozenset()
        self._claims = StockClaims()
        self._applied: dict[str, tuple[StockCommand, StockDelta]] = {}
        self._locations = {
            u.unit_id: UnitLocation(u.unit_id, u.origin_hu, None) for u in seed.units
        }
        self._authorized_locations = self._locations.copy()
        self._revision = 0
        self._history: tuple[StockDelta, ...] = ()
        self.check_invariants()

    @property
    def history(self) -> tuple[StockDelta, ...]:
        return self._history

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def claims(self) -> tuple[StockClaim, ...]:
        return self._claims.snapshot()

    def inventory_snapshot(self) -> InventorySnapshot:
        stock = self.snapshot()
        return InventorySnapshot(
            stock.revision,
            stock.containers,
            stock.locations,
            self._receipts,
            self.claims,
            self._claims.generation,
        )

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
            self._tokens.keys() == self._registered_tokens.keys()
            and all(self._tokens[key] is token for key, token in self._registered_tokens.items()),
            "immutable ancestry violation",
        )
        self._check_source_authority()
        require(
            self._containers.keys() == self._registered_containers.keys(), "material conservation"
        )
        for key, container in self._containers.items():
            require(
                container.recipe is self._registered_containers[key].recipe,
                "material recipe changed",
            )
            require(
                container is self._authorized_containers[key], "unauthorized container mutation"
            )
        check_state(
            self._containers, self._locations, self._tokens, self._owners, self._whole_shipments
        )
        require(
            all(value is self._authorized_locations[key] for key, value in self._locations.items()),
            "unauthorized unit location mutation",
        )
        self._claims.check(self._containers, self._locations)

    def _check_source_authority(self) -> None:
        require(
            self._initial_tokens.keys() == self._source_token_ids
            and self._source_token_ids <= self._registered_tokens.keys()
            and all(
                self._initial_tokens[k] is self._registered_tokens[k]
                for k in self._source_token_ids
            ),
            "immutable source ancestry violation",
        )
        require(
            self._initial_containers.keys() == self._source_container_ids
            and self._source_container_ids <= self._registered_containers.keys()
            and all(
                self._initial_containers[k] is self._registered_containers[k]
                for k in self._source_container_ids
            ),
            "immutable source recipe violation",
        )

    def pick(
        self,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        return self._move(
            "pick",
            transaction_id,
            expected_revision,
            source_id,
            target_id,
            placements,
            claim_id=claim_id,
        )

    def transfer(
        self,
        transaction_id: str,
        expected_revision: int,
        source_id: str,
        target_id: str,
        placements: tuple[Placement, ...],
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        return self._move(
            "transfer",
            transaction_id,
            expected_revision,
            source_id,
            target_id,
            placements,
            claim_id=claim_id,
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
        claim_id: str | None = None,
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
            claim_id=claim_id,
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
        claim_id: str | None = None,
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
        self._claims.authorize(source_id, ids, claim_id)
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
            transaction_id,
            operation,
            ids,
            (source_id, target_id),
            containers,
            locations,
            consume_claim=claim_id,
        )

    def ship(
        self,
        transaction_id: str,
        expected_revision: int,
        package_id: str,
        owner_id: str,
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        package = self._movable(package_id)
        require(package.recipe.kind == "package" and bool(package.sealed_for), "unsealed package")
        require(bool(self.contents(package_id).units), "empty shipment")
        self._owner_kind(owner_id, {"shipped"})
        self._authorize_container(package_id, claim_id)
        return self._reown(transaction_id, "ship", package_id, owner_id, consume_claim=claim_id)

    def relocate(
        self,
        transaction_id: str,
        expected_revision: int,
        container_id: str,
        owner_id: str,
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        container = self._movable(container_id)
        require(
            container.recipe.kind in {"carrier", "package"}, "source wrapper relocation unsupported"
        )
        self._owner_kind(owner_id, {"material", "workstation"})
        self._authorize_container(container_id, claim_id)
        return self._reown(transaction_id, "relocate", container_id, owner_id)

    def dispose_empty_wrapper(
        self,
        transaction_id: str,
        expected_revision: int,
        container_id: str,
        owner_id: str,
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        container = self._movable(container_id)
        require(container.recipe.kind == "source_wrapper", "only original wrapper disposition")
        require(not self.contents(container_id).units, "wrapper is not empty")
        self._owner_kind(owner_id, {"disposal"})
        self._authorize_container(container_id, claim_id)
        return self._reown(
            transaction_id,
            "dispose_empty_wrapper",
            container_id,
            owner_id,
            consume_claim=claim_id,
        )

    def _reown(
        self,
        transaction_id: str,
        operation: str,
        container_id: str,
        owner_id: str,
        *,
        consume_claim: str | None = None,
        whole_shipments: frozenset[str] | None = None,
    ) -> StockDelta:
        containers = self._containers.copy()
        containers[container_id] = replace(containers[container_id], owner_id=owner_id)
        ids = tuple(u.token.unit_id for u in self.contents(container_id).units)
        return self._commit(
            transaction_id,
            operation,
            ids,
            (container_id,),
            containers,
            self._locations,
            consume_claim=consume_claim,
            whole_shipments=whole_shipments,
        )

    def _commit(
        self,
        transaction_id: str,
        operation: str,
        ids: tuple[str, ...],
        affected: tuple[str, ...],
        containers: dict[str, Container],
        locations: dict[str, UnitLocation],
        *,
        consume_claim: str | None = None,
        whole_shipments: frozenset[str] | None = None,
    ) -> StockDelta:
        shipped = self._whole_shipments if whole_shipments is None else whole_shipments
        check_state(containers, locations, self._tokens, self._owners, shipped)
        before = tuple(self.contents(key) for key in affected)
        after = tuple(contents_view(containers[key], locations, self._tokens) for key in affected)
        delta = StockDelta(transaction_id, self._revision + 1, operation, ids, before, after)
        self._containers, self._locations = containers, locations
        self._authorized_locations = locations.copy()
        self._authorized_containers = containers.copy()
        self._whole_shipments = shipped
        self._revision += 1
        self._history += (delta,)
        self._claims.consume(consume_claim)
        return delta

    def _begin(self, transaction_id: str, expected_revision: int) -> None:
        identity(transaction_id)
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
        identity(owner_id)
        require(owner_id in self._owners, "unknown owner")
        require(self._owners[owner_id].kind in allowed, "unsupported destination owner")

    def _authorize_container(self, container_id: str, claim_id: str | None) -> None:
        ids = tuple(u.token.unit_id for u in self.contents(container_id).units)
        self._claims.authorize(container_id, ids, claim_id, container_move=True)

    def receive_hu(
        self, transaction_id: str, expected_revision: int, receipt: ReceiptDefinition, owner_id: str
    ) -> ReceiptDelta:
        self._begin(transaction_id, expected_revision)
        container, created = self._receipt_candidate(receipt, owner_id)
        containers, tokens, locations = (
            self._containers.copy(),
            self._tokens.copy(),
            self._locations.copy(),
        )
        containers[container.container_id] = container
        for token in created:
            tokens[token.unit_id] = token
            locations[token.unit_id] = UnitLocation(token.unit_id, container.container_id, None)
        check_state(containers, locations, tokens, self._owners, self._whole_shipments)
        after = contents_view(container, locations, tokens)
        delta = ReceiptDelta(
            transaction_id,
            self._revision + 1,
            "receive_hu",
            tuple(t.unit_id for t in created),
            (),
            (after,),
            receipt,
            created,
        )
        self._tokens, self._locations, self._containers = tokens, locations, containers
        self._authorized_locations = locations.copy()
        self._registered_tokens = tokens.copy()
        self._registered_containers = {**self._registered_containers, receipt.hu_id: container}
        self._authorized_containers = containers.copy()
        self._receipts += (receipt,)
        self._revision += 1
        self._history += (delta,)
        return delta

    def _receipt_candidate(
        self, receipt: ReceiptDefinition, owner_id: str
    ) -> tuple[Container, tuple[UnitToken, ...]]:
        validate_receipt(receipt)
        self._owner_kind(owner_id, {"buffer", "worker", "vehicle"})
        require(receipt.hu_id not in self._containers, "duplicate HU identity")
        require(
            all(r.receipt_id != receipt.receipt_id for r in self._receipts), "duplicate receipt"
        )
        unit, wrapper = receipt_recipes(
            receipt.sku_id, self._initial_tokens, self._initial_containers
        )
        require(receipt.quantity_units == wrapper.max_units, "receipt recipe quantity mismatch")
        require(
            all(
                t.sku_id == receipt.sku_id
                for t in self._tokens.values()
                if t.lot_id == receipt.lot_id
            ),
            "lot belongs to another SKU",
        )
        container = Container(receipt.hu_id, wrapper, owner_id)
        created = receipt_tokens(receipt, unit)
        require(
            not {t.unit_id for t in created}.intersection(self._tokens), "duplicate unit identity"
        )
        return container, created

    def _intact(self, hu_id: str) -> tuple[str, ...]:
        identity(hu_id)
        hu = self._movable(hu_id)
        require(hu.recipe.kind == "source_wrapper", "whole HU needs original wrapper")
        units = self.contents(hu_id).units
        require(len(units) == hu.recipe.max_units, "whole HU must be intact")
        require(
            {u.token.ordinal for u in units} == set(range(1, len(units) + 1)), "intact ancestry"
        )
        return tuple(u.token.unit_id for u in units)

    def transfer_whole_hu(
        self,
        transaction_id: str,
        expected_revision: int,
        hu_id: str,
        owner_id: str,
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        ids = self._intact(hu_id)
        self._owner_kind(owner_id, {"slot", "buffer", "worker", "vehicle"})
        require(self._containers[hu_id].owner_id != owner_id, "same owner")
        self._claims.authorize(hu_id, ids, claim_id, whole=True, container_move=True)
        return self._reown(transaction_id, "transfer_whole_hu", hu_id, owner_id)

    def ship_whole_hu(
        self,
        transaction_id: str,
        expected_revision: int,
        hu_id: str,
        owner_id: str,
        *,
        claim_id: str | None = None,
    ) -> StockDelta:
        self._begin(transaction_id, expected_revision)
        ids = self._intact(hu_id)
        self._owner_kind(owner_id, {"shipped"})
        self._claims.authorize(hu_id, ids, claim_id, whole=True, container_move=True)
        return self._reown(
            transaction_id,
            "ship_whole_hu",
            hu_id,
            owner_id,
            consume_claim=claim_id,
            whole_shipments=self._whole_shipments | {hu_id},
        )

    def reserve_hu(
        self, claim_id: str, job_id: str, expected_revision: int, hu_id: str
    ) -> StockClaim:
        self._reservation_revision(expected_revision)
        return self._claims.reserve(StockClaim(claim_id, job_id, hu_id, self._intact(hu_id), True))

    def reserve_units(
        self,
        claim_id: str,
        job_id: str,
        expected_revision: int,
        container_id: str,
        unit_ids: tuple[str, ...],
    ) -> StockClaim:
        self._reservation_revision(expected_revision)
        self._movable(container_id)
        require(type(unit_ids) is tuple and bool(unit_ids), "claim units required")
        for unit_id in unit_ids:
            identity(unit_id)
            require(unit_id in self._tokens, "unknown claim unit")
            require(self._locations[unit_id].container_id == container_id, "wrong claim source")
            require(self._tokens[unit_id].recipe.archetype_id == "SMALL_CARTON", "unit claim class")
        return self._claims.reserve(StockClaim(claim_id, job_id, container_id, unit_ids, False))

    def _reservation_revision(self, expected_revision: int) -> None:
        require(
            type(expected_revision) is int and expected_revision == self._revision, "stale revision"
        )
        self.check_invariants()

    def release_claim(self, claim_id: str, job_id: str) -> None:
        self.check_invariants()
        self._claims.release(claim_id, job_id)

    def apply_once(self, command: StockCommand) -> StockDelta:
        validate_command(command)
        self.check_invariants()
        if command.transaction_id in self._applied:
            previous, result = self._applied[command.transaction_id]
            require(command == previous, "conflicting duplicate transaction command")
            return result
        if isinstance(command, ReceiveHUCommand):
            result = self.receive_hu(
                command.transaction_id, command.expected_revision, command.receipt, command.owner_id
            )
        else:
            move = (
                self.ship_whole_hu if isinstance(command, ShipHUCommand) else self.transfer_whole_hu
            )
            result = move(
                command.transaction_id,
                command.expected_revision,
                command.hu_id,
                command.owner_id,
                claim_id=command.claim_id,
            )
        self._applied[command.transaction_id] = (command, result)
        return result
