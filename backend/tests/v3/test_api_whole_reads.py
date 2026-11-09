"""Nested whole artifacts retain actual paid return and are rehashed before cached reads."""

from hashlib import sha256

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from tests.v3.test_api_whole_fixtures import WholeApi, registered_hand_whole_api  # noqa: F401


def test_repeat_submit_and_native_plus_outer_bytes_are_exact(whole_api: WholeApi) -> None:
    api = whole_api
    repeated = api.client.post("/api/v3/whole-runs", json=api.body)
    assert repeated.json() == api.response and len(api.processor.calls) == 1
    assert api.response["status"] == "partial"
    manifest = api.client.get(api.base + "/manifest").json()
    assert manifest["transport"]["run_id"] == api.response["native_run_id"]
    for group, root in (
        ("files", api.processor.artifact / "run"),
        ("request_files", api.processor.artifact),
    ):
        for row in manifest[group]:
            response = api.client.get(api.base + "/files/" + row["sha256"])
            assert response.status_code == 200
            assert response.content == (root / row["path"]).read_bytes()
            assert sha256(response.content).hexdigest() == row["sha256"]
            assert response.headers["etag"] == '"' + row["sha256"] + '"'


def test_exact_cap_capture_contains_ship_but_open_paid_return(whole_api: WholeApi) -> None:
    api = whole_api
    cap = api.client.get(api.base + "/checkpoint?tick=47000000").json()["checkpoint"]
    assert cap["state"]["whole_orders"][0]["shipped_tick"] == 47_000_000
    assert cap["state"]["whole_orders"][0]["returned_tick"] is None
    assert len(cap["state"]["leases"]) == 1
    window = api.client.get(api.base + "/events?start_tick=46000000&end_tick=47000001")
    assert window.status_code == 200
    assert any(row["tick"] == 47_000_000 for row in window.json()["events"])
    assert api.client.get(api.base + "/seek?tick=47000000").status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        "/checkpoint?tick=1",
        "/checkpoint?tick=true",
        "/events?start_tick=0&end_tick=60000001",
        "/events?start_tick=10&end_tick=9",
    ],
)
def test_uncaptured_or_unobserved_queries_reject(whole_api: WholeApi, suffix: str) -> None:
    assert whole_api.client.get(whole_api.base + suffix).status_code == 422


def test_unrelated_store_blob_is_not_an_authorized_run_file(whole_api: WholeApi) -> None:
    unrelated = whole_api.store.put_bytes("run_files", b"unrelated")
    assert whole_api.client.get(whole_api.base + "/files/" + unrelated).status_code == 404


def test_unknown_public_run_stays_not_found(whole_api: WholeApi) -> None:
    unknown = "f" * 64
    assert unknown != whole_api.response["run_id"]
    response = whole_api.client.get("/api/v3/whole-runs/" + unknown)
    assert response.status_code == 404
    assert len(whole_api.processor.calls) == 1


def test_warm_reader_still_rehashes_outer_request(whole_api: WholeApi) -> None:
    api = whole_api
    api.client.get(api.base)
    path = api.store.path("run_files", api.response["request_sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(b"corrupt request evidence")
        assert api.client.get(api.base).status_code == 500
    finally:
        path.write_bytes(original)


def test_cached_complete_cannot_override_actual_partial(whole_api: WholeApi) -> None:
    api = whole_api
    path = api.store.path("requests", api.frozen.key())
    raw = path.read_bytes()
    changed = {**api.response, "status": "complete"}
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(changed), "value": changed}))
        response = api.client.post("/api/v3/whole-runs", json=api.body)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(raw)


@pytest.mark.parametrize(
    "change",
    [
        {"profile_path": "unregistered.json"},
        {"horizon_tick": 1},
        {"source_revision": "another revision"},
        {"layout_version": "another layout"},
    ],
)
def test_profile_overrides_reject_without_scheduling(
    whole_api: WholeApi, change: dict[str, object]
) -> None:
    api = whole_api
    assert api.client.post("/api/v3/whole-runs", json={**api.body, **change}).status_code == 422
    assert len(api.processor.calls) == 1


def test_rehashed_outer_result_cannot_override_native_terminal_state(whole_api: WholeApi) -> None:
    api = whole_api
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    index = api.store.read_reference("runs", api.response["run_id"])
    row = next(r for r in index["request_files"] if r["path"] == "result.json")
    changed = api.store.read_json("run_files", row["sha256"])
    changed["status"] = "complete"
    raw = canonical_bytes(changed)
    row.update(sha256=api.store.put_bytes("run_files", raw), bytes=len(raw))
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(index), "value": index}))
        response = api.client.get(api.base)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
