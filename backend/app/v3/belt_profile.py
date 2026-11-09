"""Strict source-bound whole-HU conveyor profiles; no invented pick/pack operations."""

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.storage.canonical_json import canonical_bytes
from app.v3.belt_models import BeltJob
from app.v3.belt_plan import compile_job
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.conveyor_source import RAW_SHA256, SOURCE_PATH
from app.v3.input_models import V3Bundle
from app.v3.run_values import record


class BeltJobProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    job_id: str = Field(min_length=1)
    hu_id: str = Field(min_length=1)
    payload_id: str = Field(min_length=1)
    arrival_tick: int = Field(ge=0)
    route: list[str] = Field(min_length=1)
    station_id: str | None
    station_dwell_tick: int = Field(ge=0)


class BeltProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    profile_id: str = Field(min_length=1)
    source_revision: str
    layout_content_hash: str
    horizon_tick: int = Field(gt=0)
    end_tick: int = Field(gt=0)
    jobs: list[BeltJobProposal]


@dataclass(frozen=True, slots=True)
class CompiledBeltProfile:
    jobs: tuple[BeltJob, ...]
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes

    @property
    def input_hash(self) -> str:
        return sha256(self.frozen_bytes).hexdigest()


def _job(bundle: V3Bundle, proposal: BeltJobProposal) -> BeltJob:
    units = {hu.handling_unit_id: hu for hu in bundle.handling_units}
    if proposal.hu_id not in units:
        raise ValueError("conveyor job requires an exact catalogue HU identity")
    hu = units[proposal.hu_id]
    cargo = next(c for c in bundle.cargo_archetypes if c.archetype_id == hu.archetype_id)
    x, y, z = (Fraction(str(value)) for value in cargo.dimensions_xyz_m)
    payload = ConveyorPayload(
        proposal.payload_id,
        hu.archetype_id,
        (x, y, z),
        Fraction(str(hu.gross_mass_kg)),
        "upright_xyz",
        hu.handling_unit_id,
        bundle.source_revision,
    )
    return BeltJob(
        proposal.job_id,
        hu.handling_unit_id,
        payload,
        proposal.arrival_tick,
        tuple(proposal.route),
        proposal.station_id,
        proposal.station_dwell_tick,
    )


def _validate_jobs(source: ConveyorSource, jobs: tuple[BeltJob, ...], horizon: int) -> None:
    for identities in (
        {job.job_id for job in jobs},
        {job.hu_id for job in jobs},
        {job.payload.payload_id for job in jobs},
    ):
        if len(identities) != len(jobs):
            raise ValueError("duplicate conveyor job, HU or payload identity")
    for job in jobs:
        if job.arrival_tick >= horizon:
            raise ValueError("conveyor arrival must precede horizon")
        compile_job(source, job)


def compile_belt_profile(
    bundle: V3Bundle,
    source: ConveyorSource,
    document: Any,
) -> CompiledBeltProfile:
    proposal = BeltProposal.model_validate(document)
    if proposal.source_revision != bundle.source_revision:
        raise ValueError("conveyor profile source revision mismatch")
    if proposal.layout_content_hash != bundle.layout_content_hash:
        raise ValueError("conveyor profile layout hash mismatch")
    if source.source_revision != bundle.source_revision or source.raw_sha256 != RAW_SHA256:
        raise ValueError("conveyor profile requires the verified source supplement")
    if proposal.end_tick < proposal.horizon_tick:
        raise ValueError("conveyor end cap must be at or after horizon")
    jobs = tuple(sorted((_job(bundle, job) for job in proposal.jobs), key=lambda j: j.job_id))
    _validate_jobs(source, jobs, proposal.horizon_tick)
    choices = proposal.model_dump(mode="json")
    choices["jobs"] = sorted(choices["jobs"], key=lambda j: j["job_id"])
    frozen = canonical_bytes(
        {
            "schema": "qoima.conveyor-component-inputs.v3-proposal",
            "proposal": choices,
            "jobs": [record(job) for job in jobs],
            "source_bindings": [record(item) for item in bundle.source_inventory],
            "conveyor_source": {
                "path": SOURCE_PATH,
                "raw_sha256": source.raw_sha256,
                "canonical_sha256": source.document_sha256,
                "document": source.document.decode(),
            },
            "external_offer_assumption": True,
            "inventory_integration": False,
        }
    )
    return CompiledBeltProfile(jobs, proposal.horizon_tick, proposal.end_tick, frozen)
