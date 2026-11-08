"""One server-registered whole source profile, with exact public and physical evidence."""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.contracts.base import FrozenModel
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json, sha256_hex
from app.v3.api_manual_inputs import confined
from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_json import verified_package
from app.v3.input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION, SOURCE_REVISION
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.whole_cli_evidence import REQUEST_VERSION, freeze_request
from app.v3.whole_flow_models import WHOLE_FLOW_ENGINE_VERSION
from app.v3.whole_profile_io import COMPILER_VERSION, CompiledWholeProfile, compile_whole_profile
from app.v3.whole_run_schema import PUBLICATION_VERSION

DOMAIN = "qoima-v3-whole-api-1"
PROFILE = "explicit-standard-receipt-whole-v1"
EXPORT_VERSION = PUBLICATION_VERSION


class WholeRequest(FrozenModel):
    profile: Literal["explicit-standard-receipt-whole-v1"]
    layout_version: str
    source_revision: str


@dataclass(frozen=True)
class FrozenWholeProfile:
    bundle_id: str
    metadata: Json

    def key(self) -> str:
        return sha256_hex(
            {
                "domain": DOMAIN,
                "bundle": self.bundle_id,
                "input_hash": self.metadata["input_hash"],
                "request_sha256": self.metadata["request_sha256"],
                "engine": WHOLE_FLOW_ENGINE_VERSION,
                "compiler": COMPILER_VERSION,
                "export": EXPORT_VERSION,
            }
        )


def freeze_profile(store: ArtifactStore, source: Path) -> FrozenWholeProfile:
    bundle = load_v3_bundle(source)
    conveyor = load_conveyor_source(bundle)
    root = Path(__file__).resolve().parents[2]
    document = parse_json(
        (root / "docs/proposals/adaptive-v3/whole-flow-profile.example.json").read_bytes()
    )
    compiled = compile_whole_profile(bundle, conveyor, document)
    if compiled.run_inputs.profile.receipts.flow.profile_id != PROFILE:
        raise InvalidInputError("registered whole profile identity mismatch")
    inventory, _ = verified_package(source)
    snapshot = _freeze_evidence(store, compiled)
    snapshot.update(
        _versions(),
        input_hash=compiled.run_inputs.input_hash,
        physical_input_hash=compiled.run_inputs.physical_input_hash,
        files=_files(store, source, ("provenance.json", *(row.path for row in inventory))),
        conveyor_files=_files(
            store, root / "data/v3-conveyor-proposal", ("provenance.json", "conveyor-v3.json")
        ),
    )
    return FrozenWholeProfile(store.put_json("bundles", snapshot), _metadata(snapshot, compiled))


def _freeze_evidence(store: ArtifactStore, compiled: CompiledWholeProfile) -> Json:
    with tempfile.TemporaryDirectory(prefix="qoima-whole-registration-") as temporary:
        root = Path(temporary)
        request_hash = freeze_request(compiled, root)
        result = {
            key: store.put_bytes("run_files", (root / name).read_bytes())
            for key, name in (
                ("profile_sha256", "profile.json"),
                ("request_sha256", "request.json"),
                ("frozen_inputs", "run/inputs.json"),
            )
        }
    if result["request_sha256"] != request_hash:
        raise InvalidInputError("registered whole request hash mismatch")
    return result


def _versions() -> Json:
    return {
        "domain": DOMAIN,
        "profile": PROFILE,
        "engine_version": WHOLE_FLOW_ENGINE_VERSION,
        "compiler_version": COMPILER_VERSION,
        "export_version": EXPORT_VERSION,
        "request_version": REQUEST_VERSION,
    }


def _metadata(snapshot: Json, compiled: CompiledWholeProfile) -> Json:
    inputs, profile = compiled.run_inputs, compiled.run_inputs.profile
    flow = profile.receipts.flow
    metadata = {
        k: v for k, v in snapshot.items() if k not in {"files", "conveyor_files", "frozen_inputs"}
    }
    metadata.update(
        layout_version=LAYOUT_VERSION,
        source_revision=SOURCE_REVISION,
        layout_content_hash=LAYOUT_CONTENT_HASH,
        horizon_tick=inputs.horizon_tick,
        end_tick=inputs.end_tick,
        baseline_hus=len(flow.stock.containers),
        baseline_units=len(flow.stock.units),
        actor_ids_preserved=len(flow.actors),
        unit_job_count=len(flow.orders),
        whole_job_count=len(profile.orders),
        receipt_count=len(profile.receipts.receipts),
        receipt_units=sum(r.definition.quantity_units for r in profile.receipts.receipts),
        operational_admission=False,
        full_v3=False,
        frontend_adapter=False,
        hand_contact_proof=False,
        arbitrary_seek=False,
        interpolation=False,
        contract_status="proposal",
        synthetic_choices=parse_json(compiled.choices_bytes),
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
        raise InvalidInputError("registered whole version mismatch")
    for row in snapshot["files"]:
        path = confined(root, row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.read_bytes("run_files", row["sha256"]))
    conveyor_root = Path(__file__).resolve().parents[2] / "data/v3-conveyor-proposal"
    for row in snapshot["conveyor_files"]:
        if confined(conveyor_root, row["path"]).read_bytes() != store.read_bytes(
            "run_files", row["sha256"]
        ):
            raise InvalidInputError("registered whole conveyor changed")
    for key in ("frozen_inputs", "request_sha256"):
        store.read_bytes("run_files", snapshot[key])
    profile = root / "profile.json"
    profile.write_bytes(store.read_bytes("run_files", snapshot["profile_sha256"]))
    return profile, snapshot
