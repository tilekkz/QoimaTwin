"""Immutable raw input ancestry: all 24 pinned base/vehicle/mesh files and manifests."""

from dataclasses import replace
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.pallet_outbound_pickup_identity import identity, require
from app.v3.pallet_outbound_pickup_models import PickupDocument, PickupSource

PINS = (
    ("v3-proposal", "6bd6d445c4ba7ee3c6d2f99ff2603502b7584b5b5559c5139925091d6c657cab"),
    ("v3-vehicle-proposal", "da9cf5b7e47e4c590de409f54e827e17614c951b1f36208f52ef123a179dffb2"),
    ("v3-mesh-proof-proposal", "8d3664e081e3906071ff70fdd00f274f047a498aeee98f3296f0e4c5cd4eddb7"),
)
PREFIX = "docs/v3/contract-proposals/"


def _entries(raw: bytes, digest: str) -> list[dict[str, Any]]:
    require(sha256(raw).hexdigest() == digest, "Pickup source provenance SHA256 mismatch")
    value: dict[str, Any] = parse_json(raw)
    result: list[dict[str, Any]] = value["sources"] if "sources" in value else value["files"]
    return result


def load_pickup_source(data_root: Path) -> PickupSource:
    documents: list[PickupDocument] = []
    try:
        for package, digest in PINS:
            raw = (data_root / package / "provenance.json").read_bytes()
            documents.append(PickupDocument(package, "provenance.json", raw))
            for entry in _entries(raw, digest):
                path = entry.get("stored_path", entry["path"])
                documents.append(
                    PickupDocument(
                        package, entry["path"], (data_root / package / path).read_bytes()
                    )
                )
    except OSError as error:
        raise ValueError("Pickup source missing or unreadable") from error
    source = PickupSource(tuple(documents), "")
    source = replace(source, source_hash=identity(source))
    verify_pickup_source(source)
    return source


def _check_document(document: PickupDocument, entry: dict[str, Any]) -> None:
    expected = entry.get("raw_sha256", entry.get("sha256"))
    raw = document.raw
    require(
        sha256(raw).hexdigest() == expected and len(raw) == entry["bytes"],
        "Pickup raw source changed",
    )
    require(
        sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == entry["git_blob_sha1"],
        "Pickup Git blob ancestry changed",
    )


def verify_pickup_source(source: PickupSource) -> None:
    require(type(source) is PickupSource, "Exact PickupSource required")
    require(
        type(source.documents) is tuple and type(source.source_hash) is str,
        "Exact source fields required",
    )
    for doc in source.documents:
        require(
            type(doc) is PickupDocument
            and type(doc.package) is str
            and type(doc.path) is str
            and type(doc.raw) is bytes,
            "Exact source document required",
        )
    actual = {(d.package, d.path): d for d in source.documents}
    require(len(actual) == len(source.documents), "Duplicate pickup document")
    expected: list[tuple[str, str]] = []
    for package, digest in PINS:
        key = package, "provenance.json"
        require(key in actual, "Missing pickup provenance")
        expected.append(key)
        for entry in _entries(actual[key].raw, digest):
            key = package, entry["path"]
            expected.append(key)
            require(key in actual, "Missing pickup raw source")
            _check_document(actual[key], entry)
    require(
        tuple(expected) == tuple((d.package, d.path) for d in source.documents),
        "Pickup source document universe/order changed",
    )
    require(
        source.source_hash == identity(replace(source, source_hash="")),
        "Pickup source canonical identity changed",
    )


def raw_document(source: PickupSource, package: str, path: str) -> bytes:
    return next(d.raw for d in source.documents if (d.package, d.path) == (package, path))


def document(source: PickupSource, name: str, package: str = "v3-proposal") -> dict[str, Any]:
    result: dict[str, Any] = parse_json(raw_document(source, package, PREFIX + name))
    return result
