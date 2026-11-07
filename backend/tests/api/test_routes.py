"""Every required HTTP route has strict, explicit request boundaries."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job
from app.api.service import BusyError
from app.storage.artifacts import ArtifactStore

BASE = {"schema_version": "2.0", "layout_version": "qoima-72x48-v2"}


class FakeProcessor:
    def __init__(self) -> None:
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> dict[str, Any]:
        self.calls.append(job)
        return {"status": "passed", "kind": job.kind}


def test_catalog_exposes_versions_and_persisted_assignment(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, processor=FakeProcessor())) as client:
        response = client.get("/api/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["layout_version"] == BASE["layout_version"]
        assert len(data["sku_ids"]) == 200  # 01 section8 frozen DEMO catalog
        assert ArtifactStore(tmp_path).read_json("assignments", data["assignment_id"])


@pytest.mark.parametrize(
    ("route", "fields", "kind"),
    [
        ("scenarios/materialize", {"profile": "large-normal", "horizon_s": 60}, "materialize"),
        ("forecast", {"history_id": "histories", "model": "mean28"}, "forecast"),
        (
            "plans",
            {"scenario_id": "scenarios", "forecast_id": "forecasts", "budget_swaps": 2},
            "plans",
        ),
        ("compare", {"scenario_id": "scenarios", "plan_id": "plans"}, "compare"),
    ],
)
def test_post_routes_validate_refs_and_reuse_completed_request(
    tmp_path: Path, route: str, fields: dict[str, Any], kind: str
) -> None:
    store, processor = ArtifactStore(tmp_path), FakeProcessor()
    refs = {
        name: store.put_json(name, {"test": name})
        for name in ("histories", "scenarios", "forecasts", "plans")
    }
    body = {**BASE, **{k: refs.get(v, v) if isinstance(v, str) else v for k, v in fields.items()}}
    with TestClient(create_app(tmp_path, processor=processor)) as client:
        first, second = (
            client.post(f"/api/{route}", json=body),
            client.post(f"/api/{route}", json=body),
        )
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json() == {"status": "passed", "kind": kind}
    assert len(processor.calls) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"horizon_s": 0},
        {"horizon_s": True},
        {"horizon_s": "60"},
        {"horizon_s": 604801},
        {"schema_version": "9.9"},
        {"layout_version": "unknown"},
        {"unexpected": 1},
    ],
)
def test_bad_quantities_versions_and_extra_fields_return_json_422(
    tmp_path: Path, updates: dict[str, Any]
) -> None:
    processor = FakeProcessor()
    with TestClient(create_app(tmp_path, processor=processor)) as client:
        body = {**BASE, "profile": "large-normal", "horizon_s": 60, **updates}
        response = client.post("/api/scenarios/materialize", json=body)
        assert response.status_code == 422
        assert response.json()["status"] == "failed"
        assert response.json()["error"]["code"] == "invalid_input"
    assert processor.calls == []


def test_unknown_reference_is_422_and_missing_run_is_404(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, processor=FakeProcessor())) as client:
        bad = client.post("/api/forecast", json={**BASE, "history_id": "0" * 64})
        assert bad.status_code == 422
        assert client.get(f"/api/runs/{'0' * 64}/manifest").status_code == 404
        assert client.get("/api/runs/not-a-hash/manifest").status_code == 422


def test_run_manifest_and_chunks_are_bounded_and_keep_raw_hashes(tmp_path: Path) -> None:
    store, run_id = ArtifactStore(tmp_path), "a" * 64
    descriptors = []
    for index in range(5):
        digest = store.put_json("run_files", {"events": [index]})
        descriptors.append(
            {
                "sha256": digest,
                "bytes": len(store.read_bytes("run_files", digest)),
                "start_s": index * 60,
                "end_s": (index + 1) * 60,
            }
        )
    catalog = store.put_json("run_files", {"cargo": []})
    store.publish_reference(
        "runs", run_id, {"run_id": run_id, "catalog": {"sha256": catalog}, "chunks": descriptors}
    )
    with TestClient(create_app(tmp_path, processor=FakeProcessor())) as client:
        manifest = client.get(f"/api/runs/{run_id}/manifest").json()
        assert manifest["run_id"] == run_id and manifest["catalog_data"] == {"cargo": []}
        response = client.get(f"/api/runs/{run_id}/chunks?from_s=60&limit=2").json()
        assert [row["payload"]["events"] for row in response["chunks"]] == [[1], [2]]
        assert response["chunks"][0]["descriptor"]["sha256"] == descriptors[1]["sha256"]
        assert response["next_from_s"] == 180
        raw = client.get(f"/api/runs/{run_id}/files/{descriptors[1]['sha256']}")
        assert raw.status_code == 200
        assert hashlib.sha256(raw.content).hexdigest() == descriptors[1]["sha256"]
        assert client.get(f"/api/runs/{run_id}/files/{'f' * 64}").status_code == 404
        assert client.get(f"/api/runs/{run_id}/chunks?limit=4").status_code == 422
        assert client.get(f"/api/runs/{run_id}/chunks?from_s=-1").status_code == 422


def test_busy_and_unexpected_execution_errors_are_uniform_json(tmp_path: Path) -> None:
    class FailingProcessor:
        async def execute(self, job: Job) -> dict[str, Any]:
            if job.payload["profile"] == "large-normal":
                raise BusyError("one compare is already running")
            raise RuntimeError("injected calculation failure")

    with TestClient(
        create_app(tmp_path, processor=FailingProcessor()), raise_server_exceptions=False
    ) as client:
        for profile, status in (("large-normal", 409), ("large-peak", 500)):
            response = client.post(
                "/api/scenarios/materialize", json={**BASE, "profile": profile, "horizon_s": 60}
            )
            assert response.status_code == status
            assert response.json()["status"] == "failed"
            assert "message" in response.json()["error"]


@pytest.mark.parametrize("budget", [True, "2", 1, -1, 9])
def test_plan_budget_is_an_exact_supported_integer(tmp_path: Path, budget: Any) -> None:
    processor = FakeProcessor()
    with TestClient(create_app(tmp_path, processor=processor)) as client:
        response = client.post(
            "/api/plans",
            json={**BASE, "scenario_id": "a" * 64, "forecast_id": "b" * 64, "budget_swaps": budget},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_input"
    assert processor.calls == []


def test_lifespan_closes_owned_processor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class OwnedProcessor(FakeProcessor):
        closed = False

        async def close(self) -> None:
            self.closed = True

    processor = OwnedProcessor()
    monkeypatch.setattr("app.api.ProcessProcessor", lambda: processor)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/catalog").status_code == 200
        assert not processor.closed
    assert processor.closed


def test_completed_request_survives_app_restart(tmp_path: Path) -> None:
    body = {**BASE, "profile": "large-normal", "horizon_s": 60}
    with TestClient(create_app(tmp_path, processor=FakeProcessor())) as client:
        first = client.post("/api/scenarios/materialize", json=body)
        assert first.status_code == 200
    fresh = FakeProcessor()
    with TestClient(create_app(tmp_path, processor=fresh)) as client:
        second = client.post("/api/scenarios/materialize", json=body)
        assert second.json() == first.json()
        assert second.status_code == 200
    assert fresh.calls == []
