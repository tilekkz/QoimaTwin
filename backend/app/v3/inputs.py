"""Public offline ingestion seam for a pinned, immutable V3 geometry proposal."""

from pathlib import Path
from typing import Any

from .input_build import build_bundle
from .input_catalogs import (
    validate_catalogs,
    validate_graphs,
    validate_layout,
    validate_source_links,
)
from .input_checks import get_document, indexed
from .input_json import PREFIX, verified_package
from .input_models import BaselineStats
from .input_models import V3Bundle as V3Bundle
from .input_models import V3InputError as V3InputError
from .input_ports import validate_ports
from .input_stock import validate_assignments, validate_skus, validate_slots


def validate_documents(documents: dict[str, Any]) -> BaselineStats:
    """Internal semantic stage, also used to exercise corruption independently of raw pins."""
    validate_layout(documents)
    validate_catalogs(documents)
    nodes = validate_graphs(documents)
    cargo = indexed(
        get_document(documents, "cargo-catalog-v3.json")["records"],
        "archetype_id",
        PREFIX + "cargo-catalog-v3.json/records",
    )
    slots = validate_slots(documents, cargo, nodes)
    ports = validate_ports(documents, set(cargo), nodes)
    skus = validate_skus(documents, cargo, ports)
    _, stats = validate_assignments(documents, cargo, skus, slots, ports)
    return stats


def load_v3_bundle(path: Path) -> V3Bundle:
    """Load only local reviewed bytes; fail closed on missing or changed sources."""
    inventory, documents = verified_package(path)
    validate_source_links(documents, {e.path: e.raw_sha256 for e in inventory})
    stats = validate_documents(documents)
    return build_bundle(documents, inventory, stats)
