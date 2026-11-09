"""Bind public manual API references and responses to the verified native run."""

from app.storage.canonical_json import sha256_hex
from app.v3.api_manual_inputs import DOMAIN, EXPORT_VERSION, Json


def public_run_id(native_run_id: str, input_bundle_id: str) -> str:
    return sha256_hex(
        {
            "domain": DOMAIN,
            "native_run_id": native_run_id,
            "inputs": input_bundle_id,
            "export": EXPORT_VERSION,
        }
    )


def verified_response(run: Json, index: Json) -> Json:
    run_id = index["run_id"]
    return {
        "status": run["at_end"]["status"],
        "run_id": run_id,
        "native_run_id": run["run_id"],
        "input_hash": run["profile"]["profile_id"],
        "source_label": run["source_label"],
        "full_v3_warehouse": run["capabilities"]["full_v3_warehouse"],
        "frontend_adapter": run["capabilities"]["frontend_adapter"],
        "manifest": f"/api/v3/manual-runs/{run_id}/manifest",
    }


def check_manifest_inventory(transport: Json, index: Json) -> None:
    rows = {row["path"]: row for row in index["files"]}
    if len(rows) != len(index["files"]):
        raise ValueError("manual file inventory contains duplicate paths")
    descriptors = [
        transport["metadata"],
        transport["graph_document"],
        *transport["event_chunks"],
        *transport["snapshot_chunks"],
    ]
    for descriptor in descriptors:
        path = "run/" + descriptor["path"]
        row = rows.get(path)
        if row is None or any(row[key] != descriptor[key] for key in ("sha256", "bytes")):
            raise ValueError("manual file inventory differs from transport descriptors")
