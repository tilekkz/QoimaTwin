"""Pure source-bound staffing assumptions; this hash proves registry sameness only."""

import hashlib
from dataclasses import dataclass
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.input_pin import SOURCE_REVISION
from app.v3.staff_registry_models import (
    StaffSource,
    StationBinding,
    Unavailability,
    WorkerCapability,
)
from app.v3.staff_registry_source import load_staff_source, source_record
from app.v3.staff_registry_validation import validate_registry_inputs
from app.v3.staff_registry_values import (
    REGISTRY_VERSION,
    array,
    object_fields,
    role,
    string_set,
    text,
)


@dataclass(frozen=True, slots=True)
class StaffRegistry:
    workers: tuple[WorkerCapability, ...]
    unavailability: tuple[Unavailability, ...]
    station_bindings: tuple[StationBinding, ...]

    def __post_init__(self) -> None:
        validate_registry_inputs(
            self.workers, self.unavailability, self.station_bindings, self.source
        )

    @property
    def source(self) -> StaffSource:
        return load_staff_source()

    @property
    def canonical_bytes(self) -> bytes:
        source = validate_registry(self)
        return canonical_bytes({"source": source_record(source), **registry_document(self)})

    @property
    def registry_common_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    @property
    def operational_admission(self) -> bool:
        return False


def validate_registry(registry: StaffRegistry) -> StaffSource:
    if type(registry) is not StaffRegistry:
        raise ValueError("STAFF_REGISTRY_TYPE_REQUIRED")
    source = load_staff_source()
    validate_registry_inputs(
        registry.workers, registry.unavailability, registry.station_bindings, source
    )
    return source


def compile_staff_registry(document: object) -> StaffRegistry:
    """Strict decoded JSON boundary; source facts are loaded locally, never supplied as claims."""
    data = object_fields(
        document, "schema_version source_revision workers unavailability station_bindings"
    )
    if (
        text(data["schema_version"]) != REGISTRY_VERSION
        or text(data["source_revision"]) != SOURCE_REVISION
    ):
        raise ValueError("STAFF_REGISTRY_VERSION_OR_SOURCE_MISMATCH")
    workers = tuple(_worker(row) for row in array(data["workers"]))
    windows = tuple(_window(row) for row in array(data["unavailability"]))
    bindings = tuple(_binding(row) for row in array(data["station_bindings"]))
    return StaffRegistry(
        tuple(sorted(workers, key=lambda w: w.actor_id)),
        tuple(sorted(windows, key=lambda w: (w.actor_id, w.start_tick))),
        tuple(sorted(bindings, key=lambda b: b.station_id)),
    )


def _worker(value: object) -> WorkerCapability:
    data = object_fields(value, "actor_id primary_role eligible_roles permitted_equipment")
    return WorkerCapability(
        text(data["actor_id"]),
        role(data["primary_role"]),
        tuple(role(r) for r in string_set(data["eligible_roles"])),
        string_set(data["permitted_equipment"]),
    )


def _window(value: object) -> Unavailability:
    data = object_fields(value, "actor_id start_tick end_tick reason")
    return Unavailability(
        text(data["actor_id"]), data["start_tick"], data["end_tick"], text(data["reason"])
    )


def _binding(value: object) -> StationBinding:
    data = object_fields(value, "station_id primary_actor_id")
    return StationBinding(text(data["station_id"]), text(data["primary_actor_id"]))


def registry_document(registry: StaffRegistry) -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_VERSION,
        "source_revision": SOURCE_REVISION,
        "workers": [
            {
                "actor_id": w.actor_id,
                "primary_role": w.primary_role,
                "eligible_roles": sorted(w.eligible_roles),
                "permitted_equipment": sorted(w.permitted_equipment),
            }
            for w in sorted(registry.workers, key=lambda w: w.actor_id)
        ],
        "unavailability": [
            {
                "actor_id": w.actor_id,
                "start_tick": w.start_tick,
                "end_tick": w.end_tick,
                "reason": w.reason,
            }
            for w in sorted(registry.unavailability, key=lambda w: (w.actor_id, w.start_tick))
        ],
        "station_bindings": [
            {"station_id": b.station_id, "primary_actor_id": b.primary_actor_id}
            for b in sorted(registry.station_bindings, key=lambda b: b.station_id)
        ],
    }


def require_same_registry(left: StaffRegistry, right: StaffRegistry) -> None:
    """Compare verified canonical facts, not caller-reported hashes or full physical scenarios."""
    if type(left) is not StaffRegistry or type(right) is not StaffRegistry:
        raise ValueError("STAFF_REGISTRY_TYPE_REQUIRED")
    if left.canonical_bytes != right.canonical_bytes:
        raise ValueError("REGISTRY_COMMON_INPUT_DRIFT")
