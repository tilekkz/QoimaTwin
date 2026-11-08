"""Registration stays lazy and concurrent callers share one frozen source compilation."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.storage.artifacts import ArtifactStore
from app.v3 import api_whole_registry
from app.v3.api_whole_inputs import FrozenWholeProfile
from tests.v3.test_api_manual import HoldingProcessor


def test_unrelated_routes_never_compile_whole_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object) -> object:
        pytest.fail("unrelated route compiled whole source")

    monkeypatch.setattr(api_whole_registry, "freeze_profile", forbidden)
    with TestClient(create_app(tmp_path, processor=HoldingProcessor())) as client:
        assert client.get("/openapi.json").status_code == 200


def test_concurrent_registration_gets_compile_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []
    frozen = FrozenWholeProfile("a" * 64, {})

    def compile_once(store: ArtifactStore, source: Path) -> FrozenWholeProfile:
        calls.append(source)
        return frozen

    monkeypatch.setattr(api_whole_registry, "freeze_profile", compile_once)
    registry = api_whole_registry.WholeRegistry(ArtifactStore(tmp_path), tmp_path)

    async def exercise() -> None:
        results = await asyncio.gather(*(registry.get() for _ in range(3)))
        assert all(value is frozen for value in results)
        assert calls == [tmp_path]

    asyncio.run(exercise())
