"""Strict content-addressed whole registration and native/outer file inventories."""

from typing import Annotated, Literal

from pydantic import Field

from app.api.models import ArtifactId
from app.contracts.base import FrozenModel


class WholeSourceFile(FrozenModel):
    path: Annotated[str, Field(min_length=1)]
    sha256: ArtifactId


class WholeFile(WholeSourceFile):
    bytes: Annotated[int, Field(gt=0)]


class WholeRegistration(FrozenModel):
    domain: Literal["qoima-v3-whole-api-1"]
    profile: Literal["explicit-standard-receipt-whole-v1"]
    engine_version: str
    compiler_version: str
    export_version: str
    request_version: str
    profile_sha256: ArtifactId
    request_sha256: ArtifactId
    frozen_inputs: ArtifactId
    input_hash: ArtifactId
    physical_input_hash: ArtifactId
    files: tuple[WholeSourceFile, ...]
    conveyor_files: tuple[WholeSourceFile, ...]


class WholeIndex(FrozenModel):
    domain: Literal["qoima-v3-whole-api-1"]
    run_id: ArtifactId
    native_run_id: ArtifactId
    input_bundle_id: ArtifactId
    input_hash: ArtifactId
    physical_input_hash: ArtifactId
    request_sha256: ArtifactId
    files: tuple[WholeFile, ...]
    request_files: tuple[WholeFile, ...]
