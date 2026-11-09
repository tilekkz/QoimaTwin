"""HTTP/storage controls with explicit producer/validator doubles; no source or fit work."""

import asyncio
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job
from app.api.worker import execute_job
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3 import api_offer_planning_worker as worker
from app.v3.api_offer_planning_inputs import DOMAIN
from app.v3.input_pin import LAYOUT_VERSION, SOURCE_REVISION
from app.v3.offer_planning_cli_models import STAGES, PlanningFiles
from app.v3.offer_planning_cli_storage import freeze_request, prepare_output, put
from app.v3.whole_profile_geometry import ROUTE_POLICY


def body() -> dict[str, Any]:
    history = {
        "target_unit": "outbound_whole_hu_offers",
        "test_day": "2026-04-01",
        "timezone_name": "UTC",
        "window_start_second": 0,
        "window_end_second": 28800,
        "provenance": {
            "kind": "declared_synthetic",
            "dataset_id": "hand",
            "generator_id": "explicit",
            "generator_version": "1",
            "seed": 7,
        },
    }
    projection = {
        "policy": {
            "horizon_tick": 4_000_000,
            "inbound_hus": 0,
            "outbound_hus": 4,
            "calendar": "normal",
            "windows": [],
        },
        "port_mix_mode": "source_c10",
        "port_mix": [],
    }
    placement = {
        "policy_id": "hand",
        "candidates": [],
        "permitted_actor_ids": ["S01"],
        "route_policy": ROUTE_POLICY,
        "min_width_m": [7, 10],
        "min_height_m": [9, 5],
        "path_clearance_m": [1, 50],
        "receipt_targets": [],
    }
    return {
        "schema_version": DOMAIN,
        "model": "mean28",
        "layout_version": LAYOUT_VERSION,
        "source_revision": SOURCE_REVISION,
        "acknowledge_bounded_planning": True,
        "history_csv": "date,sku_id,offered_hus\r\n2026-03-31,explicit-hand-sku,1\r\n",
        "history_choices_json": canonical_bytes(history).decode(),
        "projection_choices_json": canonical_bytes(projection).decode(),
        "placement_choices_json": canonical_bytes(placement).decode(),
    }


class DoubleProcessor:
    def __init__(self) -> None:
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> dict[str, Any]:
        self.calls.append(job)
        return (await asyncio.to_thread(execute_job, job)).payload


@dataclass
class ApiCase:
    client: TestClient
    store: ArtifactStore
    processor: DoubleProcessor
    producers: list[str]
    validations: list[Path]


def _result(root: Path) -> dict[str, Any]:
    return {
        "status": "no-op",
        "plan_id": sha256((root / "decision.json").read_bytes()).hexdigest(),
        "semantic_bundle_id": "a" * 64,
        "manifest_sha256": sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "selection_reason": "EXPLICIT_HAND_DOUBLE",
        "unallocated_offers": 3,
        "engine_calls": 0,
        "operational_admission": False,
        "actual_test_stream": False,
        "full_n1_acceptance": False,
    }


def _guards(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.simulation.engine import Engine
    from app.v3 import input_json, inputs, offer_forecast, workload_source
    from app.v3.coordinator_engine import CoordinatorEngine
    from app.v3.light_flow_engine import LightFlowEngine
    from app.v3.receipt_flow_engine import ReceiptFlowEngine
    from app.v3.relocation_engine import RelocationEngine
    from app.v3.staff_registry_source import load_staff_source
    from app.v3.whole_flow_engine import WholeFlowEngine

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Real source, forecast or engine entrypoint is forbidden in short API tests")

    targets = (
        inputs.load_v3_bundle,
        workload_source.load_workload_source,
        offer_forecast.fit_offer_forecast,
        load_staff_source,
        input_json.verified_package,
        input_json.read_bytes,
    )
    for name, module in tuple(sys.modules.items()):
        if name.startswith("app.v3") and module is not None:
            for attribute, value in tuple(vars(module).items()):
                if any(value is target for target in targets):
                    monkeypatch.setattr(module, attribute, forbidden)
    # Existing eager unrelated registration is an explicit startup double, not source acceptance.
    monkeypatch.setattr("app.api.attach_v3_routes", lambda *args: None)
    monkeypatch.setattr("app.api.attach_manual_routes", lambda *args: None)
    for cls in (
        CoordinatorEngine,
        RelocationEngine,
        Engine,
        LightFlowEngine,
        WholeFlowEngine,
        ReceiptFlowEngine,
    ):
        monkeypatch.setattr(cls, "__init__", forbidden)
        monkeypatch.setattr(cls, "run", forbidden)


@pytest.mark.parametrize("hook", ["attach_v3_routes", "attach_manual_routes"])
def test_source_guard_stops_real_eager_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hook: str
) -> None:
    import app.api

    actual = getattr(app.api, hook)
    _guards(monkeypatch)
    monkeypatch.setattr(app.api, hook, actual)
    # Explicit source path also bypasses the unrelated catalog's existing router cache.
    with pytest.raises(pytest.fail.Exception, match="Real source, forecast or engine"):
        create_app(tmp_path / "store", v3_inputs=tmp_path / "must-not-read")


@pytest.fixture
def api_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiCase]:
    _guards(monkeypatch)
    producers: list[str] = []
    validations: list[Path] = []

    def produce(paths: PlanningFiles, model: str, out: Path) -> dict[str, Any]:
        producers.append(model)
        prepare_output(out)
        freeze_request(paths, model, out)
        for name in (*STAGES, "observations", "manifest"):
            put(out, name + ".json", canonical_bytes({"explicit_producer_double": name}))
        return _result(out)

    def validate(root: Path) -> dict[str, Any]:
        validations.append(root)
        assert (root / "raw/history.csv").read_bytes().endswith(b"\r\n")
        return {
            **_result(root),
            "status": "passed",
            "planning_status": "no-op",
            "validation_scope": "data_only_planning_bundle",
        }

    monkeypatch.setattr(worker, "plan_offer_files", produce)
    monkeypatch.setattr(worker, "validate_offer_plan", validate)
    processor = DoubleProcessor()
    with TestClient(
        create_app(tmp_path / "store", processor=processor), raise_server_exceptions=False
    ) as client:
        yield ApiCase(client, ArtifactStore(tmp_path / "store"), processor, producers, validations)


@pytest.mark.parametrize("model", ["mean28", "hgb"])
def test_post_preserves_raw_inputs_and_reuses_one_producer(api_case: ApiCase, model: str) -> None:
    request = {**body(), "model": model}
    first = api_case.client.post("/api/v3/offer-plans", json=request)
    assert first.status_code == 200, first.text
    assert len(api_case.validations) == 1
    second = api_case.client.post("/api/v3/offer-plans", json=request)
    assert second.status_code == 200 and second.json() == first.json()
    result = first.json()
    assert result["status"] == "no-op" and result["unallocated_offers"] == 3
    assert result["operational_admission"] is False
    assert api_case.producers == [model]
    assert [j.kind for j in api_case.processor.calls] == [
        "offer-planning-v3",
        "offer-planning-read-v3",
    ]
    assert len(api_case.validations) == 2
    row = next(r for r in result["files"] if r["path"] == "raw/history.csv")
    assert api_case.store.read_bytes("run_files", row["sha256"]) == request["history_csv"].encode()
    assert "store" not in first.text and "attempt-" not in first.text


@pytest.mark.parametrize("change", ["extra", "model", "ack", "layout", "source", "choices"])
def test_bad_request_is_422_without_worker(api_case: ApiCase, change: str) -> None:
    request = body()
    if change == "extra":
        request["source_path"] = "C:/private"
    elif change == "ack":
        request["acknowledge_bounded_planning"] = 1
    elif change == "choices":
        request["placement_choices_json"] = "{}"
    else:
        request[
            {"model": "model", "layout": "layout_version", "source": "source_revision"}[change]
        ] = "wrong"
    response = api_case.client.post("/api/v3/offer-plans", json=request)
    assert response.status_code == 422, response.text
    assert api_case.processor.calls == []


def test_get_result_and_file_revalidate_in_worker_and_return_exact_bytes(api_case: ApiCase) -> None:
    result = api_case.client.post("/api/v3/offer-plans", json=body()).json()
    base = "/api/v3/offer-plans/" + result["planning_id"]
    response = api_case.client.get(base + "/result")
    assert response.status_code == 200 and response.json() == result
    row = next(r for r in result["files"] if r["path"] == "raw/history.csv")
    file = api_case.client.get(base + "/files/" + row["sha256"])
    assert file.status_code == 200 and file.content == body()["history_csv"].encode()
    assert len(api_case.validations) == 3
    assert [j.kind for j in api_case.processor.calls] == [
        "offer-planning-v3",
        "offer-planning-read-v3",
        "offer-planning-read-v3",
    ]


def test_published_result_recovers_missing_request_cache_without_reproduction(
    api_case: ApiCase,
) -> None:
    first = api_case.client.post("/api/v3/offer-plans", json=body())
    assert first.status_code == 200
    result = first.json()
    api_case.store.path("requests", result["planning_id"]).unlink()
    second = api_case.client.post("/api/v3/offer-plans", json=body())
    assert second.status_code == 200 and second.json() == result
    assert api_case.producers == ["mean28"]


def test_warm_corruption_rejects_post_and_get(api_case: ApiCase) -> None:
    result = api_case.client.post("/api/v3/offer-plans", json=body()).json()
    row = result["files"][0]
    api_case.store.path("run_files", row["sha256"]).write_bytes(b"changed")
    assert api_case.client.post("/api/v3/offer-plans", json=body()).status_code == 500
    assert (
        api_case.client.get("/api/v3/offer-plans/" + result["planning_id"] + "/result").status_code
        == 500
    )
    assert len(api_case.producers) == 1


def test_unknown_or_nonmember_file_is_not_exposed(api_case: ApiCase) -> None:
    assert api_case.client.get("/api/v3/offer-plans/" + "f" * 64 + "/result").status_code == 404
    result = api_case.client.post("/api/v3/offer-plans", json=body()).json()
    unrelated = api_case.store.put_bytes("run_files", b"not-a-member")
    path = "/api/v3/offer-plans/" + result["planning_id"] + "/files/" + unrelated
    assert api_case.client.get(path).status_code == 404


def test_typed_authority_failure_is_not_hidden_by_raw_hashes(
    api_case: ApiCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = api_case.client.post("/api/v3/offer-plans", json=body()).json()

    def fail(root: Path) -> Any:
        raise ValueError("changed producer authority")

    monkeypatch.setattr(worker, "validate_offer_plan", fail)
    path = "/api/v3/offer-plans/" + result["planning_id"] + "/result"
    assert api_case.client.get(path).status_code == 500


def test_cached_post_reauthenticates_typed_authority(
    api_case: ApiCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = api_case.client.post("/api/v3/offer-plans", json=body())
    assert first.status_code == 200

    def fail(root: Path) -> Any:
        raise ValueError("current typed authority differs")

    monkeypatch.setattr(worker, "validate_offer_plan", fail)
    assert api_case.client.post("/api/v3/offer-plans", json=body()).status_code == 500
    assert api_case.producers == ["mean28"]


@pytest.mark.parametrize("bad", [None, {"status": "forged"}])
def test_cached_receipt_shape_and_binding_fail_closed(api_case: ApiCase, bad: Any) -> None:
    first = api_case.client.post("/api/v3/offer-plans", json=body())
    assert first.status_code == 200
    identifier = first.json()["planning_id"]
    envelope = {"content_sha256": sha256_hex(bad), "value": bad}
    api_case.store.path("requests", identifier).write_bytes(canonical_bytes(envelope))
    assert api_case.client.post("/api/v3/offer-plans", json=body()).status_code == 500
    assert api_case.producers == ["mean28"]
