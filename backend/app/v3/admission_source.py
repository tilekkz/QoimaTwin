"""Static C04/C05 source adapter; no route, scheduling, contact or C08 rating claims."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from types import MappingProxyType

from app.v3.admission import storage_admission
from app.v3.admission_models import Admission, StorageState
from app.v3.admission_source_decode import decode_cargo, decode_slots, document
from app.v3.admission_source_models import SelectedCapability as SelectedCapability
from app.v3.admission_source_models import SourceCargo, SourceSlot, select_handler
from app.v3.admission_source_models import SourcePlacement as SourcePlacement
from app.v3.input_models import V3Bundle


@dataclass(frozen=True)
class SourceAdmissionCatalog:
    cargo: Mapping[str, SourceCargo]
    slots: Mapping[str, SourceSlot]
    hu_archetypes: Mapping[str, str]
    hu_orientations: Mapping[str, str]
    baseline: tuple[SourcePlacement, ...]

    @classmethod
    def from_bundle(cls, bundle: V3Bundle) -> "SourceAdmissionCatalog":
        cargo = {
            value["archetype_id"]: decode_cargo(value)
            for value in document(bundle, "cargo-catalog-v3.json")["records"]
        }
        return cls(
            MappingProxyType(cargo),
            MappingProxyType(decode_slots(bundle)),
            MappingProxyType(
                {hu.handling_unit_id: hu.archetype_id for hu in bundle.handling_units}
            ),
            MappingProxyType(
                {hu.handling_unit_id: hu.orientation_id for hu in bundle.handling_units}
            ),
            tuple(SourcePlacement(hu.handling_unit_id, hu.slot_id) for hu in bundle.handling_units),
        )

    def evaluate(
        self,
        handling_unit_id: str,
        slot_id: str,
        selected: SelectedCapability | None,
        *,
        placements: tuple[SourcePlacement, ...],
    ) -> Admission:
        """Add/move one whole known HU in explicit occupancy, excluding only that HU."""
        cargo = self.cargo[self.hu_archetypes[handling_unit_id]]
        slot = self.slots[slot_id]
        state = self._state(handling_unit_id, slot_id, placements)
        model = cargo.cargo
        if self.hu_orientations[handling_unit_id] != "upright_xyz":
            model = replace(model, orientations=())
        physical = slot.slot
        if slot.storage_family not in cargo.storage_families:
            physical = replace(physical, allowed_archetypes=())
        return storage_admission(model, physical, state, select_handler(cargo, slot, selected))

    def _state(
        self,
        moving_id: str,
        slot_id: str,
        placements: tuple[SourcePlacement, ...],
    ) -> StorageState:
        self._validate_placements(placements)
        target = self.slots[slot_id].slot
        residents = [p for p in placements if p.handling_unit_id != moving_id]
        module = [p for p in residents if self.slots[p.slot_id].slot.module_id == target.module_id]
        local = [p for p in module if p.slot_id == slot_id]
        return StorageState(len(local), self._mass(local), self._mass(module))

    def _validate_placements(self, placements: tuple[SourcePlacement, ...]) -> None:
        identities = [p.handling_unit_id for p in placements]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate HU in explicit occupancy")
        counts: Counter[str] = Counter()
        for placement in placements:
            if placement.handling_unit_id not in self.hu_archetypes:
                raise ValueError("Unknown HU in explicit occupancy")
            if placement.slot_id not in self.slots:
                raise ValueError("Unknown slot in explicit occupancy")
            counts[placement.slot_id] += 1
        if any(count > self.slots[key].slot.max_handling_units for key, count in counts.items()):
            raise ValueError("Explicit occupancy exceeds source slot HU limit")

    def _mass(self, placements: list[SourcePlacement]) -> Decimal:
        values = [
            self.cargo[self.hu_archetypes[p.handling_unit_id]].cargo.gross_mass_kg
            for p in placements
        ]
        if any(value is None for value in values):
            raise ValueError("Unknown resident mass")
        finite = [value for value in values if value is not None]
        with localcontext() as context:
            context.prec = max(28, sum(len(v.as_tuple().digits) for v in finite) + 10)
            return sum(finite, Decimal(0))
