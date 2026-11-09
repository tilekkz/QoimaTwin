"""Actual receipts appear only after creation; HTTP caches never bless corrupted bytes."""

from hashlib import sha256

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.api_receipt_inputs import FrozenReceiptProfile
from tests.v3.test_api_receipt_fixtures import ReceiptApi, registered_receipt_api  # noqa: F401


def test_repeat_post_and_all_export_files_match_the_cli_bytes(receipt_api: ReceiptApi) -> None:
    api = receipt_api
    again = api.client.post("/api/v3/receipt-runs", json=api.body)
    assert again.status_code == 200 and again.json() == api.response
    assert len(api.processor.calls) == 1
    assert api.client.get(api.base).json() == api.response
    assert api.response["status"] == "complete" and api.response["operational_admission"] is False
    manifest = api.client.get(api.base + "/manifest").json()
    assert manifest["transport"]["run_id"] == api.response["native_run_id"]
    for row in manifest["files"]:
        response = api.client.get(api.base + "/files/" + row["sha256"])
        assert response.status_code == 200 and len(response.content) == row["bytes"]
        assert response.content == (api.processor.artifact / row["path"]).read_bytes()
        assert sha256(response.content).hexdigest() == row["sha256"]
        assert response.headers["etag"] == '"' + row["sha256"] + '"'


def test_future_receipt_is_absent_initially_and_created_once_at_horizon(
    receipt_api: ReceiptApi,
) -> None:
    api = receipt_api
    initial = api.client.get(api.base + "/checkpoint?tick=0").json()["checkpoint"]
    horizon = api.client.get(api.base + "/checkpoint?tick=1200000000").json()["checkpoint"]
    assert len(initial["state"]["stock"]["locations"]) == 12256
    assert len(horizon["state"]["stock"]["locations"]) == 12256 + 24
    assert horizon["state"]["balance"]["shipped_units_by_sku"] == [["DEMO_001", 3]]
    assert api.client.get(api.base + "/checkpoint?tick=0").json()["checkpoint"] == initial
    window = api.client.get(api.base + "/events?start_tick=0&end_tick=60000000")
    assert window.status_code == 200 and window.json()["events"]
    assert all(0 <= event["tick"] < 60_000_000 for event in window.json()["events"])
    assert api.client.get(api.base + "/seek?cutoff_tick=0").status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        "/checkpoint?tick=1",
        "/checkpoint?tick=true",
        "/checkpoint?tick=1.0",
        "/events?start_tick=0&end_tick=60000001",
        "/events?start_tick=10&end_tick=9",
    ],
)
def test_uncaptured_ticks_and_bad_windows_reject(receipt_api: ReceiptApi, suffix: str) -> None:
    response = receipt_api.client.get(receipt_api.base + suffix)
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_input"


def test_warm_cache_cannot_hide_raw_artifact_tampering(receipt_api: ReceiptApi) -> None:
    api = receipt_api
    manifest = api.client.get(api.base + "/manifest").json()["transport"]
    path = api.store.path("run_files", manifest["event_chunks"][-1]["sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(b"corrupt")
        result = api.client.post("/api/v3/receipt-runs", json=api.body)
        assert result.status_code == 500 and result.json()["error"]["code"] == "artifact_corruption"
        assert api.client.get(api.base + "/checkpoint?tick=0").status_code == 500
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("field", ["status", "capability"])
def test_cached_response_cannot_override_actual_run(receipt_api: ReceiptApi, field: str) -> None:
    api = receipt_api
    bundle = api.processor.calls[0].payload["receipt_bundle_id"]
    snapshot = api.store.read_json("bundles", bundle)
    key = FrozenReceiptProfile(bundle, {"input_hash": snapshot["input_hash"]}).key()
    path = api.store.path("requests", key)
    original = path.read_bytes()
    value = api.store.read_reference("requests", key)
    if field == "status":
        value["status"] = "partial"
    else:
        value["capabilities"]["hand_contact_proof"] = True
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(value), "value": value}))
        response = api.client.post("/api/v3/receipt-runs", json=api.body)
        assert (
            response.status_code == 500
            and response.json()["error"]["code"] == "artifact_corruption"
        )
    finally:
        path.write_bytes(original)
