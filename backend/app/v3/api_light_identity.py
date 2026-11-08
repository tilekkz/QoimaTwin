"""Public identity includes the exact registered source/profile and native engine identity."""

from app.api.context import Json
from app.storage.canonical_json import sha256_hex
from app.v3.api_light_inputs import DOMAIN, EXPORT_VERSION
from app.v3.flow_profile import COMPILER_VERSION
from app.v3.flow_run_validation import validate_terminal_status
from app.v3.light_flow_models import LIGHT_FLOW_ENGINE_VERSION


def public_run_id(native: str, bundle: str) -> str:
    return sha256_hex(
        {
            "domain": DOMAIN,
            "native_run_id": native,
            "inputs": bundle,
            "engine": LIGHT_FLOW_ENGINE_VERSION,
            "compiler": COMPILER_VERSION,
            "export": EXPORT_VERSION,
        }
    )


def verified_response(run: Json, index: Json) -> Json:
    validate_terminal_status(run)
    return {
        "status": run["status"],
        "run_id": index["run_id"],
        "native_run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "capabilities": run["capabilities"],
        "operational_admission": False,
        "manifest": f"/api/v3/light-runs/{index['run_id']}/manifest",
    }


def check_manifest_inventory(manifest: Json, index: Json) -> None:
    rows = {r["path"]: r for r in index["files"]}
    descriptors = [manifest[k] for k in ("inputs", "catalog", "metadata")]
    descriptors.extend([*manifest["event_chunks"], *manifest["checkpoint_chunks"]])
    expected = {"manifest.json", *(r["path"] for r in descriptors)}
    if len(rows) != len(index["files"]) or rows.keys() != expected:
        raise ValueError("connected run file inventory differs from its manifest")
    for descriptor in descriptors:
        if any(rows[descriptor["path"]][k] != descriptor[k] for k in ("sha256", "bytes")):
            raise ValueError("connected descriptor differs from immutable inventory")
