"""Actual source bytes drive HTTP reads; cached responses cannot legitimize tampering."""

from hashlib import sha256

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.api_light_inputs import FrozenLightProfile
from tests.v3.test_api_light_fixtures import LightApi, registered_light_api  # noqa: F401


def test_repeat_post_status_and_every_raw_file_preserve_identity(light_api: LightApi) -> None:
    api = light_api
    again = api.client.post("/api/v3/light-runs", json=api.body)
    assert again.status_code == 200 and again.json() == api.response
    assert len(api.processor.calls) == 1
    assert api.client.get(api.base).json() == api.response
    assert api.response["status"] == "complete" and api.response["operational_admission"] is False
    assert not api.response["capabilities"]["arbitrary_seek"]
    manifest = api.client.get(api.base + "/manifest").json()
    assert manifest["transport"]["run_id"] == api.response["native_run_id"]
    for row in manifest["files"]:
        response = api.client.get(api.base + "/files/" + row["sha256"])
        assert response.status_code == 200 and len(response.content) == row["bytes"]
        assert sha256(response.content).hexdigest() == row["sha256"]
        assert response.headers["etag"] == '"' + row["sha256"] + '"'


def test_exact_checkpoint_and_half_open_window_preserve_source_stock(light_api: LightApi) -> None:
    api = light_api
    initial = api.client.get(api.base + "/checkpoint?tick=0").json()["checkpoint"]
    horizon = api.client.get(api.base + "/checkpoint?tick=600000000").json()["checkpoint"]
    assert len(initial["state"]["stock"]["locations"]) == 12256
    assert horizon["state"]["balance"]["shipped_units_by_sku"] == [["DEMO_001", 3]]
    assert api.client.get(api.base + "/checkpoint?tick=0").json()["checkpoint"] == initial
    window = api.client.get(api.base + "/events?start_tick=0&end_tick=60000000")
    assert window.status_code == 200 and window.json()["events"]
    assert all(0 <= e["tick"] < 60_000_000 for e in window.json()["events"])
    assert api.client.get(api.base + "/seek?cutoff_tick=0").status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        "/checkpoint?tick=1",
        "/checkpoint?tick=-1",
        "/checkpoint?tick=1.0",
        "/checkpoint?tick=true",
        "/events?start_tick=0&end_tick=60000001",
        "/events?start_tick=10&end_tick=9",
        "/events?start_tick=0&end_tick=999999999999",
        "/events?start_tick=0.0&end_tick=1",
    ],
)
def test_bad_windows_and_uncaptured_ticks_are_typed_422(light_api: LightApi, suffix: str) -> None:
    response = light_api.client.get(light_api.base + suffix)
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_input"


def test_unknown_run_and_file_are_404(light_api: LightApi) -> None:
    assert light_api.client.get("/api/v3/light-runs/" + "f" * 64).status_code == 404
    assert light_api.client.get(light_api.base + "/files/" + "f" * 64).status_code == 404


def test_raw_tamper_after_cache_warm_is_rejected(light_api: LightApi) -> None:
    api = light_api
    manifest = api.client.get(api.base + "/manifest").json()["transport"]
    path = api.store.path("run_files", manifest["event_chunks"][-1]["sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(b"corrupt")
        response = api.client.post("/api/v3/light-runs", json=api.body)
        assert (
            response.status_code == 500
            and response.json()["error"]["code"] == "artifact_corruption"
        )
        assert api.client.get(api.base + "/checkpoint?tick=0").status_code == 500
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("field", ["native_run_id", "input_bundle_id"])
def test_foreign_native_or_profile_index_rejected_after_cache(
    light_api: LightApi, field: str
) -> None:
    api = light_api
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    value = api.store.read_reference("runs", api.response["run_id"])
    value[field] = "e" * 64
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(value), "value": value}))
        response = api.client.get(api.base + "/manifest")
        assert (
            response.status_code == 500
            and response.json()["error"]["code"] == "artifact_corruption"
        )
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("field", ["status", "capability"])
def test_cached_request_response_is_verified_against_actual_run(
    light_api: LightApi, field: str
) -> None:
    api = light_api
    bundle = api.processor.calls[0].payload["light_bundle_id"]
    snapshot = api.store.read_json("bundles", bundle)
    key = FrozenLightProfile(bundle, {"input_hash": snapshot["input_hash"]}).key()
    path = api.store.path("requests", key)
    original = path.read_bytes()
    value = api.store.read_reference("requests", key)
    if field == "status":
        value["status"] = "failed"
    else:
        value["capabilities"]["hand_contact_proof"] = True
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(value), "value": value}))
        result = api.client.post("/api/v3/light-runs", json=api.body)
        assert result.status_code == 500 and result.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
