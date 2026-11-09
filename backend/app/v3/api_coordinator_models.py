"""Strict content-addressed coordinator registration and native/outer file inventories."""

from typing import Annotated, Literal

from pydantic import Field

from app.api.models import ArtifactId
from app.contracts.base import FrozenModel


class CoordinatorSourceFile(FrozenModel):
    path: Annotated[str, Field(min_length=1)]
    sha256: ArtifactId


class CoordinatorFile(CoordinatorSourceFile):
    bytes: Annotated[int, Field(gt=0)]


class CoordinatorRegistration(FrozenModel):
    domain: Literal["qoima-v3-coordinator-api-1"]
    profile: Literal["explicit-two-cart-six-station-source-proposal"]
    engine_version: str
    compiler_version: str
    export_version: str
    request_version: str
    profile_sha256: ArtifactId
    request_sha256: ArtifactId
    frozen_inputs: ArtifactId
    input_hash: ArtifactId
    registry_common_hash: ArtifactId
    files: tuple[CoordinatorSourceFile, ...]
    conveyor_files: tuple[CoordinatorSourceFile, ...]


class CoordinatorIndex(FrozenModel):
    domain: Literal["qoima-v3-coordinator-api-1"]
    run_id: ArtifactId
    native_run_id: ArtifactId
    input_bundle_id: ArtifactId
    input_hash: ArtifactId
    registry_common_hash: ArtifactId
    request_sha256: ArtifactId
    files: tuple[CoordinatorFile, ...]
    request_files: tuple[CoordinatorFile, ...]
