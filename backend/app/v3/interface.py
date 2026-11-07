"""Read-only seam between validated V3 ingestion and static interface projections."""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex

type Json = dict[str, Any]

PREFIX = "docs/v3/contract-proposals/"
LAYOUT_VERSION = "qoima-144x72-v3-proposal"
SCHEMA_VERSION = "0.1.0"
INTERFACE_VERSION = "qoima-v3-static-interface-1"
CAPABILITIES = {
    "static_catalog": True,
    "initial_stock_projection": True,
    "operational_admission": False,
    "actual_engine_run": False,
    "timed_materialization": False,
    "comparison": False,
    "operational_replay": False,
}


class SourceRef(Protocol):
    @property
    def path(self) -> str: ...

    @property
    def raw_sha256(self) -> str: ...

    @property
    def bytes(self) -> int: ...


class ImmutableDocument(Protocol):
    @property
    def canonical_bytes(self) -> bytes: ...

    def decode(self) -> Any: ...


class CatalogSource(Protocol):
    @property
    def source_revision(self) -> str: ...

    @property
    def layout_content_hash(self) -> str: ...

    @property
    def source_inventory(self) -> Sequence[SourceRef]: ...

    @property
    def documents(self) -> Mapping[str, ImmutableDocument]: ...


class V3InterfaceError(ValueError):
    """A projection cannot faithfully represent the supplied frozen source bundle."""


def document(bundle: CatalogSource, name: str) -> Json:
    path = PREFIX + name
    try:
        value = parse_json(bundle.documents[path].canonical_bytes)
    except KeyError as exc:
        raise V3InterfaceError(f"missing source document: {path}") from exc
    if not isinstance(value, dict):
        raise V3InterfaceError(f"source document must be an object: {path}")
    return value


def fields(value: Json, names: str) -> Json:
    try:
        return {name: value[name] for name in names.split()}
    except KeyError as exc:
        raise V3InterfaceError(f"missing projection field: {exc.args[0]}") from exc


def identity(value: Json, key: str) -> Json:
    return {key: sha256_hex(value), **value}


def envelope(schema: str) -> Json:
    return {
        "schema_id": f"qoima.{schema}.v3-proposal",
        "schema_version": SCHEMA_VERSION,
        "data_kind": "static_geometry_proposal",
        "contract_status": "proposal",
        "operational_admission": False,
    }


def source_binding(bundle: CatalogSource) -> Json:
    entries = {entry.path: entry for entry in bundle.source_inventory}
    documents = []
    for path, value in sorted(bundle.documents.items()):
        if path not in entries:
            raise V3InterfaceError(f"source inventory does not bind document: {path}")
        source = entries[path]
        documents.append(
            {
                "path": path,
                "raw_sha256": source.raw_sha256,
                "bytes": source.bytes,
                "canonical_sha256": sha256_hex(parse_json(value.canonical_bytes)),
            }
        )
    return {
        "revision": bundle.source_revision,
        "documents": documents,
        "interface_version": INTERFACE_VERSION,
    }


def layout_binding(bundle: CatalogSource) -> Json:
    value = document(bundle, "layout-manifest-v3.json")
    if value["layout_version"] != LAYOUT_VERSION:
        raise V3InterfaceError("unsupported V3 layout version")
    if value["layout_content_hash"] != bundle.layout_content_hash:
        raise V3InterfaceError("layout content hash differs from the frozen bundle")
    return {
        "layout_version": LAYOUT_VERSION,
        "layout_content_hash": bundle.layout_content_hash,
        "bounds": value["envelope"]["bounds"],
        "units": value["units"],
        "model_scale_factor": 1,
    }


def canonical_documents(bundle: CatalogSource) -> dict[str, bytes]:
    return {
        sha256_hex(parse_json(doc.canonical_bytes)): canonical_bytes(
            parse_json(doc.canonical_bytes)
        )
        for doc in bundle.documents.values()
    }
