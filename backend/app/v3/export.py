"""Canonical, schema-validated static V3 artifact publication; never a simulation run."""

from functools import lru_cache
from hashlib import sha256
from os import link
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.catalog import build_catalog, build_initial_state
from app.v3.export_schema import schema
from app.v3.export_validation import validate_relations
from app.v3.interface import (
    CatalogSource,
    Json,
    V3InterfaceError,
    canonical_documents,
    envelope,
    identity,
)


def build_static_export(bundle: CatalogSource) -> Json:
    result = identity(
        {
            **envelope("static-export"),
            "catalog": build_catalog(bundle),
            "initial_state": build_initial_state(bundle),
        },
        "export_id",
    )
    validate_static_export(result)
    return result


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    value = schema()
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def validate_static_export(value: Json) -> None:
    try:
        _validator().validate(value)
    except ValidationError as exc:
        raise V3InterfaceError(f"static export schema: {exc.json_path}: {exc.message}") from exc
    for item, key in (
        (value, "export_id"),
        (value["catalog"], "catalog_id"),
        (value["initial_state"], "state_id"),
    ):
        if sha256_hex({name: data for name, data in item.items() if name != key}) != item[key]:
            raise V3InterfaceError(f"static export {key} mismatch")
    if value["catalog"]["layout"] != value["initial_state"]["layout"]:
        raise V3InterfaceError("catalog and initial state use different layouts")
    if value["catalog"]["source"] != value["initial_state"]["source"]:
        raise V3InterfaceError("catalog and initial state use different source bundles")
    validate_relations(value)


def write_static_export(bundle: CatalogSource, out_dir: Path) -> Json:
    value = build_static_export(bundle)
    documents = canonical_documents(bundle)
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        raise V3InterfaceError("static output directory must be empty")
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = _write(out_dir, "catalog.json", canonical_bytes(value["catalog"]))
    stock = _write(out_dir, "initial-state.json", canonical_bytes(value["initial_state"]))
    refs = [
        _write(out_dir, f"sources/{digest}.json", raw) for digest, raw in sorted(documents.items())
    ]
    manifest = {
        **envelope("static-manifest"),
        "export_id": value["export_id"],
        "catalog": catalog,
        "initial_state": stock,
        "source_documents": refs,
    }
    full_schema = schema()
    Draft202012Validator({"$defs": full_schema["$defs"], "$ref": "#/$defs/manifest"}).validate(
        manifest
    )
    _write(out_dir, "manifest.json", canonical_bytes(manifest))
    return manifest


def _write(root: Path, relative: str, raw: bytes) -> Json:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(raw)
        link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": relative, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}
