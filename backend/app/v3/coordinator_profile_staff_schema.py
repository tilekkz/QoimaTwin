"""Explicit registry assumptions, not capability-derived admission grants."""

from typing import Any

from app.v3.flow_profile_schema import TEXT, TICK, object_schema
from app.v3.input_pin import SOURCE_REVISION
from app.v3.staff_registry_values import EQUIPMENT, REGISTRY_VERSION, ROLES


def _rows(value: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": value}


def registry_schema() -> dict[str, Any]:
    role = {"enum": list(ROLES)}
    return object_schema(
        {
            "schema_version": {"const": REGISTRY_VERSION},
            "source_revision": {"const": SOURCE_REVISION},
            "workers": _rows(
                object_schema(
                    {
                        "actor_id": TEXT,
                        "primary_role": role,
                        "eligible_roles": {**_rows(role), "uniqueItems": True},
                        "permitted_equipment": {
                            **_rows({"enum": sorted(EQUIPMENT)}),
                            "uniqueItems": True,
                        },
                    }
                )
            ),
            "unavailability": _rows(
                object_schema(
                    {
                        "actor_id": TEXT,
                        "start_tick": TICK,
                        "end_tick": TICK,
                        "reason": TEXT,
                    }
                )
            ),
            "station_bindings": _rows(
                object_schema(
                    {
                        "station_id": TEXT,
                        "primary_actor_id": TEXT,
                    }
                )
            ),
        }
    )
