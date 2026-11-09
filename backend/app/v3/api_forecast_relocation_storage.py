"""Closed immutable publication for existing native files; no validation cache."""

from typing import Any

from app.storage.artifacts import ArtifactCorruption, ArtifactStore, require_identifier
from app.storage.canonical_json import canonical_bytes
from app.v3.api_forecast_relocation_inputs import (
    DOMAIN,
    UnknownForecastRelocation,
    load_request,
    public_id,
)
from app.v3.api_forecast_relocation_validation import inventory
from app.v3.coordinator_transport_schema import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, reference
from app.v3.offer_planning_cli_storage import descriptor
from app.v3.workload_policy import fields


def known(store: ArtifactStore, identifier: str) -> dict[str, Any]:
    value = store.read_reference("runs", identifier)
    if value is None and not store.path("runs", identifier).exists():
        raise UnknownForecastRelocation("Unknown V3 forecast relocation result")
    try:
        row = fields(value, {"domain", "run_id", "request_id", "files", "result"})
        if row["domain"] != DOMAIN or row["run_id"] != identifier:
            raise ValueError("Forecast relocation namespace differs")
        if public_id(require_identifier(row["request_id"])) != identifier:
            raise ValueError("Request/public identity differs")
        return row
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("Forecast relocation publication identity is invalid") from exc


def checked(store: ArtifactStore, identifier: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    index = known(store, identifier)
    try:
        rows = index["files"]
        if type(rows) is not list:
            raise ValueError("File descriptors must be an array")
        refs = [reference(row, set()) for row in rows]
        if sum(row["bytes"] for row in refs) > 2 * MAX_BUNDLE_BYTES + 4 * MAX_FILE_BYTES:
            raise ValueError("Pair exceeds existing native file bounds")
        raw = {row["path"]: store.read_bytes("run_files", row["sha256"]) for row in refs}
        expected = [descriptor(name, raw[name]) for name in sorted(raw)]
        if canonical_bytes(rows) != canonical_bytes(expected):
            raise ValueError("Closed canonical file inventory differs")
        inventory(raw)
        load_request(store, index["request_id"])
        return index, raw
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("Forecast relocation saved bytes are invalid") from exc


def response(index: dict[str, Any]) -> dict[str, Any]:
    return dict(
        index["result"],
        domain=DOMAIN,
        run_id=index["run_id"],
        request_id=index["request_id"],
        files=index["files"],
    )


def verified_response(
    store: ArtifactStore, result: dict[str, Any], identifier: str
) -> dict[str, Any]:
    index, _ = checked(store, identifier)
    if canonical_bytes(result) != canonical_bytes(response(index)):
        raise ArtifactCorruption("Returned forecast relocation authority differs from publication")
    return result


def publish(
    store: ArtifactStore, request_id: str, raw: dict[str, bytes], result: dict[str, Any]
) -> dict[str, Any]:
    inventory(raw)
    rows = [
        dict(path=name, bytes=len(raw[name]), sha256=store.put_bytes("run_files", raw[name]))
        for name in sorted(raw)
    ]
    index: dict[str, Any] = dict(
        domain=DOMAIN,
        run_id=public_id(request_id),
        request_id=request_id,
        files=rows,
        result=result,
    )
    store.publish_reference("runs", index["run_id"], index)
    return verified_response(store, response(index), index["run_id"])
