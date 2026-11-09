"""Read-only ASGI routes share the existing owned worker with explicit semantic doubles."""

import asyncio
import base64
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import ApiContext, Job
from app.api.worker import execute_job
from app.storage.canonical_json import parse_json
from app.v3 import api_relocation_pair_worker as worker
from app.v3.relocation_pair_publication import publish_pair
from tests.v3.test_relocation_pair_publication import PairCase
from tests.v3.test_relocation_pair_publication import pair_case as pair_case


class Processor:
    def __init__(self) -> None:
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> dict[str, Any]:
        self.calls.append(job)
        return (await asyncio.to_thread(execute_job, job)).payload


@pytest.fixture
def api_case(pair_case: PairCase, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from tests.v3.test_api_offer_planning import _guards

    _guards(monkeypatch)
    result = publish_pair(pair_case.root, pair_case.store_root)
    processor = Processor()
    app = create_app(pair_case.store_root, processor=processor)
    monkeypatch.setattr(
        worker,
        "replay_relocation_run",
        lambda run, *, inputs, tick: {
            "tick": tick,
            "run_id": run["run_id"],
            "snapshot": {"explicit_replay_double": True},
        },
    )
    with TestClient(app) as client:
        yield client, result["pair_id"], processor, pair_case


def test_result_manifest_file_and_bundle(api_case: Any) -> None:
    client, identifier, processor, case = api_case
    base = f"/api/v3/relocation-pairs/{identifier}"
    assert client.get(base + "/result").json()["comparison"]["status"] == "partial"
    manifest = client.get(base + "/arms/candidate/manifest").json()
    artifact = next(r for r in manifest["files"] if r["path"] == "events/0.json")
    response = client.get(base + "/arms/candidate/files/" + artifact["sha256"])
    assert response.content == (case.root / "candidate/events/0.json").read_bytes()
    before = case.calls.count("inputs")
    response = client.get(base + "/arms/candidate/bundle")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    records = [parse_json(line) for line in response.content.splitlines()]
    assert records[0]["arm"] == "candidate"
    assert records[0]["pair_id"] == identifier
    assert len(records) == 5
    assert {r["path"] for r in records[1:]} == {
        "manifest.json",
        "catalog.json",
        "events/0.json",
        "snapshots/7.json",
    }
    for row in records[1:]:
        assert (
            base64.b64decode(row["body_base64"])
            == (case.root / "candidate" / row["path"]).read_bytes()
        )
    assert case.calls.count("inputs") == before + 1
    assert all(job.kind == "relocation-pair-read-v3" for job in processor.calls)


def test_unknowns_skip_worker_and_foreign_arm(api_case: Any) -> None:
    client, identifier, processor, _ = api_case
    base = f"/api/v3/relocation-pairs/{identifier}"
    left = client.get(base + "/arms/baseline/manifest").json()
    artifact = next(r for r in left["files"] if r["path"] == "events/0.json")
    count = len(processor.calls)
    for suffix in ("/arms/other/manifest", "/arms/candidate/files/" + artifact["sha256"]):
        assert client.get(base + suffix).status_code == 404
    assert client.get("/api/v3/relocation-pairs/" + "f" * 64 + "/result").status_code == 404
    assert len(processor.calls) == count


@pytest.mark.parametrize("tick", ["-1", "01", "1.0", "true", "8"])
def test_replay_tick_rejected(api_case: Any, tick: str) -> None:
    client, identifier, _, _ = api_case
    response = client.get(f"/api/v3/relocation-pairs/{identifier}/arms/baseline/replay?tick={tick}")
    assert response.status_code == 422


def test_fresh_reads_reject_after_warm_success(api_case: Any) -> None:
    client, identifier, _, case = api_case
    base = f"/api/v3/relocation-pairs/{identifier}"
    assert client.get(base + "/arms/candidate/replay?tick=3").status_code == 200
    from app.storage.artifacts import ArtifactStore

    store = ArtifactStore(case.store_root)
    index = store.read_reference("runs", identifier)
    row = next(r for r in index["files"] if r["path"] == "baseline/events/0.json")
    store.path("run_files", row["sha256"]).write_bytes(b"[]")
    assert client.get(base + "/result").status_code == 500
    assert client.get(base + "/arms/candidate/bundle").status_code == 500
    assert not (case.store_root / "requests").exists()


def test_file_response_identity_headers(api_case: Any) -> None:
    client, identifier, _, _ = api_case
    base = f"/api/v3/relocation-pairs/{identifier}/arms/candidate"
    manifest = client.get(base + "/manifest").json()
    row = next(r for r in manifest["files"] if r["path"] == "catalog.json")
    response = client.get(base + "/files/" + row["sha256"])
    for key in (
        "pair_id",
        "arm",
        "native_run_id",
        "input_hash",
        "pair_input_hash",
        "common_input_hash",
        "registry_common_hash",
    ):
        assert response.headers["X-Qoima-" + key.replace("_", "-")] == manifest[key]


def test_stream_keeps_captured_bytes_after_store_change(api_case: Any) -> None:
    from app.storage.artifacts import ArtifactStore
    from app.storage.canonical_json import canonical_bytes
    from app.v3.api_relocation_pair import _records

    client, identifier, processor, case = api_case
    assert (
        client.get(f"/api/v3/relocation-pairs/{identifier}/arms/baseline/bundle").status_code == 200
    )
    job = processor.calls[-1]
    value = worker.pair_read_job(job)
    store = ArtifactStore(case.store_root)
    row = value["header"]["stream_descriptors"][0]
    store.path("run_files", row["sha256"]).write_bytes(b"changed after validation")
    records = list(_records(value))
    assert records[0] == canonical_bytes(value["header"]) + b"\n"
    for line in records[1:]:
        record = parse_json(line)
        original = (case.root / "baseline" / record["path"]).read_bytes()
        assert base64.b64decode(record["body_base64"]) == original


def test_shared_slot_returns_409(api_case: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    client, identifier, processor, _ = api_case
    started, release = Event(), Event()
    actual = processor.execute

    async def gated(job: Job) -> dict[str, Any]:
        started.set()
        await asyncio.to_thread(release.wait)
        result: dict[str, Any] = await actual(job)
        return result

    monkeypatch.setattr(processor, "execute", gated)
    path = f"/api/v3/relocation-pairs/{identifier}/result"
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(client.get, path)
        try:
            assert started.wait(5)
            assert client.get(path).status_code == 409
            assert client.get("/api/v3/relocation-pairs/" + "f" * 64 + "/result").status_code == 404
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 200


def test_cancelled_read_retains_slot_and_shutdown_drains() -> None:
    from types import SimpleNamespace

    from app.api.service import BusyError, JobService

    async def scenario() -> None:
        started, release = asyncio.Event(), asyncio.Event()

        async def execute(job: Job) -> dict[str, Any]:
            started.set()
            await release.wait()
            return {"observed": True}

        service = JobService(cast(ApiContext, SimpleNamespace()), SimpleNamespace(execute=execute))
        job = Job("relocation-pair-read-v3", {}, "", "", "", "")
        caller = asyncio.create_task(service.read_job(job))
        await started.wait()
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        with pytest.raises(BusyError):
            await service.read_job(job)
        draining = asyncio.create_task(service.finish())
        await asyncio.sleep(0)
        assert not draining.done()
        release.set()
        await draining
        assert service.active is not None and service.active.result() == {"observed": True}

    asyncio.run(scenario())


def test_foreign_domain_is_404_before_worker(api_case: Any) -> None:
    from app.storage.artifacts import ArtifactStore

    client, _, processor, case = api_case
    store = ArtifactStore(case.store_root)
    identifier = "e" * 64
    store.publish_reference("runs", identifier, {"domain": "foreign"})
    before = len(processor.calls)
    assert client.get(f"/api/v3/relocation-pairs/{identifier}/result").status_code == 404
    assert len(processor.calls) == before
