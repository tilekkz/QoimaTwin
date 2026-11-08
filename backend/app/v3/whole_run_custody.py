"""Stage-aware original-wrapper authority; balanced arbitrary baseline moves still fail."""

from app.v3.interface import Json
from app.v3.receipt_run_journal import InventoryJournal, same
from app.v3.whole_run_facts import WholeFacts
from app.v3.whole_run_operations import WholeOperations

HANDOFFS = {
    "whole_picked": "whole_pick_slot",
    "whole_buffered": "whole_place_buffer",
    "whole_buffer_picked": "whole_pick_buffer",
    "whole_shipped": "whole_service",
}


def guard_delta(event: Json, facts: WholeFacts, operations: WholeOperations) -> None:
    delta, key, kind = event["delta"], event["order_id"], event["kind"]
    if kind in HANDOFFS and delta is None:
        raise ValueError("Whole physical handoff lost its actual stock transaction")
    if delta is None or delta["delta_type"] == "receipt_creation":
        return
    if kind in HANDOFFS:
        operations.handoff(event, HANDOFFS[kind])
        _whole_delta(event, facts)
        return
    original = {u["origin_hu"] for u in facts.inventory.units.values()}
    before = {r["container"]["container_id"]: r["container"] for r in delta["before"]}
    for row in delta["after"]:
        container = row["container"]
        hu = container["container_id"]
        if hu in original and before[hu]["owner_id"] != container["owner_id"]:
            allowed = {"receipt_buffered", "receipt_buffer_picked", "receipt_putaway"}
            if key not in facts.inventory.offers or kind not in allowed:
                raise ValueError(
                    "Unadmitted baseline wrapper moved without actual whole-HU operation"
                )
            if facts.inventory.offers[key]["definition"]["hu_id"] != hu:
                raise ValueError("Receipt handoff changed another physical wrapper")


def _whole_delta(event: Json, facts: WholeFacts) -> None:
    key, view, delta = event["order_id"], event["whole_order"], event["delta"]
    order = facts.orders[key]
    hu, actor = order["hu_id"], "actor:" + str(view["actor_id"])
    if event["actor_id"] != view["actor_id"] or "whole:" + key not in facts.claims:
        raise ValueError("Whole handoff lacks its assigned actor or complete inventory claim")
    expected = {
        "whole_picked": actor,
        "whole_buffered": view["buffer_owner_id"],
        "whole_buffer_picked": actor,
        "whole_shipped": facts.ports[order["port_id"]]["shipped_owner"],
    }
    operation = "ship_whole_hu" if event["kind"] == "whole_shipped" else "transfer_whole_hu"
    if delta["operation"] != operation or len(delta["before"]) != 1 or len(delta["after"]) != 1:
        raise ValueError("Whole handoff is not an intact one-wrapper transaction")
    before, after = delta["before"][0], delta["after"][0]
    if before["container"]["container_id"] != hu or after["container"]["container_id"] != hu:
        raise ValueError("Whole handoff changes another container identity")
    same(
        before["container"]["sealed_for"],
        after["container"]["sealed_for"],
        "Intact original wrapper cannot change parcel seal during whole movement",
    )
    same(
        before["units"], after["units"], "Whole operation split or rearranged unsupported contents"
    )
    same(
        sorted(delta["unit_ids"]),
        sorted(facts.claims["whole:" + key]["unit_ids"]),
        "Whole handoff did not move exactly the reserved physical ancestry",
    )
    if after["container"]["owner_id"] != expected[event["kind"]]:
        raise ValueError("Whole handoff owner differs from its actual physical stage")


def check_custody(state: Json, facts: WholeFacts, inventory: InventoryJournal) -> None:
    whole = {r["job_id"]: r for r in state["whole_orders"]}
    whole_hus = {
        facts.orders[k]["hu_id"]: row for k, row in whole.items() if row["picked_tick"] is not None
    }
    for row in whole.values():
        if row["admitted_tick"] is None:
            continue
        order = facts.orders[row["job_id"]]
        expected = _whole_owner(row, facts, inventory)
        if inventory.containers[order["hu_id"]]["owner_id"] != expected:
            raise ValueError("Whole captured custody differs from performed movement stages")
        claim = facts.claims.get("whole:" + row["job_id"])
        if (claim is not None) != (row["shipped_tick"] is None):
            raise ValueError("Whole actual claim must persist until business handover")
    _receipts(state, whole_hus, facts, inventory)


def _whole_owner(row: Json, facts: WholeFacts, inventory: InventoryJournal) -> str:
    order = facts.orders[row["job_id"]]
    if row["shipped_tick"] is not None:
        return str(facts.ports[order["port_id"]]["shipped_owner"])
    if row["buffered_tick"] is not None and row["buffer_picked_tick"] is None:
        return str(row["buffer_owner_id"])
    if row["picked_tick"] is not None:
        return "actor:" + str(row["actor_id"])
    original = next(
        (
            c["initial_owner_id"]
            for c in inventory.catalog["initial_containers"]
            if c["container_id"] == order["hu_id"]
        ),
        None,
    )
    if original is not None:
        return str(original)
    return str(
        next(
            o["slot_owner_id"]
            for o in inventory.offers.values()
            if o["definition"]["hu_id"] == order["hu_id"]
        )
    )


def _receipts(
    state: Json, moved: dict[str, Json], facts: WholeFacts, inventory: InventoryJournal
) -> None:
    for row in state["receipts"]:
        key = row["receipt_id"]
        offer = inventory.offers[key]
        if (row["credited_tick"] is not None) != (key in inventory.registered):
            raise ValueError("Receipt chronology differs from actual inventory creation")
        if row["credited_tick"] is None:
            continue
        hu = offer["definition"]["hu_id"]
        owner = (
            offer["slot_owner_id"]
            if row["placed_tick"] is not None
            else (
                row["buffer_owner_id"]
                if row["status"] == "buffered"
                else "actor:" + str(row["actor_id"])
            )
        )
        if hu in moved:
            if row["placed_tick"] is None:
                raise ValueError("Whole pickup occurred before actual receipt putaway")
            owner = _whole_owner(moved[hu], facts, inventory)
        if inventory.containers[hu]["owner_id"] != owner:
            raise ValueError("Receipt/whole captured physical custody differs")
        if ("receipt:" + key in facts.claims) != (row["placed_tick"] is None):
            raise ValueError("Receipt claim must persist until actual putaway")
