"""Finite receiving/shipping queues and forklift ownership in public replay."""

from typing import Any

type Json = dict[str, Any]


def apply_pallet(state: Json, event: Json, params: Json, actions: dict[str, Json]) -> None:
    p, kind = event["payload"], event["kind"]
    shipping, receiving = state["shipping"], state["receiving"]
    if kind == "shipping_arrived":
        shipping["buffer"].append(p["parcel_id"])
    elif kind == "cargo_placed" and p["container_id"] == "OPEN_PALLET":
        shipping["open_pallet"] = {
            "pallet_id": p["cargo_id"],
            "state": "OPEN",
            "parcels": [],
            "reserved": 0,
            "first_placement_tick": None,
            "generation": 0,
            "expires_tick": None,
        }
    elif kind == "parcel_scanned":
        _scanned(shipping, p, event["at_tick"], params["pallet_max_age_ticks"])
    elif kind == "pallet_seal_pending":
        shipping["open_pallet"]["state"] = "SEAL_PENDING"
        shipping["open_pallet"]["expires_tick"] = None
    elif kind == "pallet_sealed":
        pallet = shipping["open_pallet"]
        pallet["state"], pallet["expires_tick"] = "SEALED", None
        pallet["generation"] += 1
        shipping["sealed_queue"].append(pallet)
        shipping["open_pallet"] = None
        shipping["outbound"]["tasks"].append(p["pallet_id"])
    elif kind == "order_dispatched":
        shipping["outbound"]["carrying"] = None
    elif kind == "receipt_arrived":
        receiving["external"].append(p["receipt_id"])
    elif kind == "receipt_accepted":
        receiving["external"].remove(p["receipt_id"])
        receiving["area"].append(
            {"pallet_id": p["pallet_id"], "receipt_id": p["receipt_id"], "state": "WAITING"}
        )
        receiving["counts"]["accepted"] += 1
    elif kind == "receipt_processed":
        _receipt(receiving, p["pallet_id"])["state"] = "PROCESSED"
    elif kind == "pallet_putaway":
        receiving["counts"]["putaway"] += 1
    elif kind == "cargo_attached":
        _attached(state, p, params)
    elif kind == "actor_state_changed":
        next(a for a in state["actors"] if a["actor_id"] == p["actor_id"])["state"] = p["state"]
        action = actions.get(p["action_id"])
        _actor_transition(state, p, action, params)


def _scanned(shipping: Json, p: Json, tick: int, age: int) -> None:
    pallet = shipping["open_pallet"]
    pallet["reserved"] -= 1
    pallet["parcels"].append(p["parcel_id"])
    if pallet["first_placement_tick"] is None:
        pallet["first_placement_tick"] = tick
        pallet["expires_tick"] = tick + age if pallet["state"] == "OPEN" else None
    shipping["scanning"] = [
        scan for scan in shipping["scanning"] if scan["actor_id"] != p["actor_id"]
    ]


def _receipt(receiving: Json, pallet: str) -> Json:
    return next(item for item in receiving["area"] if item["pallet_id"] == pallet)


def _attached(state: Json, p: Json, params: Json) -> None:
    route = params["vehicles"][p["vehicle_id"]]["route"]
    if route == "inbound":
        state["receiving"]["area"] = [
            pal for pal in state["receiving"]["area"] if pal["pallet_id"] != p["cargo_id"]
        ]
    else:
        shipping = state["shipping"]
        pallet = next(pal for pal in shipping["sealed_queue"] if pal["pallet_id"] == p["cargo_id"])
        shipping["sealed_queue"].remove(pallet)
        shipping["outbound"]["carrying"] = {
            "pallet_id": p["cargo_id"],
            "state": "CLAIMED",
            "parcels": pallet["parcels"],
        }


def _actor_transition(state: Json, payload: Json, action: Json | None, params: Json) -> None:
    driver = next(
        (v for v in params["vehicles"].values() if v["actor_id"] == payload["actor_id"]), None
    )
    if action is None:
        if driver and payload["state"] == "IDLE":
            if driver["route"] == "inbound":
                state["receiving"]["forklift_busy"] = False
            else:
                state["shipping"]["outbound"]["busy"] = False
        return
    operation, entity = action["operation"], action["entity_id"]
    if operation == "scan":
        state["shipping"]["buffer"].remove(f"PCL_{entity}")
        state["shipping"]["open_pallet"]["reserved"] += 1
        state["shipping"]["scanning"].append(
            {
                "actor_id": action["actor_id"],
                "order_id": entity,
                "until_tick": round(action["scheduled_end_s"] * params["ticks_per_second"]),
            }
        )
    elif operation == "receive":
        _receipt(state["receiving"], entity)["state"] = "IN_SERVICE"
    elif (
        driver
        and operation == "travel_empty"
        and action["destination_node_id"] in {"FI_PICK", "FO_PICK"}
    ):
        _claim(state, entity, driver["route"])


def _claim(state: Json, pallet_id: str, route: str) -> None:
    if route == "inbound":
        receiving = state["receiving"]
        receiving["forklift_busy"] = True
        receiving["staging_used"] += 1
        _receipt(receiving, pallet_id)["state"] = "CLAIMED"
    else:
        shipping = state["shipping"]
        shipping["outbound"]["busy"] = True
        shipping["outbound"]["tasks"].remove(pallet_id)
        pallet = next(p for p in shipping["sealed_queue"] if p["pallet_id"] == pallet_id)
        pallet["state"] = "CLAIMED"
