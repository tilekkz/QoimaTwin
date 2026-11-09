"""Tiny saved transport doubles exercise publication without source assets or engines."""

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import relocation_pair_publication_source as source
from app.v3.relocation_models import RELOCATION_VERSION
from app.v3.relocation_pair_publication import publish_pair
from app.v3.relocation_pair_publication_storage import checked, known
from app.v3.relocation_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION


def put(root: Path, name: str, value: Any) -> dict[str, Any]:
    raw = canonical_bytes(value)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def native(root: Path, arm: str, common: str) -> dict[str, Any]:
    inputs = put(root, "inputs.json", {"arm": arm})
    run = {
        "run_id": sha256(arm.encode()).hexdigest(),
        "input_hash": inputs["sha256"],
        "common_input_hash": common,
        "registry_common_hash": "c" * 64,
        "engine_version": RELOCATION_VERSION,
        "outcome_kind": "base_noop",
        "observed_until_tick": 7,
        "outcome": {"status": "partial", "end": 7},
    }
    catalog = put(root, "catalog.json", run)
    events = put(root, "events/0.json", [{"seq": 0, "tick": 3, "arm": arm}])
    snapshot = put(root, "snapshots/7.json", {"tick": 7, "arm": arm})
    put(
        root,
        "manifest.json",
        {
            "transport_version": TRANSPORT_VERSION,
            "schema_version": PUBLICATION_VERSION,
            **{
                k: run[k]
                for k in (
                    "engine_version",
                    "run_id",
                    "input_hash",
                    "common_input_hash",
                    "registry_common_hash",
                )
            },
            "inputs": inputs,
            "catalog": catalog,
            "event_chunks": [
                {**events, "start_tick": 0, "end_tick": 60_000_000, "first_seq": 0, "last_seq": 0}
            ],
            "snapshot_chunks": [
                {**snapshot, "tick": 7, "last_seq": 0, "roles": ["at_horizon", "at_end"]}
            ],
        },
    )
    return run


@dataclass
class PairCase:
    root: Path
    store_root: Path
    calls: list[str]


def report(pair: Any, left: Any, right: Any, before: Any, after: Any) -> dict[str, Any]:
    assert before["status"] == after["status"] == "partial"
    return {
        "status": "partial",
        "no_op": True,
        "end": 7,
        "baseline": left["input_hash"],
        "candidate": right["input_hash"],
    }


def semantic_doubles(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    def load(raw: bytes) -> Any:
        calls.append("inputs")
        value = parse_json(raw)
        assert value == {"explicit_pair_double": True}
        arms = [
            SimpleNamespace(
                frozen_bytes=canonical_bytes({"arm": arm}), profile=SimpleNamespace(coordinator=arm)
            )
            for arm in ("baseline", "candidate")
        ]
        return SimpleNamespace(
            baseline=arms[0],
            candidate=arms[1],
            input_hash=sha256(raw).hexdigest(),
            common_input_hash="d" * 64,
        )

    def read(root: Path) -> dict[str, Any]:
        calls.append(root.name)
        value: dict[str, Any] = parse_json((root / "catalog.json").read_bytes())
        assert value["input_hash"] == sha256((root / "inputs.json").read_bytes()).hexdigest()
        return value

    def restore(profile: Any, outcome: Any) -> Any:
        calls.append("restore_base:" + profile)
        return outcome

    def restore_relocation(profile: Any, outcome: Any) -> Any:
        calls.append("relocation")
        return outcome

    monkeypatch.setattr(source, "load_relocation_pair_inputs", load)
    monkeypatch.setattr(source, "read_relocation_run", read)
    monkeypatch.setattr(source, "restore_base", restore)
    monkeypatch.setattr(source, "restore_outcome", restore_relocation)
    monkeypatch.setattr(source, "build_pair_report", report)


@pytest.fixture
def pair_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PairCase:
    root = tmp_path / "pair"
    root.mkdir()
    calls: list[str] = []
    semantic_doubles(monkeypatch, calls)
    put(root, "inputs.json", {"explicit_pair_double": True})
    left = native(root / "baseline", "baseline", "d" * 64)
    right = native(root / "candidate", "candidate", "d" * 64)
    put(root, "comparison.json", report(None, left, right, left["outcome"], right["outcome"]))
    return PairCase(root, tmp_path / "store", calls)


def test_publish_exact_snapshot_and_repeat(pair_case: PairCase) -> None:
    case = pair_case
    result = publish_pair(case.root, case.store_root)
    assert publish_pair(case.root, case.store_root) == result
    store = ArtifactStore(case.store_root)
    index, saved = checked(store, result["pair_id"])
    assert len(index["files"]) == 12
    assert saved.comparison["status"] == "partial"
    assert saved.comparison["end"] == 7
    assert result["origin"] == "verified_saved_native_pair"
    assert case.calls.count("baseline") == 3
    assert case.calls.count("restore_base:candidate") == 3
    assert not (case.store_root / "requests").exists()


@pytest.mark.parametrize("change", ["extra", "missing", "corrupt", "comparison", "arm"])
def test_reject_before_store_creation(pair_case: PairCase, change: str) -> None:
    root = pair_case.root
    if change == "extra":
        put(root, "extra.json", {})
    elif change == "missing":
        (root / "baseline/events/0.json").unlink()
    elif change == "corrupt":
        (root / "candidate/catalog.json").write_bytes(b"{}")
    elif change == "comparison":
        put(root, "comparison.json", {"status": "invented"})
    else:
        put(root / "candidate", "inputs.json", {"arm": "baseline"})
    with pytest.raises((ValueError, AssertionError)):
        publish_pair(root, pair_case.store_root)
    assert not pair_case.store_root.exists()


def test_source_error_and_captured_bytes(
    pair_case: PairCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = source.capture(pair_case.root)
    (pair_case.root / "comparison.json").write_bytes(b"changed later")
    assert source.validate(captured).comparison["end"] == 7
    monkeypatch.setattr(
        source,
        "load_relocation_pair_inputs",
        lambda _: (_ for _ in ()).throw(ValueError("explicit source authority error")),
    )
    with pytest.raises(ValueError, match="source authority"):
        source.validate(captured)


def test_publication_last_failure(pair_case: PairCase, monkeypatch: pytest.MonkeyPatch) -> None:
    actual = ArtifactStore.put_bytes
    calls: list[str] = []

    def fail(store: ArtifactStore, kind: str, raw: bytes) -> str:
        calls.append(kind)
        if len(calls) == 3:
            raise OSError("explicit disk failure")
        return actual(store, kind, raw)

    monkeypatch.setattr(ArtifactStore, "put_bytes", fail)
    with pytest.raises(OSError, match="disk failure"):
        publish_pair(pair_case.root, pair_case.store_root)
    assert not (pair_case.store_root / "runs").exists()


def test_hardlink_rejected(pair_case: PairCase) -> None:
    path = pair_case.root / "comparison.json"
    alias = pair_case.root.parent / "hardlink.json"
    os.link(path, alias)
    with pytest.raises(ValueError, match="alias"):
        source.capture(pair_case.root)


def test_repinned_index_cannot_keep_identity(pair_case: PairCase) -> None:
    result = publish_pair(pair_case.root, pair_case.store_root)
    store = ArtifactStore(pair_case.store_root)
    value = known(store, result["pair_id"])
    value["files"][0]["sha256"] = "e" * 64
    path = store.path("runs", result["pair_id"])
    from app.storage.canonical_json import sha256_hex

    path.write_bytes(canonical_bytes({"value": value, "content_sha256": sha256_hex(value)}))
    with pytest.raises(Exception, match="identity"):
        known(store, result["pair_id"])


def repin(root: Path, arm: str, run: dict[str, Any]) -> None:
    target = root / arm
    manifest = parse_json((target / "manifest.json").read_bytes())
    manifest["catalog"] = put(target, "catalog.json", run)
    manifest["inputs"] = source.descriptor("inputs.json", (target / "inputs.json").read_bytes())
    for key in ("run_id", "input_hash", "common_input_hash", "registry_common_hash"):
        manifest[key] = run[key]
    put(target, "manifest.json", manifest)


@pytest.mark.parametrize("change", ["arm", "common", "registry", "kind"])
def test_coherently_repinned_native_still_correlated(pair_case: PairCase, change: str) -> None:
    root = pair_case.root
    run = parse_json((root / "candidate/catalog.json").read_bytes())
    if change == "arm":
        descriptor = put(root / "candidate", "inputs.json", {"arm": "baseline"})
        run["input_hash"] = descriptor["sha256"]
    elif change in {"common", "registry"}:
        key = "common_input_hash" if change == "common" else "registry_common_hash"
        run[key] = "e" * 64
    else:
        run["outcome_kind"] = "invented"
    repin(root, "candidate", run)
    with pytest.raises(ValueError):
        publish_pair(root, pair_case.store_root)
    assert not pair_case.store_root.exists()


def test_relocation_restore_branch(pair_case: PairCase) -> None:
    root = pair_case.root
    run = parse_json((root / "candidate/catalog.json").read_bytes())
    run["outcome_kind"] = "relocation"
    repin(root, "candidate", run)
    result = publish_pair(root, pair_case.store_root)
    assert result["comparison"]["end"] == 7
    assert pair_case.calls.count("relocation") == 1
    assert "restore_base:candidate" not in pair_case.calls


@pytest.mark.parametrize("bound", ["MAX_FILE_BYTES", "MAX_PAIR_BYTES", "MAX_MEMBERS"])
def test_capture_bounds(pair_case: PairCase, monkeypatch: pytest.MonkeyPatch, bound: str) -> None:
    monkeypatch.setattr(source, bound, 2)
    with pytest.raises(ValueError):
        source.capture(pair_case.root)


def test_empty_extra_directory_rejected(pair_case: PairCase) -> None:
    (pair_case.root / "extra").mkdir()
    with pytest.raises(ValueError, match="extra directories"):
        source.capture(pair_case.root)


def test_symlink_rejected(pair_case: PairCase) -> None:
    original = pair_case.root / "comparison.json"
    moved = pair_case.root.parent / "comparison.json"
    original.rename(moved)
    try:
        original.symlink_to(moved)
    except OSError as exc:
        pytest.skip("Host cannot create test symbolic link: " + str(exc))
    with pytest.raises(ValueError, match="aliases"):
        source.capture(pair_case.root)


def test_indexlast_all_members_already_present(
    pair_case: PairCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = ArtifactStore.publish_reference
    observed: list[str] = []

    def publish(store: ArtifactStore, kind: str, identifier: str, value: Any) -> None:
        assert kind == "runs"
        for row in value["files"]:
            assert len(store.read_bytes("run_files", row["sha256"])) == row["bytes"]
        observed.append(identifier)
        actual(store, kind, identifier, value)

    monkeypatch.setattr(ArtifactStore, "publish_reference", publish)
    result = publish_pair(pair_case.root, pair_case.store_root)
    assert observed == [result["pair_id"]]


def test_ancestor_junction_policy(pair_case: PairCase, monkeypatch: pytest.MonkeyPatch) -> None:
    actual = Path.is_junction
    ancestor = pair_case.root.parent
    monkeypatch.setattr(Path, "is_junction", lambda path: path == ancestor or actual(path))
    with pytest.raises(ValueError, match="links or junctions"):
        source.capture(pair_case.root)


def test_cli_entry_point(pair_case: PairCase, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    from app.v3.relocation_pair_publication import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "publication",
            "publish",
            "--pair",
            str(pair_case.root),
            "--store-root",
            str(pair_case.store_root),
        ],
    )
    main()
    response = parse_json(capsys.readouterr().out.encode())
    assert response["origin"] == "verified_saved_native_pair"
    assert known(ArtifactStore(pair_case.store_root), response["pair_id"])["domain"]


def test_fully_repinned_comparison_rejected_at_new_identity(pair_case: PairCase) -> None:
    from app.storage.artifacts import ArtifactCorruption
    from app.v3.relocation_pair_publication_storage import public_id

    result = publish_pair(pair_case.root, pair_case.store_root)
    store = ArtifactStore(pair_case.store_root)
    index = known(store, result["pair_id"])
    raw = canonical_bytes({"invented": "comparison"})
    digest = store.put_bytes("run_files", raw)
    index["files"] = [
        source.descriptor(row["path"], raw) if row["path"] == "comparison.json" else row
        for row in index["files"]
    ]
    index["comparison_sha256"] = digest
    index["pair_id"] = public_id(index)
    store.publish_reference("runs", index["pair_id"], index)
    with pytest.raises(ArtifactCorruption, match="strict native"):
        checked(store, index["pair_id"])


@pytest.mark.parametrize("change", ["version", "extra", "path"])
def test_native_manifest_controls_are_real(pair_case: PairCase, change: str) -> None:
    root = pair_case.root / "candidate"
    manifest = parse_json((root / "manifest.json").read_bytes())
    if change == "version":
        manifest["transport_version"] = "foreign"
    elif change == "extra":
        manifest["unexpected"] = True
    else:
        manifest["catalog"]["path"] = "../catalog.json"
    put(root, "manifest.json", manifest)
    with pytest.raises(ValueError):
        publish_pair(pair_case.root, pair_case.store_root)
    assert not pair_case.store_root.exists()


@pytest.mark.parametrize("location", ["same", "inside", "ancestor"])
def test_publication_rejects_source_store_overlap(pair_case: PairCase, location: str) -> None:
    root = pair_case.root
    target = {"same": root, "inside": root / "store", "ancestor": root.parent}[location]
    before = source.capture(root)
    with pytest.raises(ValueError, match="overlap"):
        publish_pair(root, target)
    assert source.capture(root) == before
    assert not (target / "runs").exists()
    assert not (target / "run_files").exists()
    assert pair_case.calls == []
