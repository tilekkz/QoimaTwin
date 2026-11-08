"""Public identity and inventory bind namespace3 inputs and actual native observations."""

from app.storage.canonical_json import sha256_hex
from app.v3.api_coordinator_inputs import DOMAIN, EXPORT_VERSION
from app.v3.coordinator_models import COORDINATOR_VERSION
from app.v3.coordinator_profile import COMPILER_VERSION
from app.v3.interface import Json


def public_run_id(native: str, bundle: str) -> str:
    return sha256_hex(
        {
            "domain": DOMAIN,
            "native_run_id": native,
            "inputs": bundle,
            "engine": COORDINATOR_VERSION,
            "compiler": COMPILER_VERSION,
            "export": EXPORT_VERSION,
        }
    )


def verified_response(run: Json, index: Json) -> Json:
    """Called only after strict C65 read; do not infer terminal status from one worker field."""
    outcome = run["outcome"]
    return {
        "status": run["status"],
        "run_id": index["run_id"],
        "native_run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "registry_common_hash": run["registry_common_hash"],
        "request_sha256": index["request_sha256"],
        "business_complete_tick": outcome["business_complete_tick"],
        "resource_drained_tick": outcome["resource_drained_tick"],
        "observation_end_tick": outcome["observation_end_tick"],
        "staffing_status": outcome["staffing_status"],
        "constraint_violations": outcome["constraint_violations"],
        "metrics": run["metrics"],
        "operational_admission": False,
        "capabilities": {
            "captured_checkpoints": True,
            "observed_events": True,
            "arbitrary_seek": False,
            "interpolation": False,
            "full_v3": False,
            "frontend_adapter": False,
            "human_contact_proof": False,
        },
        "manifest": f"/api/v3/coordinator-runs/{index['run_id']}/manifest",
    }


def manifest_descriptors(manifest: Json) -> list[Json]:
    return [
        manifest["inputs"],
        manifest["catalog"],
        *manifest["event_chunks"],
        *manifest["snapshot_chunks"],
    ]


def check_manifest_inventory(manifest: Json, index: Json) -> None:
    rows = {row["path"]: row for row in index["files"]}
    descriptors = manifest_descriptors(manifest)
    paths = [row["path"] for row in descriptors]
    expected = {"manifest.json", *paths}
    if len(paths) != len(set(paths)) or "manifest.json" in paths:
        raise ValueError("duplicate coordinator transport descriptor path")
    if len(rows) != len(index["files"]) or rows.keys() != expected:
        raise ValueError("coordinator native inventory differs from manifest")
    for row in descriptors:
        if type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ValueError("coordinator descriptor length must be an exact positive integer")
        if any(rows[row["path"]][key] != row[key] for key in ("sha256", "bytes")):
            raise ValueError("coordinator descriptor differs from immutable inventory")
