"""Server-registered canonical choices and verified source evidence; no request paths."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.api.context import Json
from app.contracts.base import FrozenModel
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.api_manual_inputs import confined
from app.v3.conveyor_source import load_conveyor_source
from app.v3.flow_profile import COMPILER_VERSION, CompiledLightProfile, compile_light_profile
from app.v3.flow_profile_wire import normalized_choices
from app.v3.input_json import verified_package
from app.v3.input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION, SOURCE_REVISION
from app.v3.inputs import load_v3_bundle
from app.v3.light_flow_models import LIGHT_FLOW_ENGINE_VERSION

DOMAIN = "qoima-v3-light-api-1"
PROFILE = "explicit-source-small-three-units-v1"
EXPORT_VERSION = "qoima.connected-small-run.v3-proposal/0.1.0"


class LightRequest(FrozenModel):
    profile: Literal["explicit-source-small-three-units-v1"]
    layout_version: str
    source_revision: str


@dataclass(frozen=True)
class FrozenLightProfile:
    bundle_id: str
    metadata: Json

    def key(self) -> str:
        return sha256_hex(
            {
                "domain": DOMAIN,
                "bundle": self.bundle_id,
                "input_hash": self.metadata["input_hash"],
                "engine": LIGHT_FLOW_ENGINE_VERSION,
                "compiler": COMPILER_VERSION,
                "export": EXPORT_VERSION,
            }
        )


def freeze_profile(store: ArtifactStore, source: Path) -> FrozenLightProfile:
    bundle = load_v3_bundle(source)
    conveyor = load_conveyor_source(bundle)
    root = Path(__file__).resolve().parents[2]
    path = root / "docs/proposals/adaptive-v3/light-flow-profile.example.json"
    document = parse_json(path.read_bytes())
    compiled = compile_light_profile(bundle, conveyor, document)
    if compiled.profile.profile_id != PROFILE:
        raise InvalidInputError("registered connected profile identity mismatch")
    choices = normalized_choices(document)
    inventory, _ = verified_package(source)
    snapshot: Json = {
        "domain": DOMAIN,
        "profile": PROFILE,
        "engine_version": LIGHT_FLOW_ENGINE_VERSION,
        "compiler_version": COMPILER_VERSION,
        "export_version": EXPORT_VERSION,
        "input_hash": compiled.input_hash,
        "frozen_inputs": store.put_bytes("run_files", compiled.frozen_bytes),
        "profile_sha256": store.put_bytes("run_files", canonical_bytes(choices)),
        "files": _files(store, source, ("provenance.json", *(r.path for r in inventory))),
        "conveyor_files": _files(
            store, root / "data/v3-conveyor-proposal", ("provenance.json", "conveyor-v3.json")
        ),
    }
    return FrozenLightProfile(
        store.put_json("bundles", snapshot), _metadata(snapshot, compiled, choices)
    )


def _metadata(snapshot: Json, compiled: CompiledLightProfile, choices: Json) -> Json:
    metadata: Json = {
        k: snapshot[k]
        for k in (
            "profile",
            "input_hash",
            "profile_sha256",
            "engine_version",
            "compiler_version",
            "export_version",
        )
    }
    metadata.update(
        layout_version=LAYOUT_VERSION,
        source_revision=SOURCE_REVISION,
        layout_content_hash=LAYOUT_CONTENT_HASH,
        baseline_hus=len(compiled.profile.stock.containers),
        actor_ids_preserved=len(compiled.profile.actors),
        job_count=len(compiled.profile.orders),
        operational_admission=False,
        full_v3=False,
        frontend_adapter=False,
        hand_contact_proof=False,
        arbitrary_seek=False,
        interpolation=False,
        contract_status="proposal",
        synthetic_choices=choices,
    )
    return metadata


def _files(store: ArtifactStore, root: Path, names: tuple[str, ...]) -> list[Json]:
    return [
        {"path": name, "sha256": store.put_bytes("run_files", (root / name).read_bytes())}
        for name in names
    ]


def restore_inputs(store: ArtifactStore, identifier: str, root: Path) -> tuple[Path, Json]:
    snapshot = store.read_json("bundles", identifier)
    expected = {
        "domain": DOMAIN,
        "profile": PROFILE,
        "engine_version": LIGHT_FLOW_ENGINE_VERSION,
        "compiler_version": COMPILER_VERSION,
        "export_version": EXPORT_VERSION,
    }
    if any(snapshot.get(k) != v for k, v in expected.items()):
        raise InvalidInputError("connected frozen registration version mismatch")
    for row in snapshot["files"]:
        path = confined(root, row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.read_bytes("run_files", row["sha256"]))
    for row in snapshot["conveyor_files"]:
        raw = store.read_bytes("run_files", row["sha256"])
        actual = confined(
            Path(__file__).resolve().parents[2] / "data/v3-conveyor-proposal", row["path"]
        )
        if actual.read_bytes() != raw:
            raise InvalidInputError("registered conveyor source has changed")
    store.read_bytes("run_files", snapshot["frozen_inputs"])
    profile = root / "profile.json"
    profile.write_bytes(store.read_bytes("run_files", snapshot["profile_sha256"]))
    return profile, snapshot
