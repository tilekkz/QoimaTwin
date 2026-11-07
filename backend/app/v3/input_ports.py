"""Finite static port declarations and shared resource references."""

from typing import Any

from .input_checks import get_document, indexed, positive, require, rows
from .input_json import PREFIX


def validate_ports(
    documents: dict[str, Any], cargo_ids: set[str], nodes: dict[str, set[str]]
) -> dict[str, Any]:
    policy = get_document(documents, "port-resource-policy-v3.json")
    path = PREFIX + "port-resource-policy-v3.json"
    actors = policy.get("actor_ids", [])
    require(len(actors) == len(set(actors)) == 24, path + "/actor_ids", "expected 24 unique actors")
    pools = indexed(rows(policy, "pools", path), "pool_id", path + "/pools")
    pairs = indexed(rows(policy, "forklift_pairs", path), "pair_id", path + "/forklift_pairs")
    for pool in pools.values():
        require(set(pool["actor_ids"]) <= set(actors), path, "unknown pool actor")
    for pair in pairs.values():
        require(pair["actor_id"] in actors, path, "unknown forklift actor")
    ports: list[dict[str, Any]] = []
    for direction in ("inbound", "outbound"):
        name = f"ports-v3.{direction}.json"
        records = rows(get_document(documents, name), "ports", PREFIX + name)
        require(len(records) == 3, PREFIX + name, "expected three ports")
        for i, record in enumerate(records):
            validate_port(record, f"{PREFIX}{name}/ports/{i}", direction, cargo_ids)
            require(
                record.get("service_node_id") in nodes["walk"],
                f"{PREFIX}{name}/ports/{i}/service_node_id",
                "unknown service node",
            )
            validate_port_resources(record, pools, pairs, f"{PREFIX}{name}/ports/{i}")
        ports.extend(records)
    return indexed(ports, "port_id", PREFIX + "ports")


def validate_port(record: dict[str, Any], path: str, direction: str, cargo_ids: set[str]) -> None:
    require(record.get("direction") == direction, path + "/direction", "port direction mismatch")
    allowed = record.get("allowed_cargo_archetype_ids", [])
    require(bool(allowed) and set(allowed) <= cargo_ids, path, "unknown/empty cargo archetypes")
    require(len(set(allowed)) == len(allowed), path, "duplicate allowed cargo archetype")
    capacity = record.get("finite_buffer_capacity", {})
    positive(capacity.get("total"), path + "/finite_buffer_capacity/total", integer=True)
    for i, allocation in enumerate(capacity.get("allocations", [])):
        positive(
            allocation.get("max_handling_units"),
            f"{path}/finite_buffer_capacity/allocations/{i}/max_handling_units",
            integer=True,
        )
    require(
        sum(a["max_handling_units"] for a in capacity.get("allocations", [])) == capacity["total"],
        path + "/finite_buffer_capacity/allocations",
        "buffer allocation count mismatch",
    )
    positive(
        record.get("service_capacity", {}).get("max_concurrent_jobs"),
        path + "/service_capacity/max_concurrent_jobs",
        integer=True,
    )
    seconds = record.get("service_time_rule", {}).get("seconds_by_archetype", {})
    require(set(seconds) == set(allowed), path + "/service_time_rule", "service cargo mismatch")
    for key, value in seconds.items():
        positive(value, f"{path}/service_time_rule/seconds_by_archetype/{key}")
    for i, window in enumerate(record.get("open_windows", [])):
        require(isinstance(window, list) and len(window) == 2, path, "invalid open window")
        require(0 <= window[0] < window[1], f"{path}/open_windows/{i}", "invalid open window")


def validate_port_resources(
    record: dict[str, Any], pools: dict[str, Any], pairs: dict[str, Any], path: str
) -> None:
    for i, requirement in enumerate(record.get("resource_requirements", [])):
        for key in ("receiver_pool_ref", "shipper_pool_ref"):
            if key in requirement:
                require(
                    requirement[key] in pools,
                    f"{path}/resource_requirements/{i}/{key}",
                    "unknown shared actor pool",
                )
        pair = requirement.get("forklift_pair_ref")
        if pair is not None:
            require(pair in pairs, path, "unknown forklift pair")
            require(
                pairs[pair]["eligible_direction"] == record["direction"],
                path,
                "forklift pair direction mismatch",
            )
