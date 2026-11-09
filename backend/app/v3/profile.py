"""Compile a pinned source bundle and explicit synthetic choices into frozen inputs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.execution_types import (
    BoundGraph,
    ExecutionProfile,
    HandlingTimes,
    InitialPlacement,
    PlaceSpec,
    SourceBinding,
    TimedJob,
)
from app.v3.execution_validate import validate_profile
from app.v3.input_models import ImmutableDocument, V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.materialize import calendar_tick, materialize_jobs
from app.v3.profile_build import actors, document, loads, ports, storage
from app.v3.profile_connectors import add_connectors
from app.v3.profile_models import ManualProposal
from app.v3.profile_validation import validate_jobs
from app.v3.runtime_graph_source import LAYOUT_VERSION, compiled_graph


@dataclass(frozen=True, slots=True)
class CompiledManualInputs:
    profile: ExecutionProfile
    graph: BoundGraph
    horizon_tick: int
    end_tick: int
    input_hash: str
    graph_document: ImmutableDocument


def digest(value: Any) -> str:
    return sha256_hex(value)


def compile_manual_profile(bundle: V3Bundle, proposal: ManualProposal) -> CompiledManualInputs:
    expected = tuple((s.path, s.raw_sha256) for s in bundle.source_inventory)
    if proposal.source_revision != bundle.source_revision or proposal.source_hashes != expected:
        raise ValueError("synthetic profile source hashes/revision mismatch")
    if not proposal.proposal_id.strip() or not proposal.jobs or not proposal.buffers:
        raise ValueError("manual proposal needs identity, fixed jobs and finite buffers")
    jobs = materialize_jobs(proposal)
    links = document(bundle, "layout-links-v3.json")
    buffers = add_connectors(bundle, proposal, links)
    graph = compiled_graph(links, "walk")
    bound = BoundGraph(graph, LAYOUT_VERSION, digest(links))
    identity = digest(
        {
            "compiler": "v3-manual-profile-v1",
            "proposal": proposal.model_dump(),
            "graph_sha256": bound.sha256,
            "layout": bundle.layout_content_hash,
        }
    )
    profile = _profile(bundle, proposal, bound, buffers, identity, jobs)
    if min(profile.handling.pickup_ticks, profile.handling.place_ticks) <= 0:
        raise ValueError("pickup and place durations must be positive")
    validate_jobs(bundle, proposal, profile, graph)
    validate_profile(profile, bound)  # compiled output must pass engine admission (F3)
    return CompiledManualInputs(
        profile,
        bound,
        proposal.horizon_tick,
        proposal.end_tick,
        identity,
        ImmutableDocument(canonical_bytes(links)),
    )


def _profile(
    bundle: V3Bundle,
    proposal: ManualProposal,
    bound: BoundGraph,
    buffers: tuple[tuple[str, PlaceSpec], ...],
    identity: str,
    jobs: tuple[TimedJob, ...],
) -> ExecutionProfile:
    bindings = tuple(SourceBinding(s.path, s.raw_sha256) for s in bundle.source_inventory)
    bindings += (SourceBinding("synthetic/manual-proposal-v1", digest(proposal.model_dump())),)
    return ExecutionProfile(
        identity,
        LAYOUT_VERSION,
        bound.sha256,
        bindings,
        actors(proposal, set(bound.graph.node_ids)),
        ports(bundle, proposal, buffers),
        storage(bundle, set(bound.graph.node_ids)),
        loads(bundle, proposal),
        tuple(InitialPlacement(h.handling_unit_id, h.slot_id) for h in bundle.handling_units),
        jobs,
        HandlingTimes(
            calendar_tick(proposal.pickup_seconds), calendar_tick(proposal.place_seconds)
        ),
        "Explicit synthetic whole-HU manual demo, ADR0032; inactive source stock retained.",
    )


def load_manual_profile(bundle_path: Path, proposal_path: Path) -> CompiledManualInputs:
    proposal = ManualProposal.model_validate(parse_json(proposal_path.read_bytes()))
    return compile_manual_profile(load_v3_bundle(bundle_path), proposal)
