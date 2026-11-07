"""Immutable CLI publication of explicit synthetic whole-HU offers."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.errors import require_empty_output
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.inputs import load_v3_bundle
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_policy import parse_workload_policy
from app.v3.workload_source import load_workload_source
from app.v3.workload_wire import policy_dict


def _write(path: Path, document: object) -> dict[str, Any]:
    raw = canonical_bytes(document)
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def materialize_workload_file(inputs_path: Path, policy_path: Path, out: Path) -> dict[str, Any]:
    require_empty_output(out)
    policy = parse_workload_policy(parse_json(policy_path.read_bytes()))
    source = load_workload_source(load_v3_bundle(inputs_path))
    workload = materialize_workload(source, policy)
    out.mkdir(parents=True, exist_ok=True)
    files = [
        _write(out / "policy.json", policy_dict(policy)),
        _write(out / "workload.json", workload.to_dict()),
    ]
    report = {
        "status": "passed",
        "data_kind": "synthetic_timed_workload",
        "workload_id": workload.workload_id,
        "population_id": workload.population_id,
        "source_revision": source.source_revision,
        "operational_admission": False,
        "offered_hus": {"inbound": policy.inbound_hus, "outbound": policy.outbound_hus},
    }
    _write(out / "manifest.json", {**report, "files": files})
    return {**report, "manifest": "manifest.json"}
