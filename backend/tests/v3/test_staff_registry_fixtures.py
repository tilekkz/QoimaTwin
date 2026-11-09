"""Explicit staffing assumptions; no actual dynamic worker assignment is performed."""

from typing import Any

from app.v3.input_pin import SOURCE_REVISION

SECOND = 1_000_000


def registry_document() -> dict[str, Any]:
    workers = []
    for prefix, count, role in (
        ("P", 12, "pick"),
        ("K", 6, "pack"),
        ("R", 2, "receive"),
        ("S", 2, "ship"),
        ("F", 2, "forklift"),
    ):
        for index in range(1, count + 1):
            actor = f"{prefix}{index:02}"
            equipment = ["manual_cart"] if prefix == "P" else []
            if prefix == "F":
                equipment = [f"FL{index:02}"]
            workers.append(
                {
                    "actor_id": actor,
                    "primary_role": role,
                    "eligible_roles": [role, "pack"] if actor in {"P11", "P12"} else [role],
                    "permitted_equipment": equipment,
                }
            )
    return {
        "schema_version": "qoima-staff-registry-0.1.0",
        "source_revision": SOURCE_REVISION,
        "workers": workers,
        "unavailability": [
            {
                "actor_id": actor,
                "start_tick": 100 * SECOND,
                "end_tick": 160 * SECOND,
                "reason": "declared_break",
            }
            for actor in ("K05", "K06")
        ],
        "station_bindings": [
            {"station_id": f"PK{i:02}", "primary_actor_id": f"K{i:02}"} for i in range(1, 7)
        ],
    }
