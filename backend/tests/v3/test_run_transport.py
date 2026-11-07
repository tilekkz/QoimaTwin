"""Manual run transport bounds raw chunks and seeks from full settled checkpoints."""

import hashlib
import json
from pathlib import Path

import pytest

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run
from app.v3.run_replay import replay_manual
from app.v3.run_transport import read_manual_run, seek_manual_run, write_manual_run
from tests.v3.test_run_fixtures import manual_profile


def test_transport_chunks_have_raw_hashes_limits_and_lossless_full_read(tmp_path: Path) -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile,
        graph,
        outcome,
        graph_document=document,
        end_tick_limit=40_000_000,
        snapshot_interval_ticks=10_000_000,
    )
    manifest = write_manual_run(run, tmp_path / "run", max_chunk_bytes=5000)
    assert not (tmp_path / "run/run.json").exists()
    assert len(manifest["event_chunks"]) > 1
    for key in ("event_chunks", "snapshot_chunks"):
        for descriptor in manifest[key]:
            raw = (tmp_path / "run" / descriptor["path"]).read_bytes()
            assert len(raw) == descriptor["bytes"] <= 5000
            assert hashlib.sha256(raw).hexdigest() == descriptor["sha256"]
            rows = json.loads(raw)["items"]
            assert all(
                descriptor["start_tick"] <= row["tick"] < descriptor["end_tick"] for row in rows
            )
    assert read_manual_run(tmp_path / "run") == run
    assert seek_manual_run(tmp_path / "run", 18_000_000) == replay_manual(run, 18_000_000)


def test_exact_chunk_boundary_and_snapshot_event_order(tmp_path: Path) -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(31_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    manifest = write_manual_run(run, tmp_path / "run", chunk_ticks=31_000_000)
    chunks = manifest["event_chunks"]
    first = json.loads((tmp_path / "run" / chunks[0]["path"]).read_bytes())["items"]
    later = [
        row
        for d in chunks[1:]
        for row in json.loads((tmp_path / "run" / d["path"]).read_bytes())["items"]
    ]
    assert all(row["tick"] < 31_000_000 for row in first)
    assert any(row["tick"] == 31_000_000 and row["kind"] == "hu_shipped" for row in later)
    assert seek_manual_run(tmp_path / "run", 31_000_000)["shipped_units"] == [["SKU1", 24]]


@pytest.mark.parametrize("damage", ["clock", "raw_limit", "range", "foreign_field"])
def test_transport_rejects_corrupt_manifest_before_reading_timeline(
    tmp_path: Path, damage: str
) -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    manifest = write_manual_run(run, tmp_path / "run")
    if damage == "clock":
        manifest["clock"]["ticks_per_second"] = 1
    elif damage == "raw_limit":
        manifest["max_chunk_bytes"] = 1024 * 1024 * 1024
    elif damage == "range":
        manifest["event_chunks"][0]["first_tick"] = -1
    else:
        manifest["unvalidated_future_field"] = True
    (tmp_path / "run/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        seek_manual_run(tmp_path / "run", 18_000_000)


def test_seek_reads_one_checkpoint_and_only_intersecting_event_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile,
        graph,
        outcome,
        graph_document=document,
        end_tick_limit=40_000_000,
        snapshot_interval_ticks=10_000_000,
    )
    manifest = write_manual_run(run, tmp_path / "run", max_chunk_bytes=5000)
    read = Path.read_bytes
    paths: list[Path] = []

    def observed_read(path: Path) -> bytes:
        paths.append(path)
        return read(path)

    monkeypatch.setattr(Path, "read_bytes", observed_read)
    assert seek_manual_run(tmp_path / "run", 18_000_000) == replay_manual(run, 18_000_000)
    assert sum(path.parent.name == "snapshots" for path in paths) == 1
    assert sum(path.parent.name == "events" for path in paths) < len(manifest["event_chunks"])
    assert not any(path.name == "graph.json" for path in paths)


def test_changed_chunk_bytes_and_directory_escape_are_rejected(tmp_path: Path) -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    manifest = write_manual_run(run, tmp_path / "run")
    chunk = tmp_path / "run" / manifest["event_chunks"][0]["path"]
    raw = chunk.read_bytes()
    chunk.write_bytes(raw.replace(b"job_arrived", b"job_arriveX"))
    with pytest.raises(ValueError, match="hash"):
        read_manual_run(tmp_path / "run")
    manifest["metadata"]["path"] = "../outside.json"
    (tmp_path / "run/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        read_manual_run(tmp_path / "run")
