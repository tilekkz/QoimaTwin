"""Immutable source bytes for reference-only physical-interface validation."""

from dataclasses import dataclass

VERSION = "qoima-physical-handoff-reference-0.1.0"
SOURCE_REVISION = "799ff93af8b082b8f1c0a40e4112b9bf8c83df11"
VALIDATION_SCOPE = "reference_only"


@dataclass(frozen=True, slots=True)
class HandoffDocument:
    path: str
    raw: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class PhysicalHandoff:
    source_revision: str
    bundle_raw: bytes
    documents: tuple[HandoffDocument, ...]
    frozen_bytes: bytes
    input_hash: str
