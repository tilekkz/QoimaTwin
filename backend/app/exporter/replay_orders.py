"""Order, tote, packing and belt ownership replay from public records."""

from typing import Any

type Json = dict[str, Any]


def apply_order(state: Json, event: Json, params: Json) -> None:
    p, kind = event["payload"], event["kind"]
    orders, totes = state["orders"], state["totes"]
    if kind == "order_arrived":
        orders["queue"].append(p["order_id"])
        orders["counts"]["arrived"] += 1
        orders["status"][p["order_id"]] = "queued"
    elif kind == "order_assigned":
        orders["queue"].remove(p["order_id"])
        orders["picking"].append({key: p[key] for key in ("order_id", "actor_id", "tote_id")})
        orders["status"][p["order_id"]] = "admitted"
        totes["free"].remove(p["tote_id"])
        totes["allocated"].append(p["tote_id"])
    elif kind == "order_rejected_inventory":
        orders["queue"].remove(p["order_id"])
        orders["counts"]["rejected"] += 1
        orders["status"][p["order_id"]] = "unfulfilled_inventory"
    elif kind == "order_dispatched":
        orders["status"][p["order_id"]] = "dispatched"
        orders["counts"]["dispatched"] += 1
    elif kind == "handoff_ready":
        station(state, p["target_pack_id"])["reserved_wip"] += 1
        _register(
            state,
            p["tote_id"],
            "tote",
            p["order_id"],
            p["target_pack_id"],
            params["induction_inlets"][p["induction_id"]],
            event["at_tick"],
            p["actor_id"],
        )
    elif kind == "tote_inducted":
        orders["picking"] = [job for job in orders["picking"] if job["order_id"] != p["order_id"]]
        _admitted(state, p["tote_id"])
    elif kind in {"pack_started", "order_packed", "parcel_outfed"}:
        _packing(state, event, params)


def _register(
    state: Json, cargo: str, kind: str, order: str, target: str, inlet: str, ready: int, owner: str
) -> None:
    state["conveyor"]["cargo"].append(
        {"cargo_id": cargo, "kind": kind, "order_id": order, "target": target}
    )
    state["conveyor"]["admissions"].append(
        {"inlet": inlet, "cargo_id": cargo, "ready_tick": ready, "owner": owner}
    )


def _admitted(state: Json, cargo: str) -> None:
    state["conveyor"]["admissions"] = [
        a for a in state["conveyor"]["admissions"] if a["cargo_id"] != cargo
    ]


def station(state: Json, pack_id: str) -> Json:
    return next(s for s in state["stations"] if s["pack_id"] == pack_id)


def _packing(state: Json, event: Json, params: Json) -> None:
    p, kind = event["payload"], event["kind"]
    post = station(state, p["pack_id"])
    if kind == "pack_started":
        post["waiting"].remove(p["tote_id"])
        post["in_service"] = p["tote_id"]
        cargo = next(c for c in post["cargo"] if c["cargo_id"] == p["tote_id"])
        post["cargo"].remove(cargo)
        post["cargo"].append(cargo)
    elif kind == "order_packed":
        post["in_service"] = None
        post["cargo"] = [c for c in post["cargo"] if c["cargo_id"] != p["tote_id"]]
        post["blocked_parcel"], post["blocked_since"] = p["parcel_id"], event["at_tick"]
        state["orders"]["counts"]["packed"] += 1
        state["orders"]["status"][p["order_id"]] = "packed"
        state["totes"]["allocated"].remove(p["tote_id"])
        state["totes"]["free"].append(p["tote_id"])
        _register(
            state,
            p["parcel_id"],
            "parcel",
            p["order_id"],
            "SHIPPING",
            params["pack_outlets"][p["pack_id"]],
            event["at_tick"],
            p["pack_id"],
        )
    else:
        post["blocked_parcel"], post["blocked_since"] = None, None
        post["reserved_wip"] -= 1
        _admitted(state, p["parcel_id"])


def apply_cells(state: Json, events: list[Json], params: Json, known: set[str]) -> None:
    cells, cursors = dict(state["conveyor"]["cells"]), dict(state["conveyor"]["merge_cursors"])
    for event in events:
        p = event["payload"]
        if p["from"] in known and cells.pop(p["from"], None) != p["cargo_id"]:
            raise ValueError("replay cell source/cargo mismatch")
    for event in events:
        p = event["payload"]
        if p["to"] in known:
            if p["to"] in cells:
                raise ValueError("replay cell collision")
            cells[p["to"]] = p["cargo_id"]
            sources = params["merge_predecessors"].get(p["to"], [])
            if len(sources) > 1 and p["from"] in known:
                cursors[p["to"]] = (sources.index(p["from"]) + 1) % len(sources)
        else:
            _exit(state, p)
    state["conveyor"]["cells"] = sorted([cell, cargo] for cell, cargo in cells.items())
    state["conveyor"]["merge_cursors"] = sorted([cell, cursor] for cell, cursor in cursors.items())


def _exit(state: Json, payload: Json) -> None:
    cargo = next(c for c in state["conveyor"]["cargo"] if c["cargo_id"] == payload["cargo_id"])
    state["conveyor"]["cargo"].remove(cargo)
    if payload["to"] != "SHIPPING":
        post = station(state, payload["to"])
        post["waiting"].append(cargo["cargo_id"])
        post["cargo"].insert(len(post["waiting"]) - 1, cargo)
