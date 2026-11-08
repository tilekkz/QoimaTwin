"""Registered connected inputs share the existing process admission boundary."""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import ApiContext
from app.api.models import MaterializeRequest
from app.api.service import BusyError, JobService
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.api_light_inputs import freeze_profile
from app.v3.settings import default_inputs
from tests.v3.test_api_manual import HoldingProcessor
from tests.v3.test_flow_profile_compiler import document


def test_registered_inputs_import_before_api_bootstrap_in_fresh_process() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.v3.api_light_inputs import LightRequest; from app.api import create_app",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_only_registered_light_profile_is_exposed_and_request_paths_are_forbidden(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path, processor=HoldingProcessor())) as client:
        response = client.get("/api/v3/light-profiles")
        assert response.status_code == 200
        metadata = response.json()["profiles"][0]
        assert metadata["profile"] == "explicit-source-small-three-units-v1"
        assert metadata["actor_ids_preserved"] == 24 and metadata["baseline_hus"] == 530
        assert metadata["operational_admission"] is False
        body = {k: metadata[k] for k in ("profile", "layout_version", "source_revision")}
        variants: tuple[dict[str, Any], ...] = (
            {"profile": "unknown"},
            {"profile_path": "private"},
            {"horizon_tick": 1},
            {"source_revision": "wrong"},
            {"layout_version": "v2"},
        )
        for update in variants:
            result = client.post("/api/v3/light-runs", json={**body, **update})
            assert result.status_code == 422 and "private" not in result.text


def test_light_manual_and_v2_share_one_admission_slot(tmp_path: Path) -> None:
    async def exercise() -> None:
        context = ApiContext.create(ArtifactStore(tmp_path), Path("../contracts"))
        processor = HoldingProcessor()
        jobs = JobService(context, processor)
        active = asyncio.create_task(jobs.submit_job(context.job("light-v3", {}), "a" * 64))
        await processor.started.wait()
        with pytest.raises(BusyError):
            await jobs.submit_job(context.job("manual-v3", {}), "b" * 64)
        with pytest.raises(BusyError):
            await jobs.submit(
                "materialize",
                MaterializeRequest(
                    layout_version="qoima-72x48-v2", profile="large-normal", horizon_s=1
                ),
            )
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        with pytest.raises(BusyError):
            await jobs.submit_job(context.job("light-v3", {}), "c" * 64)
        processor.release.set()
        await jobs.finish()
        assert len(processor.calls) == 1

    asyncio.run(exercise())


def test_registration_does_not_normalize_invalid_boolean_rational_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = document()
    value["actors"][0]["speed_m_s"]["numerator"] = True
    original = Path.read_bytes

    def read(path: Path) -> bytes:
        if path.name == "light-flow-profile.example.json":
            return canonical_bytes(value)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ValueError):
        freeze_profile(ArtifactStore(tmp_path), default_inputs())
