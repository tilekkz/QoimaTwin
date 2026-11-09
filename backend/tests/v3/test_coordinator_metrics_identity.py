"""The immutable run domain includes the declared summary policy before first release."""

import hashlib
import json

import pytest

from app.v3 import coordinator_metrics
from app.v3.coordinator_run_identity import run_identity
from app.v3.coordinator_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION

INPUT_HASH = "1" * 64


def _expected(policy: str) -> str:
    declared = {
        "engine_version": "qoima-staff-coordinator-v3-proposal-3",
        "publication_version": "qoima-coordinator-run-0.2.0",
        "metrics_version": policy,
        "input_hash": INPUT_HASH,
    }
    raw = json.dumps(declared, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_declared_metrics_policy_is_part_of_canonical_run_identity() -> None:
    assert coordinator_metrics.METRICS_VERSION == "qoima-staff-coordinator-metrics-v2"
    assert PUBLICATION_VERSION == "qoima-coordinator-run-0.2.0"
    assert TRANSPORT_VERSION == "qoima-coordinator-run-bundle-0.1.0"
    expected = _expected("qoima-staff-coordinator-metrics-v2")
    assert run_identity(INPUT_HASH) == expected


def test_changed_summary_policy_cannot_reuse_same_physical_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = run_identity(INPUT_HASH)
    next_policy = "qoima-staff-coordinator-metrics-test-next"
    monkeypatch.setattr(coordinator_metrics, "METRICS_VERSION", next_policy)
    changed = run_identity(INPUT_HASH)
    assert changed == _expected(next_policy)
    assert changed != original
