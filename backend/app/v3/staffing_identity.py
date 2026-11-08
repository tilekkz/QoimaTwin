"""Identity of explicit analytical role periods, never a compiled physical run identity."""

from app.storage.canonical_json import sha256_hex
from app.v3.staff_registry import StaffRegistry
from app.v3.staffing_models import AnalyticalCover
from app.v3.staffing_validation import validate_covers


def analytical_allocation_hash(registry: StaffRegistry, covers: tuple[AnalyticalCover, ...]) -> str:
    """Only allocation facts are hashed; validate/compare registry_common_hash separately."""
    validate_covers(registry, covers)
    return sha256_hex(
        {
            "schema_version": "qoima-analytical-staff-allocation-0.1.0",
            "covers": [
                {
                    "cover_id": c.cover_id,
                    "actor_id": c.actor_id,
                    "station_id": c.station_id,
                    "start_tick": c.start_tick,
                    "end_tick": c.end_tick,
                    "outward_ticks": c.outward_ticks,
                    "return_ticks": c.return_ticks,
                }
                for c in sorted(covers, key=lambda c: c.cover_id)
            ],
        }
    )
