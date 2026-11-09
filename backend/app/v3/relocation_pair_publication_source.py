"""Capture closed immutable pair bytes before strict saved-native validation."""

import stat
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.api.context import Json
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run_projection import restore_outcome as restore_base
from app.v3.coordinator_transport_schema import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, reference
from app.v3.offer_planning_cli_storage import reject_links
from app.v3.relocation_native_projection import restore_outcome
from app.v3.relocation_pair_inputs import PreparedRelocationPair, load_relocation_pair_inputs
from app.v3.relocation_pair_report import build_pair_report
from app.v3.relocation_transport import IDENTITY_FIELDS, read_relocation_run
from app.v3.relocation_transport_schema import validate_manifest

ARMS = ("baseline", "candidate")
MAX_MEMBERS = 20_000
MAX_PAIR_BYTES = 2 * MAX_BUNDLE_BYTES + 4 * MAX_FILE_BYTES

type Members = tuple[tuple[str, bytes], ...]


@dataclass(frozen=True, slots=True)
class SavedPair:
    members: Members
    pair: PreparedRelocationPair
    runs: tuple[Json, Json]
    manifests: tuple[Json, Json]
    comparison: Json


def descriptor(path: str, raw: bytes) -> Json:
    return {"path": path, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def _ordinary(path: Path, *, directory: bool = False) -> tuple[int, int, int, int]:
    info = path.lstat()
    mode = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not mode(info.st_mode)
        or path.is_symlink()
        or path.is_junction()
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or (not directory and info.st_nlink != 1)
    ):
        raise ValueError("Saved pair cannot contain filesystem aliases or special files")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _inventory(root: Path) -> tuple[dict[str, tuple[int, int, int, int]], set[str]]:
    _ordinary(root, directory=True)
    pending, files, directories = [root], {}, set()
    while pending:
        for path in pending.pop().iterdir():
            name = path.relative_to(root).as_posix()
            if path.is_dir():
                _ordinary(path, directory=True)
                directories.add(name)
                pending.append(path)
            else:
                files[name] = _ordinary(path)
            if len(files) + len(directories) > MAX_MEMBERS:
                raise ValueError("Saved pair exceeds its bounded member inventory")
    return files, directories


def capture(root: Path) -> Members:
    reject_links(root.absolute())
    inventory, directories = _inventory(root)
    members: list[tuple[str, bytes]] = []
    total = 0
    for name, expected in sorted(inventory.items()):
        reference({"path": name, "bytes": expected[2], "sha256": "0" * 64}, set())
        with (root / name).open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        total += len(raw)
        if len(raw) != expected[2] or total > MAX_PAIR_BYTES:
            raise ValueError("Saved pair exceeds bounded immutable file capture")
        members.append((name, raw))
    if _inventory(root) != (inventory, directories):
        raise ValueError("Saved pair changed during immutable capture")
    parents = {p.as_posix() for name in inventory for p in Path(name).parents if str(p) != "."}
    if parents != directories:
        raise ValueError("Saved pair contains extra directories")
    return tuple(members)


def _manifest(raw: bytes) -> Json:
    value = parse_json(raw)
    if canonical_bytes(value) != raw:
        raise ValueError("Saved pair native manifest must be canonical")
    validate_manifest(value)
    return dict(value)


def manifests(members: Members) -> tuple[Json, Json]:
    raw = dict(members)
    if len(raw) != len(members) or len(raw) > MAX_MEMBERS:
        raise ValueError("Saved pair member inventory is duplicated or unbounded")
    result = tuple(_manifest(raw[arm + "/manifest.json"]) for arm in ARMS)
    expected = {"inputs.json", "comparison.json"}
    for arm, manifest in zip(ARMS, result, strict=True):
        expected.add(arm + "/manifest.json")
        for row in validate_manifest(manifest):
            name = arm + "/" + row["path"]
            if descriptor(row["path"], raw[name]) != {
                k: row[k] for k in ("path", "bytes", "sha256")
            }:
                raise ValueError("Saved pair raw member differs from native descriptor")
            expected.add(name)
    if raw.keys() != expected or sum(map(len, raw.values())) > MAX_PAIR_BYTES:
        raise ValueError("Saved pair closed native inventory differs")
    return result[0], result[1]


def restore(root: Path, members: Members) -> None:
    for name, raw in members:
        reference(descriptor(name, raw), set())
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _correlate(pair: PreparedRelocationPair, members: Members, runs: tuple[Json, Json]) -> None:
    raw = dict(members)
    for arm, bound, run in zip(ARMS, (pair.baseline, pair.candidate), runs, strict=True):
        if raw[arm + "/inputs.json"] != bound.frozen_bytes:
            raise ValueError("Saved native arm differs from its paired frozen inputs")
        if (
            run["input_hash"] != sha256(bound.frozen_bytes).hexdigest()
            or run["common_input_hash"] != pair.common_input_hash
        ):
            raise ValueError("Saved native arm input/common identity differs from pair")
    if runs[0]["registry_common_hash"] != runs[1]["registry_common_hash"]:
        raise ValueError("Saved pair common registry identities differ")


def _outcome(pair: PreparedRelocationPair, run: Json, arm: str) -> CoordinatorOutcome:
    profile = getattr(pair, arm).profile.coordinator
    if run["outcome_kind"] == "base_noop":
        return restore_base(profile, run["outcome"])
    if run["outcome_kind"] != "relocation":
        raise ValueError("Saved native outcome kind differs")
    return restore_outcome(profile, run["outcome"])


def validate(members: Members) -> SavedPair:
    native = manifests(members)
    raw = dict(members)
    pair = load_relocation_pair_inputs(raw["inputs.json"])
    with tempfile.TemporaryDirectory(prefix="qoima-relocation-pair-") as temporary:
        root = Path(temporary)
        restore(root, members)
        runs = (read_relocation_run(root / ARMS[0]), read_relocation_run(root / ARMS[1]))
    _correlate(pair, members, runs)
    for manifest, run in zip(native, runs, strict=True):
        if any(manifest[key] != run[key] for key in IDENTITY_FIELDS):
            raise ValueError("Saved pair manifest/native identities differ")
    before = _outcome(pair, runs[0], ARMS[0])
    after = _outcome(pair, runs[1], ARMS[1])
    comparison = build_pair_report(pair, runs[0], runs[1], before, after)
    if canonical_bytes(comparison) != raw["comparison.json"]:
        raise ValueError("Saved pair comparison differs from exact rebuilt native report")
    return SavedPair(members, pair, runs, native, comparison)
