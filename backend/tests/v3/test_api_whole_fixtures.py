"""Injected hand registration tests HTTP/storage; it is never source approval evidence."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3 import api_whole_readers, api_whole_registry, api_whole_worker
from app.v3.api_whole_inputs import PROFILE, FrozenWholeProfile
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json
from app.v3.whole_run import build_whole_run
from app.v3.whole_transport import write_whole_run
from tests.v3.test_receipt_flow_fixtures import SECOND
from tests.v3.test_whole_run_fixtures import sample


def hand_artifact(root: Path) -> Json:
    inputs, outcome = sample(horizon=46 * SECOND, end=47 * SECOND)
    run = build_whole_run(inputs, outcome)
    manifest = write_whole_run(run, root / "run", inputs=inputs.frozen_bytes)
    profile = canonical_bytes({"test_policy": "explicit hand; no source approval"})
    request = canonical_bytes({k: run[k] for k in ("input_hash", "physical_input_hash")})
    snapshot = {
        "input_hash": run["input_hash"],
        "physical_input_hash": run["physical_input_hash"],
        "profile_sha256": sha256(profile).hexdigest(),
        "request_sha256": sha256(request).hexdigest(),
        "frozen_inputs": inputs.input_hash,
    }
    (root / "profile.json").write_bytes(profile)
    (root / "request.json").write_bytes(request)
    result = {
        **{
            k: run[k]
            for k in (
                "status",
                "run_id",
                "input_hash",
                "physical_input_hash",
                "metrics",
                "capabilities",
            )
        },
        "request_sha256": snapshot["request_sha256"],
        "manifest_sha256": sha256((root / "run/manifest.json").read_bytes()).hexdigest(),
        "event_chunks": len(manifest["event_chunks"]),
        "checkpoint_chunks": len(manifest["checkpoint_chunks"]),
        "layout_version": LAYOUT_VERSION,
        "operational_admission": False,
        "request": str(root / "request.json"),
        "manifest": str(root / "run/manifest.json"),
    }
    (root / "result.json").write_bytes(canonical_bytes(result))
    return snapshot


class ExistingWholeProcessor:
    def __init__(self, artifact: Path, frozen: FrozenWholeProfile) -> None:
        self.artifact, self.frozen = artifact, frozen
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> Json:
        self.calls.append(job)
        assert job.kind == "whole-v3"
        return await asyncio.to_thread(
            api_whole_worker.publish_output,
            ArtifactStore(Path(job.store_root)),
            self.frozen,
            self.artifact,
        )


@dataclass
class WholeApi:
    client: TestClient
    store: ArtifactStore
    processor: ExistingWholeProcessor
    frozen: FrozenWholeProfile
    body: Json
    response: Json

    @property
    def base(self) -> str:
        return "/api/v3/whole-runs/" + str(self.response["run_id"])


@pytest.fixture(scope="module", name="whole_api")
def registered_hand_whole_api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[WholeApi]:
    root = tmp_path_factory.mktemp("whole-api-hand")
    artifact = root / "artifact"
    snapshot = hand_artifact(artifact)
    metadata = {
        **snapshot,
        "profile": PROFILE,
        "layout_version": LAYOUT_VERSION,
        "source_revision": "explicit-test-hand-policy",
    }
    frozen = FrozenWholeProfile("b" * 64, metadata)
    processor = ExistingWholeProcessor(artifact, frozen)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(api_whole_registry, "freeze_profile", lambda *args: frozen)
        patch.setattr(api_whole_worker, "verified_registration", lambda *args: snapshot)
        patch.setattr(api_whole_readers, "verified_registration", lambda *args: snapshot)
        with TestClient(
            create_app(root / "store", processor=processor), raise_server_exceptions=False
        ) as client:
            response = client.get("/api/v3/whole-profiles")
            assert response.status_code == 200, response.text
            body = {key: metadata[key] for key in ("profile", "layout_version", "source_revision")}
            first = client.post("/api/v3/whole-runs", json=body)
            assert first.status_code == 200, first.text
            yield WholeApi(
                client, ArtifactStore(root / "store"), processor, frozen, body, first.json()
            )
