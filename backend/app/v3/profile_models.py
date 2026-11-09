"""Strict, frozen backend synthetic proposal choices; no source claims."""

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class Choice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ActorChoice(Choice):
    actor_id: StrictStr
    home_node_id: StrictStr
    skills: tuple[StrictStr, ...]
    speed_m_s: StrictStr
    max_gross_mass_kg: StrictStr


class BufferChoice(Choice):
    place_id: StrictStr
    port_id: StrictStr
    zone_id: StrictStr
    bounds_xz: tuple[StrictStr, StrictStr, StrictStr, StrictStr]
    path_xz: tuple[tuple[StrictStr, StrictStr], ...]
    height_m: StrictStr
    max_payload_kg: StrictStr


class JobChoice(Choice):
    job_id: StrictStr
    arrival_seconds: StrictStr
    direction: StrictStr
    hu_id: StrictStr
    port_id: StrictStr
    slot_id: StrictStr
    receipt_template_hu_id: StrictStr | None = None


class ManualProposal(Choice):
    proposal_id: StrictStr
    calendar_policy: StrictStr
    source_revision: StrictStr
    source_hashes: tuple[tuple[StrictStr, StrictStr], ...]
    horizon_tick: StrictInt
    end_tick: StrictInt
    pickup_seconds: StrictStr
    place_seconds: StrictStr
    carry_width_m: StrictStr
    carry_height_m: StrictStr
    actors: tuple[ActorChoice, ...]
    buffers: tuple[BufferChoice, ...]
    jobs: tuple[JobChoice, ...]
