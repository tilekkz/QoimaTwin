"""Reproduce vehicle prerequisites offline using base package plus immutable supplement."""

from pathlib import Path

from .input_pin import PROVENANCE_SHA256
from .vehicle_source import PINNED_SHA256, VehicleAdapter, _decode_adapter, verified_json

SUPPLEMENT_PROVENANCE_SHA256 = "da9cf5b7e47e4c590de409f54e827e17614c951b1f36208f52ef123a179dffb2"
SUPPLEMENT_FILES = frozenset(
    {"layout-conflicts-v3.json", "vehicle-graph-v3.json", "vehicle-handling-v3.json"}
)


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"required vehicle source unreadable: {path.name}") from exc


def load_repository_vehicle_adapter(base_root: Path, supplement_root: Path) -> VehicleAdapter:
    """Both manifests and all six raw documents are pinned; no fallback or network reads."""
    verified_json(_read(supplement_root / "provenance.json"), SUPPLEMENT_PROVENANCE_SHA256)
    verified_json(_read(base_root / "provenance.json"), PROVENANCE_SHA256)
    documents: dict[str, bytes] = {}
    for name in PINNED_SHA256:
        root = supplement_root if name in SUPPLEMENT_FILES else base_root
        documents[name] = _read(root / "docs/v3/contract-proposals" / name)
    return _decode_adapter(documents)
