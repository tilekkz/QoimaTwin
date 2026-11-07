"""Persistent history proof uses tiny bytes and only temporary trusted directories."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.data import history
from app.data.history_store import HistoryCacheError, load_or_generate

KEY = "a" * 64
PAYLOAD = b"date,sku_id,visits,units,split\n2026-11-08,DEMO_001,1,2,train\n"


def forbidden() -> bytes:
    pytest.fail("warm cache called generator")


def test_cold_warm_exact_bytes(tmp_path: Path) -> None:
    assert load_or_generate(tmp_path, KEY, lambda: PAYLOAD) == PAYLOAD
    assert load_or_generate(tmp_path, KEY, forbidden) == PAYLOAD
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    assert (tmp_path / f"{digest}.csv").read_bytes() == PAYLOAD


@pytest.mark.parametrize("damage", ["bytes", "duplicate", "malformed", "missing", "traversal"])
def test_corruption_fails_closed(tmp_path: Path, damage: str) -> None:
    load_or_generate(tmp_path, KEY, lambda: PAYLOAD)
    reference = tmp_path / f"{KEY}.json"
    content = tmp_path / f"{hashlib.sha256(PAYLOAD).hexdigest()}.csv"
    if damage == "bytes":
        content.write_bytes(b"PRIVATE CORRUPTION")
    elif damage == "missing":
        content.unlink()
    elif damage == "duplicate":
        reference.write_text('{"sha256":"PRIVATE","sha256":"OTHER"}')
    elif damage == "traversal":
        reference.write_text(json.dumps({"version": 1, "input": KEY, "sha256": "../PRIVATE"}))
    else:
        reference.write_bytes(b"PRIVATE malformed")
    with pytest.raises(HistoryCacheError, match="invalid history cache") as caught:
        load_or_generate(tmp_path, KEY, forbidden)
    assert "PRIVATE" not in str(caught.value)


def test_existing_content_is_never_overwritten(tmp_path: Path) -> None:
    content = tmp_path / f"{hashlib.sha256(PAYLOAD).hexdigest()}.csv"
    content.write_bytes(b"keep")
    with pytest.raises(HistoryCacheError):
        load_or_generate(tmp_path, KEY, lambda: PAYLOAD)
    assert content.read_bytes() == b"keep"
    assert not (tmp_path / f"{KEY}.json").exists()


def test_independent_processes(tmp_path: Path) -> None:
    script = """
import sys
from pathlib import Path
from app.data.history_store import load_or_generate
def generate():
    assert sys.argv[2] == 'cold', 'generator called in warm process'
    return b'visits\\n1\\n'
assert load_or_generate(Path(sys.argv[1]), 'a' * 64, generate) == b'visits\\n1\\n'
"""
    for mode in ("cold", "warm"):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), mode],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
        assert result.returncode == 0, result.stderr


def test_input_changes_invalidate_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    original = history.history_input_fingerprint()
    monkeypatch.setattr(history, "HISTORY_DAYS", 55)
    assert history.history_input_fingerprint() != original


def test_source_changes_invalidate_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    original = history.history_input_fingerprint()
    read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda path: read_bytes(path) + b"\n# changed")
    assert history.history_input_fingerprint() != original


def test_concurrent_publishers_and_orphan_content(tmp_path: Path) -> None:
    content = tmp_path / f"{hashlib.sha256(PAYLOAD).hexdigest()}.csv"
    content.write_bytes(PAYLOAD)  # interrupted publication before the manifest
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: load_or_generate(tmp_path, KEY, lambda: PAYLOAD), range(8))
        )
    assert results == [PAYLOAD] * 8
    assert not list(tmp_path.glob(".history-*"))


@pytest.mark.parametrize("key", ["../escape", "A" * 64, "f" * 63, ""])
def test_malformed_input_key(tmp_path: Path, key: str) -> None:
    with pytest.raises(HistoryCacheError):
        load_or_generate(tmp_path, key, forbidden)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["directory", "oversized", "wrong_input", "extra", "boolean"])
def test_invalid_manifest(tmp_path: Path, kind: str) -> None:
    reference = tmp_path / f"{KEY}.json"
    if kind == "directory":
        reference.mkdir()
    elif kind == "oversized":
        reference.write_bytes(b" " * 4097)
    else:
        manifest: dict[str, object] = {"version": 1, "input": KEY, "sha256": "b" * 64}
        if kind == "wrong_input":
            manifest["input"] = "b" * 64
        elif kind == "extra":
            manifest["extra"] = 1
        else:
            manifest["version"] = True
        reference.write_text(json.dumps(manifest))
    with pytest.raises(HistoryCacheError):
        load_or_generate(tmp_path, KEY, forbidden)


def test_default_wrapper_reuses_bytes_in_new_cli_process(tmp_path: Path) -> None:
    script = """
import sys
import pandas as pd
from app.data import history
from app.cli import main
def generate():
    assert sys.argv[1] == 'cold', 'warm process regenerated history'
    return pd.DataFrame({'visits': [1]})
history.generate_history = generate
raise SystemExit(main(['materialize', '--profile', 'large-normal', '--horizon-s', '3600',
                      '--out', sys.argv[2]]))
"""
    env = os.environ | {"QOIMA_HISTORY_CACHE_DIR": str(tmp_path / "cache")}
    for mode in ("cold", "warm"):
        output = tmp_path / mode
        result = subprocess.run(
            [sys.executable, "-c", script, mode, str(output)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (output / "history_daily.csv").read_bytes() == b"visits\n1\n"


def test_directory_configuration_rejects_relative_and_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for path in ("relative", str(Path.cwd())):
        monkeypatch.setenv("QOIMA_HISTORY_CACHE_DIR", path)
        with pytest.raises(HistoryCacheError):
            history.history_cache_dir()


def test_fingerprint_independent_of_checkout_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = history.history_input_fingerprint()
    app = Path(history.__file__).resolve().parents[1]
    for folder in ("data", "contracts"):
        (tmp_path / "app" / folder).mkdir(parents=True)
        for source in (app / folder).glob("*.py"):
            shutil.copyfile(source, tmp_path / "app" / folder / source.name)
    monkeypatch.setattr(history, "__file__", str(tmp_path / "app/data/history.py"))
    assert history.history_input_fingerprint() == original


def test_new_input_key_generates_new_content(tmp_path: Path) -> None:
    load_or_generate(tmp_path, KEY, lambda: PAYLOAD)
    other = b"visits\n2\n"
    assert load_or_generate(tmp_path, "b" * 64, lambda: other) == other
    assert load_or_generate(tmp_path, KEY, forbidden) == PAYLOAD


def test_persistence_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.data.history_store.MAX_CONTENT_BYTES", 2)
    with pytest.raises(HistoryCacheError):
        load_or_generate(tmp_path, KEY, lambda: PAYLOAD)
    assert not list(tmp_path.iterdir())
