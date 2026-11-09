"""Every access rehashes evidence; cached immutable metadata never grants changed authority."""

import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_whole_inputs import FrozenWholeProfile, _metadata, _versions, restore_inputs
from app.v3.api_whole_models import WholeRegistration
from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_json import verified_package
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.whole_cli_evidence import freeze_request
from app.v3.whole_profile_io import compile_whole_profile


def registration(store: ArtifactStore, identifier: str) -> Json:
    try:
        value = WholeRegistration.from_data(store.read_json("bundles", identifier)).model_dump(
            mode="json"
        )
    except ValidationError as exc:
        raise ArtifactCorruption("invalid whole registration") from exc
    except InvalidInputError as exc:
        raise ArtifactCorruption("whole registration is unavailable") from exc
    if any(value[k] != v for k, v in _versions().items()):
        raise ArtifactCorruption("whole registration versions differ")
    for key in ("files", "conveyor_files"):
        if len({row["path"] for row in value[key]}) != len(value[key]):
            raise ArtifactCorruption("duplicate whole registration source path")
    keys = [value[k] for k in ("profile_sha256", "request_sha256", "frozen_inputs")]
    keys.extend(row["sha256"] for row in (*value["files"], *value["conveyor_files"]))
    try:
        for key in set(keys):
            store.read_bytes("run_files", key)
    except InvalidInputError as exc:
        raise ArtifactCorruption("whole registration dependency is unavailable") from exc
    return dict(value)


def verified_registration(store: ArtifactStore, frozen: FrozenWholeProfile) -> Json:
    if type(frozen) is not FrozenWholeProfile or type(frozen.bundle_id) is not str:
        raise ArtifactCorruption("exact whole registration identity required")
    snapshot = registration(store, frozen.bundle_id)
    expected = _validated_registration(str(store.root), frozen.bundle_id)
    if type(frozen.metadata) is not dict or canonical_bytes(frozen.metadata) != expected:
        raise ArtifactCorruption("whole metadata differs from its verified registration")
    return snapshot


@lru_cache(maxsize=8)
def _validated_registration(store_root: str, identifier: str) -> bytes:
    store = ArtifactStore(Path(store_root))
    snapshot = registration(store, identifier)
    try:
        with tempfile.TemporaryDirectory(prefix="qoima-whole-verify-registration-") as temporary:
            root = Path(temporary)
            path, _ = restore_inputs(store, identifier, root / "source")
            _source_names(snapshot, root / "source")
            bundle = load_v3_bundle(root / "source")
            compiled = compile_whole_profile(
                bundle, load_conveyor_source(bundle), parse_json(path.read_bytes())
            )
            freeze_request(compiled, root / "expected")
            for key, relative in (
                ("profile_sha256", "profile.json"),
                ("request_sha256", "request.json"),
                ("frozen_inputs", "run/inputs.json"),
            ):
                if (root / "expected" / relative).read_bytes() != store.read_bytes(
                    "run_files", snapshot[key]
                ):
                    raise ValueError("whole registered choices/request/inputs differ")
            inputs = compiled.run_inputs
            if (inputs.input_hash, inputs.physical_input_hash) != (
                snapshot["input_hash"],
                snapshot["physical_input_hash"],
            ):
                raise ValueError("whole registration input identity differs")
            return canonical_bytes(_metadata(snapshot, compiled))
    except ValueError as exc:
        raise ArtifactCorruption("whole source registration validation failed") from exc


def _source_names(snapshot: Json, source: Path) -> None:
    inventory, _ = verified_package(source)
    if {row["path"] for row in snapshot["files"]} != {
        "provenance.json",
        *(row.path for row in inventory),
    }:
        raise ValueError("whole registered source inventory differs")
    if {row["path"] for row in snapshot["conveyor_files"]} != {
        "provenance.json",
        "conveyor-v3.json",
    }:
        raise ValueError("whole registered conveyor inventory differs")
