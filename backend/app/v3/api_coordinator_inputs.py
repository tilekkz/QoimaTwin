"""One server-owned namespace3 source profile; raw evidence precedes every execution."""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.contracts.base import FrozenModel
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json, sha256_hex
from app.v3.api_manual_inputs import confined
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_cli_evidence import REQUEST_VERSION, freeze_request
from app.v3.coordinator_models import COORDINATOR_VERSION
from app.v3.coordinator_profile import (
    COMPILER_VERSION,
    CompiledCoordinatorProfile,
    compile_coordinator_profile,
)
from app.v3.coordinator_run_schema import PUBLICATION_VERSION
from app.v3.input_json import verified_package
from app.v3.input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION, SOURCE_REVISION
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json

DOMAIN = "qoima-v3-coordinator-api-1"
PROFILE = "explicit-two-cart-six-station-source-proposal"
EXPORT_VERSION = PUBLICATION_VERSION


class CoordinatorRequest(FrozenModel):
    profile: Literal["explicit-two-cart-six-station-source-proposal"]
    layout_version: str
    source_revision: str


@dataclass(frozen=True)
class FrozenCoordinatorProfile:
    bundle_id: str
    metadata: Json

    def key(self) -> str:
        return sha256_hex(
            {
                "domain": DOMAIN,
                "bundle": self.bundle_id,
                "input_hash": self.metadata["input_hash"],
                "request_sha256": self.metadata["request_sha256"],
                "engine": COORDINATOR_VERSION,
                "compiler": COMPILER_VERSION,
                "export": EXPORT_VERSION,
            }
        )


def freeze_profile(store: ArtifactStore, source: Path) -> FrozenCoordinatorProfile:
    bundle = load_v3_bundle(source)
    conveyor = load_conveyor_source(bundle)
    root = Path(__file__).resolve().parents[2]
    document = parse_json(
        (root / "docs/proposals/adaptive-v3/coordinator-profile.example.json").read_bytes()
    )
    compiled = compile_coordinator_profile(bundle, conveyor, document)
    if compiled.profile.profile_id != PROFILE:
        raise InvalidInputError("registered coordinator source profile identity mismatch")
    inventory, _ = verified_package(source)
    snapshot = _freeze_evidence(store, compiled, conveyor)
    snapshot.update(
        _versions(),
        input_hash=compiled.input_hash,
        registry_common_hash=compiled.registry_common_hash,
        files=_files(store, source, ("provenance.json", *(row.path for row in inventory))),
        conveyor_files=_files(
            store,
            root / "data/v3-conveyor-proposal",
            ("provenance.json", "conveyor-v3.json"),
        ),
    )
    return FrozenCoordinatorProfile(
        store.put_json("bundles", snapshot), _metadata(snapshot, compiled)
    )


def _freeze_evidence(
    store: ArtifactStore,
    compiled: CompiledCoordinatorProfile,
    conveyor: ConveyorSource,
) -> Json:
    with tempfile.TemporaryDirectory(prefix="qoima-coordinator-registration-") as temporary:
        root = Path(temporary)
        request_hash = freeze_request(compiled, conveyor, root)
        result = {
            key: store.put_bytes("run_files", (root / name).read_bytes())
            for key, name in (
                ("profile_sha256", "profile.json"),
                ("request_sha256", "request.json"),
                ("frozen_inputs", "run/inputs.json"),
            )
        }
    if result["request_sha256"] != request_hash:
        raise InvalidInputError("registered coordinator request hash mismatch")
    return result


def _versions() -> Json:
    return {
        "domain": DOMAIN,
        "profile": PROFILE,
        "engine_version": COORDINATOR_VERSION,
        "compiler_version": COMPILER_VERSION,
        "export_version": EXPORT_VERSION,
        "request_version": REQUEST_VERSION,
    }


def _metadata(snapshot: Json, compiled: CompiledCoordinatorProfile) -> Json:
    profile, flow = compiled.profile, compiled.profile.world.receipts.flow
    resources = profile.unit_resources
    metadata = {
        k: v for k, v in snapshot.items() if k not in {"files", "conveyor_files", "frozen_inputs"}
    }
    metadata.update(
        layout_version=LAYOUT_VERSION,
        source_revision=SOURCE_REVISION,
        layout_content_hash=LAYOUT_CONTENT_HASH,
        horizon_tick=compiled.horizon_tick,
        end_tick=compiled.end_tick,
        baseline_hus=len(flow.stock.containers),
        baseline_units=len(flow.stock.units),
        actor_ids_preserved=len(flow.actors),
        unit_job_count=len(flow.orders),
        whole_job_count=len(profile.world.orders),
        receipt_count=len(profile.world.receipts.receipts),
        station_count=len(resources.stations) if resources else 0,
        cart_count=len(resources.carts) if resources else 0,
        role_intent_count=len(profile.intents),
        operational_admission=False,
        full_v3=False,
        frontend_adapter=False,
        hand_contact_proof=False,
        arbitrary_seek=False,
        interpolation=False,
        contract_status="proposal",
        registry_hash_is_physical_common_identity=False,
        synthetic_choices=parse_json(compiled.frozen_bytes)["choices"],
    )
    return metadata


def _files(store: ArtifactStore, root: Path, names: tuple[str, ...]) -> list[Json]:
    return [
        {"path": name, "sha256": store.put_bytes("run_files", (root / name).read_bytes())}
        for name in names
    ]


def restore_inputs(store: ArtifactStore, identifier: str, root: Path) -> tuple[Path, Json]:
    snapshot = store.read_json("bundles", identifier)
    if any(snapshot.get(k) != v for k, v in _versions().items()):
        raise InvalidInputError("registered coordinator version mismatch")
    for row in snapshot["files"]:
        path = confined(root, row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.read_bytes("run_files", row["sha256"]))
    conveyor_root = Path(__file__).resolve().parents[2] / "data/v3-conveyor-proposal"
    for row in snapshot["conveyor_files"]:
        if confined(conveyor_root, row["path"]).read_bytes() != store.read_bytes(
            "run_files",
            row["sha256"],
        ):
            raise InvalidInputError("registered coordinator conveyor changed")
    for key in ("frozen_inputs", "request_sha256"):
        store.read_bytes("run_files", snapshot[key])
    profile = root / "profile.json"
    profile.write_bytes(store.read_bytes("run_files", snapshot["profile_sha256"]))
    return profile, snapshot
