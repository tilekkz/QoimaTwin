"""Freeze validated shared inputs once, then pass only immutable IDs to child jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import jsonschema

from app.contracts.actors import ActorRegistry
from app.contracts.assignment import Assignment
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle, load_contract_bundle
from app.contracts.runtime_inputs import load_assignment, validate_config_file
from app.data.catalog import SKU_IDS
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.version import ENGINE_VERSION

type Json = dict[str, Any]
type JobKind = Literal[
    "materialize",
    "forecast",
    "plans",
    "compare",
    "manual-v3",
    "light-v3",
    "receipt-v3",
    "whole-v3",
    "coordinator-v3",
    "offer-planning-v3",
    "offer-planning-read-v3",
    "forecast-relocation-profile-v3",
    "forecast-relocation-v3",
    "forecast-relocation-read-v3",
    "relocation-pair-read-v3",
]


@dataclass(frozen=True)
class Job:
    kind: JobKind
    payload: Json
    store_root: str
    bundle_id: str
    assignment_id: str
    contracts_dir: str


@dataclass(frozen=True)
class ApiContext:
    store: ArtifactStore
    bundle: ContractBundle
    bundle_id: str
    assignment_id: str

    @classmethod
    def create(cls, store: ArtifactStore, contracts_dir: Path) -> ApiContext:
        try:
            validate_config_file(contracts_dir / "simulation_defaults.json")
        except jsonschema.ValidationError as exc:
            raise InvalidInputError(f"configuration schema: {exc.message}") from exc
        bundle = load_contract_bundle(contracts_dir)
        bundle_id = store.put_json(
            "bundles",
            {
                "layout": bundle.layout.model_dump(mode="json", by_alias=True),
                "config": bundle.config.model_dump(mode="json", by_alias=True),
                "actors": bundle.actors.model_dump(mode="json"),
            },
        )
        assignment = load_assignment(contracts_dir / "assignment.example.json", bundle.layout)
        assignment_id = store.put_json("assignments", assignment.model_dump(mode="json"))
        return cls(store, bundle, bundle_id, assignment_id)

    def job(self, kind: JobKind, payload: Json) -> Job:
        return Job(
            kind,
            payload,
            str(self.store.root),
            self.bundle_id,
            self.assignment_id,
            str(self.bundle.directory),
        )

    def catalog(self) -> Json:
        return {
            "schema_version": "2.0",
            "layout_version": self.bundle.layout.layout_version,
            "engine_version": ENGINE_VERSION,
            "bundle_id": self.bundle_id,
            "assignment_id": self.assignment_id,
            "sku_ids": list(SKU_IDS),
            "profiles": self.bundle.config.profiles.model_dump(mode="json", by_alias=True),
        }


def job_bundle(job: Job) -> ContractBundle:
    data = ArtifactStore(Path(job.store_root)).read_json("bundles", job.bundle_id)
    return ContractBundle(
        Path(job.contracts_dir),
        Layout.from_data(data["layout"]),
        SimulationConfig.from_data(data["config"]),
        ActorRegistry.from_data(data["actors"]),
    )


def stored_assignment(store: ArtifactStore, identifier: str, layout: Layout) -> Assignment:
    store.read_bytes("assignments", identifier)
    return load_assignment(store.path("assignments", identifier), layout)
