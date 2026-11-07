"""Pinned conveyor supplement; the original fourteen-file V3 input pin is unchanged."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.v3 import conveyor_decode as decode
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_validation import validate_policy, validate_references
from app.v3.input_json import parse_json
from app.v3.input_models import ImmutableDocument, V3Bundle
from app.v3.input_pin import SOURCE_REVISION

SOURCE_PATH = "docs/v3/contract-proposals/conveyor-v3.json"
RAW_SHA256 = "3bf8cb57e46f853921bcf322d939e61dfd32db96d4e46184db18923889d17612"
GIT_BLOB_SHA1 = "d1a97197713f53f883cf49dc60ec469f07f6ae05"
RAW_BYTES = 94202


def load_conveyor_source(bundle: V3Bundle, supplement: Path | None = None) -> ConveyorSource:
    """Bind exact source bytes to the same revision as the already verified V3 bundle."""
    if bundle.source_revision != SOURCE_REVISION:
        raise ValueError("Conveyor supplement and V3 bundle revisions differ")
    root = supplement or Path(__file__).resolve().parents[2] / "data/v3-conveyor-proposal"
    try:
        raw = (root / "conveyor-v3.json").read_bytes()
        provenance = parse_json((root / "provenance.json").read_bytes(), "conveyor provenance")
    except OSError as exc:
        raise ValueError("Required conveyor supplement is unavailable") from exc
    expected = {
        "source_revision": SOURCE_REVISION,
        "source_path": SOURCE_PATH,
        "git_blob_sha1": GIT_BLOB_SHA1,
        "raw_sha256": RAW_SHA256,
        "bytes": RAW_BYTES,
    }
    if provenance != expected or len(raw) != RAW_BYTES:
        raise ValueError("Conveyor supplement provenance mismatch")
    if hashlib.sha256(raw).hexdigest() != RAW_SHA256:
        raise ValueError("Conveyor supplement raw SHA256 mismatch")
    source = decode_conveyor_document(parse_json(raw, SOURCE_PATH))
    return replace(source, source_revision=SOURCE_REVISION, raw_sha256=RAW_SHA256)


def decode_conveyor_document(document: Any) -> ConveyorSource:
    """Untrusted structural decoder for validation; never assigns verified provenance."""
    try:
        if not isinstance(document, dict):
            raise ValueError("Conveyor document must be an object")
        validate_policy(document)
        source = _decode(document)
        validate_references(source)
        return source
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed conveyor source records") from exc


def _decode(document: dict[str, Any]) -> ConveyorSource:
    raw = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    rules, assumptions = document["payload_admission"], document["source_assumptions"]
    footprint = rules["maximum_footprint_m"]
    if not isinstance(footprint, list) or len(footprint) != 2:
        raise ValueError("Source requires planar footprint dimensions")
    source = ConveyorSource(
        "",
        "",
        hashlib.sha256(raw).hexdigest(),
        ImmutableDocument(raw),
        decode.indexed(document["nodes"], "node_id", decode.node),
        decode.indexed(document["edges"], "edge_id", decode.edge),
        decode.indexed(document["cells"], "cell_id", decode.cell),
        decode.indexed(document["resources"], "resource_id", decode.resource),
        decode.indexed(document["packing_stations"], "pack_id", decode.station),
        len(document["physical_modules"]),
        decode.positive(assumptions["speed_m_s"]),
        decode.positive(assumptions["max_gross_kg_per_carrier"]),
        (decode.positive(footprint[0]), decode.positive(footprint[1])),
        decode.positive(rules["maximum_height_m"]),
        decode.positive(assumptions["payload_clearance_m"]),
        decode.positive(document["geometry"]["usable_width_m"]),
        tuple(rules["allowed"]),
    )
    dwell = decode.positive(assumptions["transfer_dwell_s"])
    if any(e.dwell_s and e.dwell_s != dwell for e in source.edges.values()):
        raise ValueError("Per-edge dwell differs from source assumption")
    return source
