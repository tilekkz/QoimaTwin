"""Internal hand storage/HTTP fixture; patched registration is never source approval."""

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
from app.v3 import api_coordinator_readers, api_coordinator_registry, api_coordinator_worker
from app.v3.api_coordinator_inputs import PROFILE, FrozenCoordinatorProfile
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.coordinator_transport import write_coordinator_run
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def hand_artifact(root: Path) -> Json:
    profile, conveyor = multi_profile(candidate=True), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 158 * SECOND, 158 * SECOND)
    outcome = CoordinatorEngine(profile, conveyor).run(158 * SECOND, 158 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    write_coordinator_run(run, root / "run", inputs=inputs.frozen_bytes)
    choices = canonical_bytes({"test_policy": "internal hand; no source approval"})
    request = canonical_bytes({k: run[k] for k in ("input_hash", "registry_common_hash")})
    snapshot = {
        "input_hash": run["input_hash"],
        "registry_common_hash": run["registry_common_hash"],
        "profile_sha256": sha256(choices).hexdigest(),
        "request_sha256": sha256(request).hexdigest(),
        "frozen_inputs": inputs.input_hash,
    }
    (root / "profile.json").write_bytes(choices)
    (root / "request.json").write_bytes(request)
    _result(root, run, snapshot)
    return snapshot


def _result(root: Path, run: Json, snapshot: Json) -> None:
    value = {
        k: run[k]
        for k in (
            "status",
            "run_id",
            "input_hash",
            "registry_common_hash",
            "observed_until_tick",
            "metrics",
        )
    }
    value.update(
        request_sha256=snapshot["request_sha256"],
        manifest_sha256=sha256((root / "run/manifest.json").read_bytes()).hexdigest(),
        request=str(root / "request.json"),
        manifest=str(root / "run/manifest.json"),
        layout_version=LAYOUT_VERSION,
        operational_admission=False,
    )
    (root / "result.json").write_bytes(canonical_bytes(value))


class ExistingCoordinatorProcessor:
    def __init__(self, artifact: Path, frozen: FrozenCoordinatorProfile) -> None:
        self.artifact, self.frozen = artifact, frozen
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> Json:
        self.calls.append(job)
        assert job.kind == "coordinator-v3"
        return await asyncio.to_thread(
            api_coordinator_worker.publish_output,
            ArtifactStore(Path(job.store_root)),
            self.frozen,
            self.artifact,
        )


@dataclass
class CoordinatorApi:
    client: TestClient
    store: ArtifactStore
    processor: ExistingCoordinatorProcessor
    frozen: FrozenCoordinatorProfile
    body: Json
    response: Json

    @property
    def base(self) -> str:
        return "/api/v3/coordinator-runs/" + str(self.response["run_id"])


@pytest.fixture(scope="module", name="coordinator_api")
def registered_hand_api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[CoordinatorApi]:
    root = tmp_path_factory.mktemp("coordinator-api-hand")
    artifact = root / "artifact"
    snapshot = hand_artifact(artifact)
    metadata = {
        **snapshot,
        "profile": PROFILE,
        "layout_version": LAYOUT_VERSION,
        "source_revision": "internal-hand-http-fixture",
    }
    frozen = FrozenCoordinatorProfile("b" * 64, metadata)
    processor = ExistingCoordinatorProcessor(artifact, frozen)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(api_coordinator_registry, "freeze_profile", lambda *args: frozen)
        patch.setattr(api_coordinator_worker, "verified_registration", lambda *args: snapshot)
        patch.setattr(api_coordinator_readers, "verified_registration", lambda *args: snapshot)
        with TestClient(
            create_app(root / "store", processor=processor), raise_server_exceptions=False
        ) as client:
            body = {k: metadata[k] for k in ("profile", "layout_version", "source_revision")}
            first = client.post("/api/v3/coordinator-runs", json=body)
            assert first.status_code == 200, first.text
            yield CoordinatorApi(
                client,
                ArtifactStore(root / "store"),
                processor,
                frozen,
                body,
                first.json(),
            )
