"""Real multi-row receipt tables are sets; future facts still affect immutable identity."""

import hashlib
import json
from copy import deepcopy
from functools import cache
from typing import Any

from app.v3.receipt_profile import CompiledReceiptProfile, compile_receipt_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_receipt_profile_fixtures import ratio, receipt_choices


def two_offers() -> dict[str, Any]:
    value = receipt_choices()
    owner = "synthetic:buffer:IN_E_PARCEL:02"
    value["owners"].extend(
        [
            {"owner_id": owner, "kind": "buffer", "capacity": 1},
            {"owner_id": "actor:R02", "kind": "worker", "capacity": 1},
        ]
    )
    second = deepcopy(value["receipt_buffers"][0])
    second.update(owner_id=owner, bounds_xz=[ratio(x) for x in ("126.4", "58.4", "127.6", "59.6")])
    second["path_xz"] = [
        [ratio(x), ratio(z)]
        for x, z in (("138", "54"), ("138", "63"), ("127", "63"), ("127", "59"))
    ]
    value["receipt_buffers"].append(second)
    value["receipt_ports"][0]["buffer_owner_ids"].append(owner)
    value["receipt_ports"][0]["receiver_ids"].append("R02")
    offer = {
        **value["receipts"][0],
        "receipt_id": "RECEIPT-2",
        "hu_id": "RECEIVED-SMALL-2",
        "slot_id": "v3:slot:SMALL_W:017:L1:B2",
    }
    value["receipts"].append(offer)
    return value


@cache
def compiled_two() -> CompiledReceiptProfile:
    return compile_receipt_profile(source_bundle(), source_catalog(), two_offers())


def test_multirow_permutations_and_unreduced_buffer_ratios_preserve_identity() -> None:
    original = two_offers()
    changed = deepcopy(original)
    for key in ("actors", "owners", "materials", "recipes", "receipts", "receipt_buffers"):
        changed[key].reverse()
    changed["receipt_ports"][0]["receiver_ids"].reverse()
    changed["receipt_ports"][0]["buffer_owner_ids"].reverse()
    for buffer in changed["receipt_buffers"]:
        buffer["height_m"] = {"numerator": 24, "denominator": 20}
    documents = {k: v.canonical_bytes for k, v in source_bundle().documents.items()}
    baseline = compiled_two()
    reordered = compile_receipt_profile(source_bundle(), source_catalog(), changed)
    assert baseline.frozen_bytes == reordered.frozen_bytes
    assert baseline.input_hash == reordered.input_hash
    assert original == two_offers()
    assert documents == {k: v.canonical_bytes for k, v in source_bundle().documents.items()}


def test_future_receipt_lot_changes_identity_without_precrediting_baseline() -> None:
    changed = two_offers()
    changed["receipts"][1]["lot_id"] = "DIFFERENT-EXPLICIT-LOT"
    result = compile_receipt_profile(source_bundle(), source_catalog(), changed)
    baseline = compiled_two()
    before, after = json.loads(baseline.frozen_bytes), json.loads(result.frozen_bytes)
    assert result.input_hash != baseline.input_hash
    assert result.input_hash == hashlib.sha256(result.frozen_bytes).hexdigest()
    assert before["initial_inventory"] == after["initial_inventory"]
    initial = after["initial_inventory"]
    assert initial["revision"] == initial["claim_generation"] == 0
    assert initial["registered_receipts"] == initial["claims"] == []
    assert len(initial["locations"]) == 12256 and len(initial["containers"]) == 532
    assert not any(u["unit_id"].startswith("RECEIVED-") for u in initial["locations"])
    assert after["receipt_process"]["route_policy"] == "c09-manual-small-source-mode-projection-v1"
