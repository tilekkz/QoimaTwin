"""Immutable local objects; references publish last with no overwrite (ADR0018)."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from app.errors import AppError, InvalidInputError
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex

KINDS = frozenset(
    {
        "bundles",
        "scenarios",
        "histories",
        "forecasts",
        "assignments",
        "plans",
        "comparisons",
        "run_files",
        "runs",
        "requests",
        "explanations",
    }
)
REFERENCES = frozenset({"runs", "requests", "explanations"})


class ArtifactConflict(AppError):
    code = "immutable_artifact_conflict"
    http_status = 409


class ArtifactCorruption(AppError):
    code = "artifact_corruption"


def require_identifier(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise InvalidInputError("artifact reference must be 64 lowercase hexadecimal characters")
    return value


def _confinement_path(path: PurePath) -> PurePath:
    """Compare equivalent resolved Windows drive/UNC forms without weakening confinement."""
    if not isinstance(path, PureWindowsPath):
        return path
    value = str(path)
    if value.upper().startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\") and re.match(r"[A-Za-z]:\\", value[4:]):
        value = value[4:]
    return PureWindowsPath(value)


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, kind: str, identifier: str) -> Path:
        if kind not in KINDS:
            raise InvalidInputError("unknown artifact namespace")
        path = (self.root / kind / f"{require_identifier(identifier)}.data").resolve()
        if not _confinement_path(path).is_relative_to(_confinement_path(self.root)):
            raise InvalidInputError("artifact path escapes the store")
        return path

    def put_bytes(self, kind: str, payload: bytes) -> str:
        if kind in REFERENCES:
            raise InvalidInputError("use publish_reference for a semantic reference")
        identifier = hashlib.sha256(payload).hexdigest()
        self._publish(self.path(kind, identifier), payload)
        return identifier

    def put_json(self, kind: str, payload: object) -> str:
        return self.put_bytes(kind, canonical_bytes(payload))

    def read_bytes(self, kind: str, identifier: str) -> bytes:
        if kind in REFERENCES:
            raise InvalidInputError("use read_reference for a semantic reference")
        path = self.path(kind, identifier)
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise InvalidInputError(f"unknown {kind} reference: {identifier}") from exc
        if hashlib.sha256(payload).hexdigest() != identifier:
            raise ArtifactCorruption(f"artifact hash mismatch: {kind}/{identifier}")
        return payload

    def read_json(self, kind: str, identifier: str) -> Any:
        return parse_json(self.read_bytes(kind, identifier))

    def publish_reference(self, kind: str, identifier: str, value: object) -> None:
        if kind not in REFERENCES:
            raise InvalidInputError("namespace requires a content hash")
        envelope = {"content_sha256": sha256_hex(value), "value": value}
        self._publish(self.path(kind, identifier), canonical_bytes(envelope))

    def read_reference(self, kind: str, identifier: str) -> Any:
        if kind not in REFERENCES:
            raise InvalidInputError("namespace requires a content hash")
        path = self.path(kind, identifier)
        if not path.exists():
            return None
        envelope = parse_json(path.read_bytes())
        if sha256_hex(envelope["value"]) != envelope["content_sha256"]:
            raise ArtifactCorruption("reference content hash mismatch")
        return envelope["value"]

    @staticmethod
    def _publish(target: Path, payload: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != payload:
                raise ArtifactConflict("immutable artifact already has different content")
            return
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)  # atomic create-if-absent on the same filesystem
            except FileExistsError:
                if target.read_bytes() != payload:
                    raise ArtifactConflict("immutable publication race") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
