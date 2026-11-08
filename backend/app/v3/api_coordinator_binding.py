"""Rehash server evidence before using cached immutable source-registration metadata."""

import tempfile
from functools import lru_cache
from pathlib import Path

from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_coordinator_inputs import (
    FrozenCoordinatorProfile,
    _metadata,
    _versions,
    restore_inputs,
)
from app.v3.api_coordinator_models import CoordinatorRegistration
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_cli_evidence import freeze_request
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.input_json import verified_package
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json


def registration(store: ArtifactStore, identifier: str) -> Json:
    try:
        value = CoordinatorRegistration.from_data(
            store.read_json("bundles", identifier)
        ).model_dump(
            mode="json",
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("coordinator registration is unavailable or invalid") from exc
    if any(value[k] != v for k, v in _versions().items()):
        raise ArtifactCorruption("coordinator registration versions differ")
    for key in ("files", "conveyor_files"):
        if len({row["path"] for row in value[key]}) != len(value[key]):
            raise ArtifactCorruption("duplicate coordinator registration source path")
    keys = [value[k] for k in ("profile_sha256", "request_sha256", "frozen_inputs")]
    keys.extend(row["sha256"] for row in (*value["files"], *value["conveyor_files"]))
    try:
        for key in set(keys):
            store.read_bytes("run_files", key)
    except InvalidInputError as exc:
        raise ArtifactCorruption("coordinator registration dependency is unavailable") from exc
    return dict(value)


def verified_registration(store: ArtifactStore, frozen: FrozenCoordinatorProfile) -> Json:
    if type(frozen) is not FrozenCoordinatorProfile or type(frozen.bundle_id) is not str:
        raise ArtifactCorruption("exact coordinator registration identity required")
    snapshot = registration(store, frozen.bundle_id)
    expected = _validated_registration(str(store.root), frozen.bundle_id)
    if type(frozen.metadata) is not dict or canonical_bytes(frozen.metadata) != expected:
        raise ArtifactCorruption("coordinator metadata differs from verified registration")
    return snapshot


@lru_cache(maxsize=8)
def _validated_registration(store_root: str, identifier: str) -> bytes:
    store = ArtifactStore(Path(store_root))
    snapshot = registration(store, identifier)
    try:
        with tempfile.TemporaryDirectory(
            prefix="qoima-coordinator-registration-read-"
        ) as temporary:
            root = Path(temporary)
            path, _ = restore_inputs(store, identifier, root / "source")
            _source_names(snapshot, root / "source")
            bundle = load_v3_bundle(root / "source")
            conveyor = load_conveyor_source(bundle)
            compiled = compile_coordinator_profile(bundle, conveyor, parse_json(path.read_bytes()))
            freeze_request(compiled, conveyor, root / "expected")
            _compare_evidence(store, snapshot, root / "expected")
            if (compiled.input_hash, compiled.registry_common_hash) != (
                snapshot["input_hash"],
                snapshot["registry_common_hash"],
            ):
                raise ValueError("coordinator registered input identity differs")
            return canonical_bytes(_metadata(snapshot, compiled))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("coordinator source registration validation failed") from exc


def _compare_evidence(store: ArtifactStore, snapshot: Json, expected: Path) -> None:
    for key, relative in (
        ("profile_sha256", "profile.json"),
        ("request_sha256", "request.json"),
        ("frozen_inputs", "run/inputs.json"),
    ):
        if (expected / relative).read_bytes() != store.read_bytes("run_files", snapshot[key]):
            raise ValueError("coordinator registered choices/request/inputs differ")


def _source_names(snapshot: Json, source: Path) -> None:
    inventory, _ = verified_package(source)
    if {row["path"] for row in snapshot["files"]} != {
        "provenance.json",
        *(row.path for row in inventory),
    }:
        raise ValueError("coordinator registered source inventory differs")
    if {row["path"] for row in snapshot["conveyor_files"]} != {
        "provenance.json",
        "conveyor-v3.json",
    }:
        raise ValueError("coordinator registered conveyor inventory differs")
