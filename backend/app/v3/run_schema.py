"""Draft 2020-12 schema for the independent V3 manual execution proposal."""

from app.v3.interface import Json

STRING = {"type": "string", "minLength": 1}
TICK = {"type": "integer", "minimum": 0}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
KINDS = [
    "job_arrived",
    "job_changed",
    "worker_changed",
    "lease_acquired",
    "lease_released",
    "hu_owner_changed",
    "operation_started",
    "operation_completed",
    "hu_shipped",
    "job_completed",
]
JOB_STATES = ["unreleased", "waiting", "active", "returning", "complete"]
WAIT_REASONS = ["not_arrived", "resources", "stock_or_slot", "no_route", "port_window", "port_busy"]


def obj(properties: Json) -> Json:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def array(item: Json) -> Json:
    return {"type": "array", "items": item}


def ref(name: str) -> Json:
    return {"$ref": "#/$defs/" + name}


def nullable(value: Json) -> Json:
    return {"anyOf": [value, {"type": "null"}]}


def _profile_defs() -> Json:
    return {
        **_resource_defs(),
        "rational": obj(
            {"numerator": {"type": "integer"}, "denominator": {"type": "integer", "minimum": 1}}
        ),
        "binding": obj({"path": STRING, "sha256": HASH}),
        "actor": obj(
            {
                "actor_id": STRING,
                "home_node_id": STRING,
                "skills": array(STRING),
                "speed_m_s": ref("rational"),
                "max_gross_mass_kg": ref("rational"),
            }
        ),
        "hu": obj(
            {
                "hu_id": STRING,
                "sku_id": STRING,
                "quantity": {"type": "integer", "minimum": 1},
                "archetype": STRING,
                "gross_mass_kg": ref("rational"),
                "dimensions_xyz_m": {**array(ref("rational")), "minItems": 3, "maxItems": 3},
            }
        ),
    }


def _resource_defs() -> Json:
    return {
        "place": obj(
            {
                "place_id": STRING,
                "node_id": STRING,
                "usable_dimensions_xyz_m": {**array(ref("rational")), "minItems": 3, "maxItems": 3},
                "max_payload_kg": ref("rational"),
                "allowed_archetypes": array(STRING),
            }
        ),
        "port": obj(
            {
                "port_id": STRING,
                "direction": {"enum": ["inbound", "outbound"]},
                "service_node_id": STRING,
                "buffer_places": array(ref("place")),
                "service_ticks": array(_pair(STRING, TICK)),
                "windows": array(_pair(TICK, TICK)),
                "eligible_actor_ids": array(STRING),
            }
        ),
        "timed_job": obj(
            {
                "job_id": STRING,
                "arrival_tick": TICK,
                "direction": {"enum": ["inbound", "outbound"]},
                "hu_id": STRING,
                "port_id": STRING,
                "slot_id": STRING,
            }
        ),
    }


def _pair(first: Json, second: Json) -> Json:
    return {
        "type": "array",
        "prefixItems": [first, second],
        "items": False,
        "minItems": 2,
        "maxItems": 2,
    }


def _profile() -> Json:
    return obj(
        {
            "profile_id": STRING,
            "layout_version": STRING,
            "graph_sha256": HASH,
            "source_bindings": array(ref("binding")),
            "actors": array(ref("actor")),
            "ports": array(ref("port")),
            "slots": array(ref("place")),
            "handling_units": array(ref("hu")),
            "initial_placements": array(obj({"hu_id": STRING, "slot_id": STRING})),
            "jobs": array(ref("timed_job")),
            "handling": obj({"pickup_ticks": TICK, "place_ticks": TICK}),
            "provenance_note": STRING,
        }
    )


def _state_defs() -> Json:
    return {
        "route": obj(
            {
                "graph_id": STRING,
                "node_ids": array(STRING),
                "arc_ids": array(STRING),
                "length_m": ref("rational"),
                "cost_m": ref("rational"),
            }
        ),
        "motion": obj({"route": ref("route"), "start_tick": TICK, "end_tick": TICK}),
        "worker": obj(
            {
                "actor_id": STRING,
                "node_id": nullable(STRING),
                "motion": nullable(ref("motion")),
                "job_id": nullable(STRING),
            }
        ),
        "job": obj(
            {
                "job_id": STRING,
                "state": {"enum": JOB_STATES},
                "wait_reason": nullable({"enum": WAIT_REASONS}),
                "actor_id": nullable(STRING),
            }
        ),
        "owner": obj(
            {
                "hu_id": STRING,
                "kind": {
                    "enum": [
                        "unreleased",
                        "outside",
                        "stock",
                        "worker",
                        "buffer",
                        "service",
                        "shipped",
                    ]
                },
                "location_id": STRING,
            }
        ),
        "lease": obj({"resource_id": STRING, "job_id": STRING, "acquired_tick": TICK}),
    }


def _snapshot() -> Json:
    return obj(
        {
            "tick": TICK,
            "status": {"enum": ["partial", "complete"]},
            "jobs": array(ref("job")),
            "workers": array(ref("worker")),
            "owners": array(ref("owner")),
            "leases": array(ref("lease")),
            **{
                name: array(_pair(STRING, TICK))
                for name in ("stock_units", "wip_units", "outside_units", "shipped_units")
            },
        }
    )


def _event() -> Json:
    return obj(
        {
            "seq": TICK,
            "tick": TICK,
            "kind": {"enum": KINDS},
            "job_id": STRING,
            "hu_id": STRING,
            "actor_id": nullable(STRING),
            "stage": nullable(STRING),
            "location_id": nullable(STRING),
            "resource_ids": array(STRING),
            "motion": nullable(ref("motion")),
            "owner": nullable(ref("owner")),
            "job": nullable(ref("job")),
            "worker": nullable(ref("worker")),
        }
    )


def schema() -> Json:
    from app.v3.run_metrics_schema import metrics_schema

    definitions = {
        **_profile_defs(),
        **_state_defs(),
        "profile": _profile(),
        "state": _snapshot(),
        "event": _event(),
        "metrics": metrics_schema(),
        "operation": _operation(),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:qoima:manual-run:v3-proposal:0.1.0",
        "$defs": definitions,
        **obj(_root_properties()),
    }


def _root_properties() -> Json:
    return {
        "schema_id": {"const": "qoima.manual-run.v3-proposal"},
        "schema_version": {"const": "0.1.0"},
        "contract_status": {"const": "proposal"},
        "data_kind": {"const": "manual_execution_proposal"},
        "source_label": {"const": "actual_engine_run"},
        "run_id": HASH,
        "engine_version": STRING,
        "profile": ref("profile"),
        "graph_document": {"type": "object"},
        "clock": obj(
            {
                "ticks_per_second": {"const": 1_000_000},
                "duration_rounding": {"const": "ceil_each_positive_operation"},
            }
        ),
        "capabilities": obj(
            {
                "actual_engine_run": {"const": True},
                "frontend_adapter": {"const": False},
                "full_v3_warehouse": {"const": False},
            }
        ),
        "end_tick_limit": TICK,
        "observed_until_tick": TICK,
        "initial_state": ref("state"),
        "at_horizon": ref("state"),
        "at_end": ref("state"),
        "events": array(ref("event")),
        "metrics": ref("metrics"),
        "operations": array(ref("operation")),
        "snapshots": array(
            obj(
                {
                    "tick": TICK,
                    "through_seq": {"type": "integer", "minimum": -1},
                    "state_hash": HASH,
                    "state": ref("state"),
                    "active_operation_ids": array(STRING),
                }
            )
        ),
    }


def _operation() -> Json:
    return obj(
        {
            "operation_id": STRING,
            "job_id": STRING,
            "hu_id": STRING,
            "actor_id": STRING,
            "stage": STRING,
            "start_tick": TICK,
            "planned_end_tick": TICK,
            "observed_end_tick": TICK,
            "completed": {"type": "boolean"},
            "motion": nullable(ref("motion")),
        }
    )
