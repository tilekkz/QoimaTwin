"""The API uses the runtime's backend JSON Schemas and reference checks, not coercion."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job, Json
from app.api.worker import execute_job
from app.contracts.loader import ContractBundle
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from tests.api.test_routes import BASE


def test_invalid_configuration_schema_fails_before_app_start(
    tmp_path: Path, bundle: ContractBundle
) -> None:
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    data = bundle.config.model_dump(mode="json", by_alias=True)
    data["totes_total"] = 0
    (contracts / "simulation_defaults.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(InvalidInputError, match="configuration schema"):
        create_app(tmp_path / "store", contracts_dir=contracts)


@pytest.mark.parametrize("invalid", ["quantity", "slot"])
def test_malformed_assignment_artifact_returns_422_before_materializing(
    tmp_path: Path, invalid: str
) -> None:
    class DirectValidationProcessor:
        async def execute(self, job: Job) -> Json:
            return execute_job(job).payload

    store = ArtifactStore(tmp_path)
    with TestClient(create_app(tmp_path, processor=DirectValidationProcessor())) as client:
        original = client.get("/api/catalog").json()["assignment_id"]
        assignment = store.read_json("assignments", original)
        if invalid == "quantity":
            assignment["initial_lots"][0]["quantity"] = 0
        else:
            assignment["initial_lots"][0]["slot_id"] = "UNKNOWN_SLOT"
        reference = store.put_json("assignments", assignment)
        response = client.post(
            "/api/scenarios/materialize",
            json={**BASE, "profile": "large-normal", "horizon_s": 3600, "assignment_id": reference},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_input"
    assert not (tmp_path / "scenarios").exists()
