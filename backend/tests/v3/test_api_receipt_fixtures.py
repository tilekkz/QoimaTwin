"""One actual source receipt artifact drives immutable HTTP boundary checks."""

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
from app.v3.api_receipt_worker import publish_output
from app.v3.cli_receipt import simulate_receipt_file


class ExistingReceiptProcessor:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> Json:
        self.calls.append(job)
        assert job.kind == "receipt-v3"
        store = ArtifactStore(Path(job.store_root))
        bundle = job.payload["receipt_bundle_id"]
        snapshot = store.read_json("bundles", bundle)
        return await asyncio.to_thread(publish_output, store, bundle, self.artifact, snapshot)


@dataclass
class ReceiptApi:
    client: TestClient
    store: ArtifactStore
    processor: ExistingReceiptProcessor
    body: Json
    response: Json

    @property
    def base(self) -> str:
        return "/api/v3/receipt-runs/" + str(self.response["run_id"])


@pytest.fixture(scope="module", name="receipt_api")
def registered_receipt_api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ReceiptApi]:
    root = tmp_path_factory.mktemp("receipt-api")
    supplied = os.environ.get("QOIMA_TEST_RECEIPT_ARTIFACT")
    artifact = Path(supplied) if supplied else root / "source-artifact"
    if supplied is None:
        simulate_receipt_file(
            Path("data/v3-proposal"),
            Path("docs/proposals/adaptive-v3/receipt-flow-profile.example.json"),
            artifact,
        )
    processor = ExistingReceiptProcessor(artifact)
    with TestClient(
        create_app(root / "store", processor=processor), raise_server_exceptions=False
    ) as client:
        result = client.get("/api/v3/receipt-profiles")
        assert result.status_code == 200, result.text
        metadata = result.json()["profiles"][0]
        body = {key: metadata[key] for key in ("profile", "layout_version", "source_revision")}
        first = client.post("/api/v3/receipt-runs", json=body)
        assert first.status_code == 200, first.text
        yield ReceiptApi(client, ArtifactStore(root / "store"), processor, body, first.json())
