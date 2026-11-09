"""The existing owned worker performs both planning and fresh producer authentication."""

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.api_offer_planning_inputs import DOMAIN, UnknownOfferPlan, load_request, public_id
from app.v3.api_offer_planning_storage import checked, publish, response, restored
from app.v3.offer_planning_cli_models import RAW_NAMES, PlanningFiles
from app.v3.offer_planning_cli_pipeline import plan_offer_files
from app.v3.offer_planning_cli_storage import put
from app.v3.offer_planning_cli_validation import validate_offer_plan
from app.v3.workload_policy import fields


def _result(value: dict[str, Any]) -> dict[str, Any]:
    if value["status"] != "passed":
        raise ArtifactCorruption("Planning producer validation did not pass")
    keys = (
        "plan_id",
        "semantic_bundle_id",
        "manifest_sha256",
        "selection_reason",
        "unallocated_offers",
        "engine_calls",
        "operational_admission",
        "actual_test_stream",
        "full_n1_acceptance",
    )
    return {"status": value["planning_status"], **{key: value[key] for key in keys}}


def _produce(store: ArtifactStore, request_id: str, attempt: Path) -> Path:
    snapshot, raw = load_request(store, request_id)
    put(attempt, "request.json", canonical_bytes(snapshot))
    for name in RAW_NAMES:
        put(attempt, "caller/" + name, raw[name])
    paths = [attempt / "caller" / name for name in RAW_NAMES]
    files = PlanningFiles(paths[0], paths[1], paths[2], paths[3])
    try:
        plan_offer_files(files, snapshot["model"], attempt / "output")
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidInputError("Offer planning explicit input validation failed") from exc
    return attempt / "output"


def planning_job(job: Job) -> dict[str, Any]:
    store = ArtifactStore(Path(job.store_root))
    payload = fields(job.payload, {"request_id"})
    identifier = public_id(payload["request_id"])
    if store.read_reference("runs", identifier) is not None:
        return planning_read_job(
            replace(
                job,
                kind="offer-planning-read-v3",
                payload={"planning_id": identifier, "artifact_id": None},
            )
        )
    root = store.root / "offer-planning-v3-evidence"
    root.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=root))
    try:
        output = _produce(store, payload["request_id"], attempt)
        try:
            result = _result(validate_offer_plan(output))
        except (ValueError, TypeError, KeyError) as exc:
            raise ArtifactCorruption("Produced offer planning authority is invalid") from exc
        return publish(store, payload["request_id"], output, result)
    except Exception as exc:
        put(
            attempt,
            "failure.json",
            canonical_bytes(
                {"domain": DOMAIN, "status": "failed", "exception_type": type(exc).__name__}
            ),
        )
        if isinstance(exc, (InvalidInputError, ArtifactCorruption)):
            raise
        raise UnexpectedExecutionError("Offer planning execution or publication failed") from exc


def planning_read_job(job: Job) -> dict[str, Any]:
    store = ArtifactStore(Path(job.store_root))
    payload = fields(job.payload, {"planning_id", "artifact_id"})
    index, raw = checked(store, payload["planning_id"])
    selected = [row for row in index["files"] if row["sha256"] == payload["artifact_id"]]
    if payload["artifact_id"] is not None and not selected:
        raise UnknownOfferPlan("File is not a member of this offer planning result")
    try:
        with tempfile.TemporaryDirectory(prefix="qoima-offer-planning-read-") as temporary:
            root = Path(temporary)
            restored(root, raw)
            expected = _result(validate_offer_plan(root))
        if canonical_bytes(expected) != canonical_bytes(index["result"]):
            raise ValueError("Typed producer result differs from saved response")
        if not selected:
            return response(index)
        name = selected[0]["path"]
        return {
            "body": raw[name],
            "media_type": "text/csv" if name.endswith(".csv") else "application/json",
        }
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("Stored offer planning producer authority is invalid") from exc
