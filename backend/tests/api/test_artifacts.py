"""PDF API: immutable content addressing and no caller-controlled filesystem paths."""

from pathlib import Path

import pytest

from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactStore


def test_same_content_is_reused_without_rewriting(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    identifier = store.put_json("scenarios", {"orders": [], "horizon_s": 60})
    path = store.path("scenarios", identifier)
    before = path.stat().st_mtime_ns
    assert store.put_json("scenarios", {"horizon_s": 60, "orders": []}) == identifier
    assert path.stat().st_mtime_ns == before
    assert store.read_json("scenarios", identifier) == {"horizon_s": 60, "orders": []}


@pytest.mark.parametrize("identifier", ["../outside", "A" * 64, "a" * 63, "a/" * 32])
def test_identifiers_cannot_escape_artifact_namespace(tmp_path: Path, identifier: str) -> None:
    with pytest.raises(InvalidInputError):
        ArtifactStore(tmp_path).read_bytes("scenarios", identifier)


def test_corrupt_content_is_detected_before_use(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    identifier = store.put_json("scenarios", {"orders": []})
    store.path("scenarios", identifier).write_bytes(b"{}")
    with pytest.raises(AppError, match="hash"):
        store.read_json("scenarios", identifier)


def test_reference_publication_never_overwrites_different_content(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    key = "a" * 64
    store.publish_reference("requests", key, {"result": 1})
    store.publish_reference("requests", key, {"result": 1})
    with pytest.raises(AppError, match="immutable"):
        store.publish_reference("requests", key, {"result": 2})
    assert store.read_reference("requests", key) == {"result": 1}


def test_failed_atomic_publication_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_link(source: Path, target: Path) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr("app.storage.artifacts.os.link", fail_link)
    with pytest.raises(OSError, match="injected"):
        ArtifactStore(tmp_path).put_bytes("histories", b"history")
    assert list((tmp_path / "histories").iterdir()) == []
