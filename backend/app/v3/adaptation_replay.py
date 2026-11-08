"""Disposable sequential planning projection of C11 transfers (ADR 0054).

This is not a StockLedger and not an executed or paid move. It copies baseline placements into
private dictionaries, replays the planned transfers strictly in sequence (destinations may be
freed only by an earlier planned move) and reuses exact static storage admission.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Any

from app.v3.adaptation_models import InventoryTotals, RowDoc, TransferDoc
from app.v3.admission import storage_admission
from app.v3.admission_models import Cargo, Slot, StorageState

PHYSICAL_OK = ("HANDLER_UNAVAILABLE",)  # no handler fact is supplied: physical checks only


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _triple(values: Any) -> tuple[Decimal, Decimal, Decimal]:
    x, y, z = values
    return _decimal(x), _decimal(y), _decimal(z)


@dataclass(frozen=True, slots=True)
class PlanningFacts:
    """Read-only source facts needed by the projection."""

    slots: Mapping[str, Mapping[str, Any]]
    modules: Mapping[str, Mapping[str, Any]]
    cargo: Mapping[str, Mapping[str, Any]]
    baseline: Mapping[str, Mapping[str, Any]]
    home_family: Mapping[str, str]

    def hu_mass(self, archetype: str) -> Fraction:
        return Fraction(str(self.cargo[archetype]["handling_unit"]["gross_mass_kg"]))


@dataclass(slots=True)
class Projection:
    """Private mutable copy of baseline occupancy, discarded after one evaluation."""

    facts: PlanningFacts
    slot_of: dict[str, str] = field(default_factory=dict)
    occupant: dict[str, str] = field(default_factory=dict)
    module_mass: dict[str, Fraction] = field(default_factory=dict)
    released_by: dict[str, int] = field(default_factory=dict)

    @classmethod
    def start(cls, facts: PlanningFacts) -> "Projection":
        projection = cls(facts)
        for hu_id, row in facts.baseline.items():
            projection.slot_of[hu_id] = row["slot_id"]
            projection.occupant[row["slot_id"]] = hu_id
            module = row["module_id"]
            mass = projection.module_mass.get(module, Fraction(0))
            projection.module_mass[module] = mass + facts.hu_mass(row["archetype_id"])
        return projection

    def apply(self, transfer: TransferDoc) -> int | None:
        """Admit and record one planned move; returns the sequence that freed its target."""
        self._check_identity(transfer)
        slot = self.facts.slots[transfer.to_slot_id]
        self._check_slot(transfer, slot)
        mass = self.facts.hu_mass(transfer.archetype_id)
        self._admit(transfer, slot, mass)
        released = self.released_by.get(transfer.to_slot_id)
        del self.occupant[transfer.from_slot_id]
        self.occupant[transfer.to_slot_id] = transfer.hu_id
        self.slot_of[transfer.hu_id] = transfer.to_slot_id
        self.module_mass[transfer.from_module_id] -= mass
        self.module_mass[transfer.to_module_id] = (
            self.module_mass.get(transfer.to_module_id, Fraction(0)) + mass
        )
        self.released_by[transfer.from_slot_id] = transfer.sequence
        return released

    def _check_identity(self, transfer: TransferDoc) -> None:
        row = self.facts.baseline.get(transfer.hu_id)
        if row is None or (row["sku_id"], row["archetype_id"]) != (
            transfer.sku_id,
            transfer.archetype_id,
        ):
            raise ValueError(f"{transfer.hu_id}: unknown HU or sku/archetype mismatch")
        if self.slot_of[transfer.hu_id] != transfer.from_slot_id:
            raise ValueError(f"{transfer.hu_id}: from slot is not its current origin")
        for slot_id, module_id in (
            (transfer.from_slot_id, transfer.from_module_id),
            (transfer.to_slot_id, transfer.to_module_id),
        ):
            source = self.facts.slots.get(slot_id)
            if source is None or source["module_id"] != module_id:
                raise ValueError(f"{slot_id}: unknown slot or module mismatch")
        if transfer.to_slot_id in self.occupant:
            raise ValueError(f"{transfer.to_slot_id}: destination is occupied at this step")

    def _check_slot(self, transfer: TransferDoc, slot: Mapping[str, Any]) -> None:
        if slot["reserve_only"] or slot["retrieval_blocked"]:
            raise ValueError(f"{transfer.to_slot_id}: reserve or retrieval-blocked slot")
        family = self.facts.home_family[transfer.hu_id]
        if slot["storage_type"] != family or family == "FLEX":
            raise ValueError(f"{transfer.to_slot_id}: not the HU's home storage family")
        mass = self.facts.hu_mass(transfer.archetype_id)
        options = [
            option
            for option in slot["conditional_handler_options"]
            if option["transport_tag"] == transfer.transport_tag
            and transfer.archetype_id in option["allowed_cargo_archetype_ids"]
            and (option["manual_gross_mass_limit_kg"] is None
                 or mass <= Fraction(str(option["manual_gross_mass_limit_kg"])))
        ]  # fmt: skip
        if not options:
            raise ValueError(f"{transfer.to_slot_id}: no declared handler option for the move")

    def _admit(self, transfer: TransferDoc, slot: Mapping[str, Any], mass: Fraction) -> None:
        module = self.facts.modules[transfer.to_module_id]
        dims = self.facts.cargo[transfer.archetype_id]["handling_unit"]["dimensions_xyz_m"]
        cargo = Cargo(transfer.archetype_id, _triple(dims),
                      _decimal(mass.numerator) / _decimal(mass.denominator), ("xyz",))  # fmt: skip
        target = Slot(
            slot["slot_id"],
            slot["module_id"],
            _triple(slot["usable_dimensions_xyz_m"]),
            _decimal(slot["max_payload_kg"]),
            slot["max_handling_units"],
            _decimal(module["max_module_payload_kg"]),
            tuple(slot["allowed_cargo_archetype_ids"]),
            ("xyz",),
            _decimal(slot["clearance_each_side_m"]),
            _decimal(slot["bin_anchor"][1]),
            _decimal(slot["service_height_m"]),
        )
        current = self.module_mass.get(transfer.to_module_id, Fraction(0))
        state = StorageState(
            0, Decimal(0), _decimal(current.numerator) / _decimal(current.denominator)
        )
        reasons = storage_admission(cargo, target, state, None).reasons
        if reasons != PHYSICAL_OK:
            raise ValueError(f"{transfer.to_slot_id}: static admission rejected {reasons}")


def inventory_totals(rows: tuple[RowDoc, ...], facts: PlanningFacts) -> InventoryTotals:
    """Exact recount of the adapted rows; identity fields must equal the baseline."""
    for row in rows:
        base = facts.baseline.get(row.hu_id)
        identity = (row.sku_id, row.lot_id, row.archetype_id, row.quantity_units)
        if base is None or identity != (
            base["sku_id"], base["lot_id"], base["archetype_id"], base["quantity_units"]
        ) or row.orientation_id != base["orientation_id"]:  # fmt: skip
            raise ValueError(f"{row.hu_id}: inventory identity differs from the baseline")
    if {row.hu_id for row in rows} != set(facts.baseline):
        raise ValueError("adapted assignment does not contain exactly the baseline HUs")
    mass = sum((facts.hu_mass(row.archetype_id) for row in rows), Fraction(0))
    return InventoryTotals(len(rows), sum(row.quantity_units for row in rows), mass)
