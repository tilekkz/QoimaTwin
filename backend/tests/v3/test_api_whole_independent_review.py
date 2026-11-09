"""Adjacent HTTP integrity probes use an explicit hand fixture, never source admission."""

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.api_whole_identity import public_run_id
from tests.v3.test_api_whole_fixtures import WholeApi, registered_hand_whole_api  # noqa: F401


@pytest.mark.parametrize("change", ["missing_native_metadata", "swapped_outer_roles"])
def test_rehashed_inventory_cannot_hide_nested_missing_or_misbound_files(
    whole_api: WholeApi, change: str
) -> None:
    api = whole_api
    assert api.client.get(api.base).status_code == 200
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    index = api.store.read_reference("runs", api.response["run_id"])
    if change == "missing_native_metadata":
        index["files"] = [row for row in index["files"] if row["path"] != "metadata.json"]
    else:
        for row in index["request_files"]:
            if row["path"] in {"profile.json", "request.json"}:
                row["path"] = "request.json" if row["path"] == "profile.json" else "profile.json"
    try:
        path.write_bytes(canonical_bytes({"content_sha256": sha256_hex(index), "value": index}))
        response = api.client.get(api.base + "/manifest")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
        assert len(api.processor.calls) == 1
    finally:
        path.write_bytes(original)


def test_another_canonical_registration_id_cannot_relabel_this_existing_run(
    whole_api: WholeApi,
) -> None:
    api = whole_api
    index = api.store.read_reference("runs", api.response["run_id"])
    alternate = public_run_id(index["native_run_id"], "c" * 64)
    assert alternate != index["run_id"]
    index.update(run_id=alternate, input_bundle_id="c" * 64)
    api.store.publish_reference("runs", alternate, index)
    try:
        response = api.client.get("/api/v3/whole-runs/" + alternate)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
        assert len(api.processor.calls) == 1
    finally:
        api.store.path("runs", alternate).unlink()


def test_half_open_event_boundary_preserves_actual_ship_and_future_paid_return(
    whole_api: WholeApi,
) -> None:
    api = whole_api
    before = api.client.get(api.base + "/events?start_tick=46000000&end_tick=47000000")
    at = api.client.get(api.base + "/events?start_tick=47000000&end_tick=47000001")
    assert before.status_code == at.status_code == 200
    assert all(row["tick"] < 47_000_000 for row in before.json()["events"])
    shipped = [row for row in at.json()["events"] if row["kind"] == "whole_shipped"]
    assert len(shipped) == 1 and shipped[0]["tick"] == 47_000_000
    cap = api.client.get(api.base + "/checkpoint?tick=47000000").json()["checkpoint"]
    worker = next(row for row in cap["state"]["workers"] if row["actor_id"] == "S01")
    assert worker["node"] is None and worker["operation"]["kind"] == "whole_return"
    assert worker["operation"]["start_tick"] == 47_000_000
    assert worker["operation"]["planned_end_tick"] == 52_000_000
    assert cap["state"]["whole_orders"][0]["returned_tick"] is None
    assert api.client.get(api.base).json()["status"] == "partial"
    assert api.client.get(api.base + "/checkpoint?tick=52000000").status_code == 422
    assert (
        api.client.get(api.base + "/events?start_tick=47000000&end_tick=52000001").status_code
        == 422
    )
