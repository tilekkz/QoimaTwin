"""Opaque registered actual profiles and explicit outer experiment requests."""

from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Final, Literal

from pydantic import Field, field_validator

from app.api.models import ArtifactId
from app.contracts.base import FrozenModel
from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore, require_identifier
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.api_coordinator_binding import registration
from app.v3.api_offer_planning_inputs import public_id as offer_id
from app.v3.api_offer_planning_storage import checked as checked_offer
from app.v3.forecast_relocation_models import VERSION
from app.v3.input_pin import LAYOUT_VERSION, SOURCE_REVISION
from app.v3.offer_planning_cli_storage import read_regular
from app.v3.relocation_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION
from app.v3.workload_policy import fields

DOMAIN: Final = "qoima-v3-forecast-relocation-api-1"
PROFILE_DOMAIN: Final = "qoima-v3-forecast-relocation-profile-1"


class UnknownForecastRelocation(AppError):
    code = "unknown_forecast_relocation"
    http_status = 404


class ForecastRelocationRequest(FrozenModel):
    schema_version: Literal["qoima-v3-forecast-relocation-api-1"]
    offer_request_id: ArtifactId
    actual_profile_id: ArtifactId
    job_id: Annotated[str, Field(min_length=1, max_length=200)]
    arrival_tick: Annotated[int, Field(ge=0)]
    layout_version: str
    source_revision: str
    acknowledge_bounded_manual: bool

    @field_validator("acknowledge_bounded_manual")
    @classmethod
    def acknowledge(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit bounded manual relocation acknowledgement required")
        return value


def recipe_hash() -> str:
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/proposals/adaptive-v3/coordinator-profile.example.json"
    )
    return sha256(read_regular(path)).hexdigest()


def profile_snapshot(registration_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return dict(
        domain=PROFILE_DOMAIN,
        recipe_sha256=recipe_hash(),
        registration_id=registration_id,
        metadata=metadata,
    )


def load_profile(store: ArtifactStore, identifier: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        value = fields(
            store.read_json("bundles", identifier),
            {"domain", "recipe_sha256", "registration_id", "metadata"},
        )
        if value["domain"] != PROFILE_DOMAIN or value["recipe_sha256"] != recipe_hash():
            raise ValueError("Actual profile recipe or namespace differs")
        if type(value["metadata"]) is not dict:
            raise ValueError("Actual profile metadata must be an object")
        raw = registration(store, require_identifier(value["registration_id"]))
        return value, raw
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Registered actual profile is invalid") from exc


def snapshot(body: ForecastRelocationRequest) -> dict[str, Any]:
    if body.layout_version != LAYOUT_VERSION or body.source_revision != SOURCE_REVISION:
        raise InvalidInputError("Forecast relocation V3 source/layout differs")
    return dict(
        domain=DOMAIN,
        request=body.model_dump(mode="json"),
        versions=dict(bridge=VERSION, publication=PUBLICATION_VERSION, transport=TRANSPORT_VERSION),
    )


def freeze_request(store: ArtifactStore, body: ForecastRelocationRequest) -> str:
    value = snapshot(body)
    checked_offer(store, offer_id(body.offer_request_id))
    load_profile(store, body.actual_profile_id)
    return store.put_json("bundles", value)


def public_id(request_id: str) -> str:
    return sha256_hex(dict(domain=DOMAIN, request_id=request_id))


def load_request(store: ArtifactStore, identifier: str) -> ForecastRelocationRequest:
    try:
        value = fields(store.read_json("bundles", identifier), {"domain", "request", "versions"})
        body = ForecastRelocationRequest.model_validate(value["request"])
        if canonical_bytes(value) != canonical_bytes(snapshot(body)):
            raise ValueError("Request namespace or producer versions differ")
        load_profile(store, body.actual_profile_id)
        return body
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Stored forecast relocation request is invalid") from exc
