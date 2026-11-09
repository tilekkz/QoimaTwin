"""Check a fixed, versioned fixture oracle in normal and optimized Python processes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.settings import default_contracts_dir
from app.version import ENGINE_VERSION
from tests.golden_identity_oracle import build_fingerprint, canonical_hash, source_hashes
from tests.probes import probe

GOLDEN_PATH = Path(__file__).parent / "golden" / "qoima-engine-0.4.0.json"


def checked_probe() -> dict[str, Any]:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    contracts = default_contracts_dir()
    identity = build_fingerprint(contracts)
    if golden["fingerprint"] != identity or identity["engine_version"] != ENGINE_VERSION:
        raise RuntimeError("fixture input identity/version differs from the reviewed golden")
    if golden["contracts_text_lf_sha256"] != source_hashes(contracts):
        raise RuntimeError("fixture source contracts differ from the reviewed golden")
    expected = {
        "run_id": canonical_hash(identity),
        "events_sha256": golden["event_regression"]["events_sha256"],
    }
    if golden["run_id"] != expected["run_id"]:
        raise RuntimeError("golden run_id does not match its independent input preimage")
    actual = probe()
    if actual != expected:
        raise RuntimeError(f"fixture regression differs: expected={expected}, actual={actual}")
    return {
        "status": "passed",
        "engine_version": ENGINE_VERSION,
        "identity_version": identity["identity_version"],
        **actual,
    }


if __name__ == "__main__":
    print(json.dumps(checked_probe(), sort_keys=True))
