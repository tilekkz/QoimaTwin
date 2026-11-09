"""Reuse one real source artifact; HTTP boundary injection never stubs production execution."""

import asyncio
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job, Json
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json
from app.v3.api_light_identity import public_run_id, verified_response
from app.v3.api_light_inputs import DOMAIN
from app.v3.cli_lightflow import simulate_light_file
from tests.v3.test_flow_profile_compiler import EXAMPLE


class ExistingArtifactProcessor:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> Json:
        self.calls.append(job)
        assert job.kind == "light-v3"
        return await asyncio.to_thread(self.publish, job)

    def publish(self, job: Job) -> Json:
        store = ArtifactStore(Path(job.store_root))
        snapshot = store.read_json("bundles", job.payload["light_bundle_id"])
        metadata = parse_json((self.artifact / "metadata.json").read_bytes())
        assert metadata["input_hash"] == snapshot["input_hash"]
        files = [
            {
                "path": p.relative_to(self.artifact).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": store.put_bytes("run_files", p.read_bytes()),
            }
            for p in sorted(self.artifact.rglob("*.json"))
        ]
        identity = public_run_id(metadata["run_id"], job.payload["light_bundle_id"])
        index = {
            "domain": DOMAIN,
            "run_id": identity,
            "native_run_id": metadata["run_id"],
            "input_bundle_id": job.payload["light_bundle_id"],
            "input_hash": metadata["input_hash"],
            "files": files,
        }
        store.publish_reference("runs", identity, index)
        return verified_response(metadata, index)


@dataclass
class LightApi:
    client: TestClient
    store: ArtifactStore
    processor: ExistingArtifactProcessor
    body: Json
    response: Json

    @property
    def base(self) -> str:
        return "/api/v3/light-runs/" + str(self.response["run_id"])


@pytest.fixture(scope="module", name="light_api")
def registered_light_api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LightApi]:
    root = tmp_path_factory.mktemp("light-api")
    supplied = os.environ.get("QOIMA_TEST_LIGHT_ARTIFACT")
    artifact = Path(supplied) if supplied else root / "source-artifact"
    if supplied is None:
        simulate_light_file(Path("data/v3-proposal"), EXAMPLE, artifact)
    processor = ExistingArtifactProcessor(artifact)
    with TestClient(
        create_app(root / "store", processor=processor), raise_server_exceptions=False
    ) as client:
        result = client.get("/api/v3/light-profiles")
        assert result.status_code == 200, result.text
        metadata = result.json()["profiles"][0]
        body = {k: metadata[k] for k in ("profile", "layout_version", "source_revision")}
        first = client.post("/api/v3/light-runs", json=body)
        assert first.status_code == 200, first.text
        yield LightApi(client, ArtifactStore(root / "store"), processor, body, first.json())
