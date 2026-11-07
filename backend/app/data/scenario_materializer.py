"""Materialize synthetic scenarios and publish canonical artifacts before simulation."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from app.contracts.config import SimulationConfig
from app.contracts.scenario import Provenance, Scenario
from app.data.catalog import Catalog, build_catalog, multiplied_weights, promotion_weights
from app.data.history import TEST_DAY, generate_history
from app.data.orders import generate_orders
from app.data.receipts import generate_receipts
from app.data.seeds import HISTORY, MASTER_SEED, ORDERS, RECEIPTS, stream_rng
from app.storage.canonical_json import CANONICALIZATION_VERSION, canonical_bytes, sha256_hex

GENERATOR_VERSION = "qoima-synthetic-v1"
type Profile = Literal["large-normal", "large-peak", "promotion"]


@dataclass(frozen=True, slots=True)
class MaterializedScenario:
    scenario: Scenario
    catalog: Catalog
    sampling_weights: tuple[float, ...]
    normalized_weights: tuple[float, ...]
    config_sha256: str


def materialize(profile: Profile, horizon_s: int, config: SimulationConfig) -> MaterializedScenario:
    """Each call starts a fresh ORDERS stream; history never consumes that stream."""
    if profile not in ("large-normal", "large-peak", "promotion"):
        raise ValueError(f"unknown profile: {profile}")
    if type(horizon_s) is not int or not 0 < horizon_s <= 168 * 3600:
        raise ValueError("scenario horizon_s must be positive integer seconds, at most 168 hours")
    catalog = build_catalog()
    base = catalog.normalized_weights
    sampling = multiplied_weights(base) if profile == "promotion" else base
    weights = promotion_weights(base) if profile == "promotion" else base
    load = config.profiles.large_peak if profile == "large-peak" else config.profiles.large_normal
    orders = generate_orders(stream_rng(ORDERS), weights, load.orders_per_hour, horizon_s, "ORD")
    receipts = generate_receipts(horizon_s)
    orders_hash = sha256_hex([order.model_dump(mode="json") for order in orders])
    receipts_hash = sha256_hex([receipt.model_dump(mode="json") for receipt in receipts])
    provenance = Provenance(
        kind="synthetic",
        generator_version=GENERATOR_VERSION,
        seed=MASTER_SEED,
        source_notes=(
            f"Frozen synthetic catalog; profile={profile}; test_day={TEST_DAY.isoformat()}; "
            + ("shortened_run=true; " if horizon_s < 3600 else "")
            + "promotion is a sampling-weight multiplier of 5 for DEMO_173 only. "
            "NumPy PCG64; per order: integers(2,5), choice(200,size=k,replace=False,p=weights), "
            "scalar integers(1,5) per selected SKU, then sort lines by sku_id."
        ),
        orders_sha256=orders_hash,
        receipts_sha256=receipts_hash,
    )
    scenario = Scenario(
        schema_version="2.0",
        scenario_id=f"{profile}-{horizon_s}s-{orders_hash[:12]}",
        layout_version=config.layout_version,
        provenance=provenance,
        horizon_s=float(horizon_s),
        orders=orders,
        receipts=receipts,
    )
    return MaterializedScenario(
        scenario,
        catalog,
        sampling,
        weights,
        sha256_hex(config.model_dump(mode="json", by_alias=True)),
    )


def _artifact_payloads(result: MaterializedScenario) -> dict[str, bytes]:
    scenario = canonical_bytes(result.scenario.model_dump(mode="json"))
    history = generate_history().to_csv(index=False, lineterminator="\n").encode("utf-8")
    catalog = asdict(result.catalog)
    weights = {
        "original": result.catalog.normalized_weights,
        "before_normalization": result.sampling_weights,
        "normalized": result.normalized_weights,
    }
    manifest = {
        "kind": "synthetic",
        "generator_version": GENERATOR_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "numpy_version": np.__version__,
        "seed": MASTER_SEED,
        "streams": {"history": HISTORY, "orders": ORDERS, "receipts": RECEIPTS},
        "scenario_id": result.scenario.scenario_id,
        "shortened_run": result.scenario.horizon_s < 3600,
        "test_day": TEST_DAY.isoformat(),
        "history": {"days": 56, "train_days": 42, "validation_days": 14},
        "catalog": catalog,
        "weights": weights,
        "hashes": {
            "scenario.json": hashlib.sha256(scenario).hexdigest(),
            "history_daily.csv": hashlib.sha256(history).hexdigest(),
            "orders": result.scenario.provenance.orders_sha256,
            "receipts": result.scenario.provenance.receipts_sha256,
            "catalog": sha256_hex(catalog),
            "weights": sha256_hex(weights),
            "config": result.config_sha256,
        },
    }
    return {
        "scenario.json": scenario,
        "history_daily.csv": history,
        "manifest.json": canonical_bytes(manifest),
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    """Same-directory temporary file, replaced only after a complete flushed write."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as f:
            temporary = Path(f.name)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_materialized(result: MaterializedScenario, out_dir: Path) -> None:
    """Atomically replace each file, publishing the manifest last.

    The directory is not a transactional snapshot: readers should verify the
    manifest's hashes. A manifest cannot include its own content hash.
    """
    payloads = _artifact_payloads(result)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        _atomic_write(out_dir / name, payload)
