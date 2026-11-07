"""Reproduced review findings: Windows publication races and public diagnostic leakage."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import Job
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore, _confinement_path
from tests.api.test_routes import BASE, FakeProcessor


def test_catalog_does_not_expose_server_contract_path(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, processor=FakeProcessor())) as client:
        payload = client.get("/api/catalog").json()
        assert "contracts_dir" not in payload
        assert payload["bundle_id"]


def test_unexpected_error_hides_internal_exception_contents(tmp_path: Path) -> None:
    class FailingProcessor:
        async def execute(self, job: Job) -> dict[str, Any]:
            raise OSError("fabricated private detail C:/fabricated-private-dir/artifact.data")

    with TestClient(
        create_app(tmp_path, processor=FailingProcessor()), raise_server_exceptions=False
    ) as client:
        response = client.post(
            "/api/scenarios/materialize",
            json={
                **BASE,
                "profile": "large-normal",
                "horizon_s": 1,
            },
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "execution_error"
        assert "fabricated" not in response.text and "private" not in response.text


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length resolve representation")
def test_extended_resolved_path_stays_confined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    target = tmp_path / "histories" / f"{'a' * 64}.data"
    monkeypatch.setattr(Path, "resolve", lambda self: Path("\\\\?\\" + str(target)))
    assert store.path("histories", "a" * 64) == Path("\\\\?\\" + str(target))


def test_resolved_escape_is_still_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ArtifactStore(tmp_path / "store")
    monkeypatch.setattr(Path, "resolve", lambda self: tmp_path / "outside" / "evil.data")
    with pytest.raises(InvalidInputError, match="escapes"):
        store.path("histories", "a" * 64)


@pytest.mark.parametrize(
    ("root", "candidate", "inside"),
    [
        (r"D:\store", r"\\?\D:\store\histories\item", True),
        (r"\\?\D:\store", r"D:\store\histories\item", True),
        (r"\\server\share\store", r"\\?\UNC\server\share\store\item", True),
        (r"\\?\UNC\server\share\store", r"\\server\share\store\item", True),
        (r"D:\store", r"\\?\E:\store\histories\item", False),
        (r"D:\store", r"\\?\D:\store-other\item", False),
        (r"\\server\share\store", r"\\?\UNC\other\share\store\item", False),
    ],
)
def test_windows_normalization_preserves_drive_and_unc_confinement(
    root: str,
    candidate: str,
    inside: bool,
) -> None:
    normalized = _confinement_path(PureWindowsPath(candidate))
    assert normalized.is_relative_to(_confinement_path(PureWindowsPath(root))) is inside


@pytest.mark.parametrize("round_number", range(3))
def test_concurrent_first_publication_reuses_identical_content(
    tmp_path: Path,
    round_number: int,
) -> None:
    store = ArtifactStore(tmp_path / f"round-{round_number}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        identifiers = list(
            pool.map(lambda _: store.put_bytes("histories", b"review-race"), range(16))
        )
    assert len(set(identifiers)) == 1
    assert store.read_bytes("histories", identifiers[0]) == b"review-race"
