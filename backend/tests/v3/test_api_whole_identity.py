"""Whole public results include paid return and keep native inventory separate from CLI evidence."""

from copy import deepcopy

import pytest

from app.v3.api_whole_identity import check_manifest_inventory, public_run_id, verified_response
from app.v3.interface import Json
from app.v3.whole_run import build_whole_run
from tests.v3.test_receipt_flow_fixtures import SECOND
from tests.v3.test_whole_run_fixtures import sample


def test_whole_business_handover_does_not_hide_paid_return() -> None:
    inputs, outcome = sample(horizon=46 * SECOND, end=47 * SECOND)
    run = build_whole_run(inputs, outcome)
    index = {"run_id": "a" * 64, "request_sha256": "b" * 64}
    response = verified_response(run, index)
    assert response["status"] == "partial"
    assert run["metrics"]["at_end"]["whole"]["completed_units"] == 24
    assert run["metrics"]["at_end"]["whole"]["pending_return"] == 1
    run["status"] = "complete"
    with pytest.raises(ValueError, match="paid return"):
        verified_response(run, index)


def test_public_identity_separates_registered_bundle_from_native_run() -> None:
    native, registration = "1" * 64, "2" * 64
    result = public_run_id(native, registration)
    assert result != native
    assert result != public_run_id(native, "3" * 64)
    assert result != public_run_id("4" * 64, registration)


def test_native_inventory_must_not_mix_outer_cli_evidence() -> None:
    descriptors = [
        {"path": path, "sha256": str(i) * 64, "bytes": i + 1}
        for i, path in enumerate(("inputs.json", "catalog.json", "metadata.json"), 1)
    ]
    manifest: Json = dict(zip(("inputs", "catalog", "metadata"), descriptors, strict=True))
    manifest.update(event_chunks=[], checkpoint_chunks=[])
    index = {
        "files": [{"path": "manifest.json", "sha256": "a" * 64, "bytes": 5}, *descriptors],
        "request_files": [{"path": "request.json", "sha256": "b" * 64, "bytes": 10}],
    }
    check_manifest_inventory(manifest, index)
    mixed = deepcopy(index)
    mixed["files"].append(mixed["request_files"][0])
    with pytest.raises(ValueError, match="inventory"):
        check_manifest_inventory(manifest, mixed)
