"""Project captured mutable state and retain separate baseline/future immutable identities."""

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.flow_profile_wire import record
from app.v3.interface import Json
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_run_values import checkpoint as receipt_checkpoint
from app.v3.receipt_run_values import event as receipt_event
from app.v3.receipt_transport_inputs import catalog_from_inputs as receipt_catalog
from app.v3.whole_flow_models import WholeFlowSnapshot


def catalog(physical: Json) -> Json:
    result = receipt_catalog(canonical_bytes(physical))
    result["receipt_process"] = {
        **physical["receipt_process"],
        "route_policy": physical["route_policy"],
    }
    result["whole_process"] = physical["whole_process"]
    result["workflow_profile"] = physical["profile"]
    return result


def checkpoint(value: WholeFlowSnapshot) -> Json:
    result = receipt_checkpoint(value)
    result["state"]["whole_orders"] = record(value.whole_orders)
    result["state_hash"] = sha256_hex(result["state"])
    return result


def event(value: FlowEvent) -> Json:
    result = receipt_event(value)
    result.setdefault("whole_order", None)
    return result
