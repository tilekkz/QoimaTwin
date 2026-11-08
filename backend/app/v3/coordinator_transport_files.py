"""Manifest-last C bundle IO with exact preexisting input evidence and no path aliases."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_transport_schema import MAX_FILE_BYTES


def put(root: Path, relative: str, raw: bytes) -> dict[str, Any]:
    if not 0 < len(raw) <= MAX_FILE_BYTES:
        raise ValueError("Coordinator file exceeds the explicit byte bound")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": relative, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def require_output(root: Path, inputs: bytes) -> None:
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Coordinator output requires an ordinary directory")
    if not root.exists():
        return
    children = list(root.iterdir())
    if not children:
        return
    path = root / "inputs.json"
    if children != [path] or path.is_symlink() or not path.is_file() or path.read_bytes() != inputs:
        raise ValueError("Coordinator output must be empty or contain only exact frozen inputs")


def publish(stage: Path, root: Path, inputs: bytes) -> None:
    require_output(root, inputs)
    root.mkdir(parents=True, exist_ok=True)
    paths = sorted(p for p in stage.rglob("*") if p.is_file() and p.name != "manifest.json")
    paths.append(stage / "manifest.json")
    created: list[Path] = []
    try:
        for source in paths:
            relative = source.relative_to(stage)
            target = root / relative
            if relative.as_posix() == "inputs.json" and target.exists():
                if target.is_symlink() or target.read_bytes() != inputs:
                    raise ValueError("Frozen coordinator input changed during publication")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                created.append(target)
                stream.write(source.read_bytes())
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def read_file(root: Path, ref: dict[str, Any]) -> bytes:
    path: Path = root / ref["path"]
    if (
        path.is_symlink()
        or not path.is_file()
        or not path.resolve().is_relative_to(root.resolve())
        or path.stat().st_size != ref["bytes"]
    ):
        raise ValueError("Coordinator file is missing, aliased or has a different byte length")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Coordinator file raw hash differs from its manifest")
    return raw


def read_json(root: Path, ref: dict[str, Any]) -> Any:
    raw = read_file(root, ref)
    value = parse_json(raw)
    if canonical_bytes(value) != raw:
        raise ValueError("Coordinator bundle files require exact canonical JSON bytes")
    return value


def closed_inventory(root: Path, refs: list[dict[str, Any]]) -> None:
    expected = {"manifest.json", *(ref["path"] for ref in refs)}
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Coordinator bundle cannot contain filesystem aliases")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise ValueError("Coordinator bundle closed file inventory differs from manifest")
