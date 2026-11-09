"""Four caller byte strings are frozen in CAS; only structural checks run at admission."""

from typing import Annotated, Any, Final, Literal

from pydantic import Field, field_validator

from app.contracts.base import FrozenModel
from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.input_pin import LAYOUT_VERSION, SOURCE_REVISION
from app.v3.offer_planning_cli_choices import decode_request_choices
from app.v3.offer_planning_cli_models import RAW_NAMES, versions
from app.v3.offer_planning_cli_storage import MAX_BYTES, descriptor
from app.v3.workload_policy import fields

DOMAIN: Final = "qoima-v3-offer-planning-api-1"
TextFile = Annotated[str, Field(strict=True, min_length=1, max_length=MAX_BYTES)]
TEXT_FIELDS = (
    "history_csv",
    "history_choices_json",
    "projection_choices_json",
    "placement_choices_json",
)


class UnknownOfferPlan(AppError):
    http_status = 404
    code = "unknown_offer_plan"


class OfferPlanningRequest(FrozenModel):
    schema_version: Literal["qoima-v3-offer-planning-api-1"]
    model: Literal["mean28", "hgb"]
    layout_version: str
    source_revision: str
    acknowledge_bounded_planning: bool
    history_csv: TextFile
    history_choices_json: TextFile
    projection_choices_json: TextFile
    placement_choices_json: TextFile

    @field_validator("acknowledge_bounded_planning")
    @classmethod
    def acknowledge(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit bounded synthetic planning acknowledgement required")
        return value


def raw_inputs(body: OfferPlanningRequest) -> dict[str, bytes]:
    if body.layout_version != LAYOUT_VERSION or body.source_revision != SOURCE_REVISION:
        raise InvalidInputError("Offer planning V3 source/layout differs")
    raw = {
        name: getattr(body, field).encode("utf-8")
        for name, field in zip(RAW_NAMES, TEXT_FIELDS, strict=True)
    }
    try:
        if any(len(value) > MAX_BYTES for value in raw.values()):
            raise ValueError("Input byte limit exceeded")
        decode_request_choices(raw)
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidInputError("Malformed explicit offer planning choices") from exc
    return raw


def snapshot(body: OfferPlanningRequest, raw: dict[str, bytes]) -> dict[str, Any]:
    return {
        "domain": DOMAIN,
        "model": body.model,
        "layout_version": body.layout_version,
        "source_revision": body.source_revision,
        "acknowledge_bounded_planning": True,
        "producer_versions": versions(),
        "raw_inputs": [descriptor(name, raw[name]) for name in RAW_NAMES],
    }


def freeze_request(store: ArtifactStore, body: OfferPlanningRequest) -> str:
    raw = raw_inputs(body)
    for value in raw.values():
        store.put_bytes("run_files", value)
    return store.put_json("bundles", snapshot(body, raw))


def public_id(request_id: str) -> str:
    return sha256_hex({"domain": DOMAIN, "request_id": request_id})


def load_request(store: ArtifactStore, identifier: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    try:
        value = fields(
            store.read_json("bundles", identifier),
            {
                "domain",
                "model",
                "layout_version",
                "source_revision",
                "acknowledge_bounded_planning",
                "producer_versions",
                "raw_inputs",
            },
        )
        rows = value["raw_inputs"]
        if type(rows) is not list or len(rows) != len(RAW_NAMES):
            raise ValueError("Closed request raw inventory required")
        raw = {
            name: store.read_bytes("run_files", row["sha256"])
            for name, row in zip(RAW_NAMES, rows, strict=True)
        }
        body = OfferPlanningRequest(
            schema_version=DOMAIN,
            model=value["model"],
            layout_version=value["layout_version"],
            source_revision=value["source_revision"],
            acknowledge_bounded_planning=value["acknowledge_bounded_planning"],
            **{
                field: raw[name].decode("utf-8")
                for name, field in zip(RAW_NAMES, TEXT_FIELDS, strict=True)
            },
        )
        if canonical_bytes(value) != canonical_bytes(snapshot(body, raw_inputs(body))):
            raise ValueError("Request differs from raw typed declarations")
        return value, raw
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Stored offer planning request is invalid") from exc
