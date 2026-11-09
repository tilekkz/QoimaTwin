"""Freeze server-registered bytes; public callers choose a name, never a local path."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from app.contracts.base import FrozenModel
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json, sha256_hex
from app.v3.execution_types import MANUAL_ENGINE_VERSION
from app.v3.input_json import verified_package
from app.v3.input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION, SOURCE_REVISION
from app.v3.profile_models import ManualProposal

DOMAIN = "qoima-v3-manual-api-1"
EXPORT_VERSION = "qoima.manual-run.v3-proposal/0.1.0/transport-0.1.0"
PROFILE = "manual-whole-hu-demo-v1"
Json = dict[str, Any]


class ManualRequest(FrozenModel):
    profile: Literal["manual-whole-hu-demo-v1"]
    layout_version: str
    source_revision: str


@dataclass(frozen=True)
class FrozenProfile:
    bundle_id: str
    metadata: Json

    def key(self) -> str:
        return sha256_hex(
            {
                "domain": DOMAIN,
                "bundle_id": self.bundle_id,
                "profile_sha256": self.metadata["profile_sha256"],
                "layout_content_hash": self.metadata["layout_content_hash"],
                "engine": MANUAL_ENGINE_VERSION,
                "export": EXPORT_VERSION,
            }
        )


def freeze_profile(store: ArtifactStore, source: Path) -> FrozenProfile:
    inventory, _ = verified_package(source)
    files = []
    for name in ("provenance.json", *(row.path for row in inventory)):
        raw = (source / name).read_bytes()
        files.append({"path": name, "sha256": store.put_bytes("run_files", raw)})
    proposal_path = Path(__file__).resolve().parents[2] / "data/v3-execution-proposals"
    raw = (proposal_path / f"{PROFILE}.json").read_bytes()
    proposal = ManualProposal.model_validate(parse_json(raw))
    proposal_id = store.put_bytes("run_files", raw)
    snapshot = {
        "domain": DOMAIN,
        "files": files,
        "proposal_sha256": proposal_id,
        "profile_sha256": sha256_hex(proposal.model_dump(mode="json")),
    }
    return FrozenProfile(store.put_json("bundles", snapshot), _metadata(proposal))


def _metadata(proposal: ManualProposal) -> Json:
    return {
        "profile": PROFILE,
        "layout_version": LAYOUT_VERSION,
        "source_revision": SOURCE_REVISION,
        "layout_content_hash": LAYOUT_CONTENT_HASH,
        "profile_sha256": sha256_hex(proposal.model_dump(mode="json")),
        "engine_version": MANUAL_ENGINE_VERSION,
        "export_version": EXPORT_VERSION,
        "baseline_hus": 530,
        "sku_count": 200,
        "actor_ids_preserved": 24,
        "job_count": 4,
        "source_label": "actual_engine_run",
        "full_v3_warehouse": False,
        "frontend_adapter": False,
        "contract_status": "proposal",
        "supported_archetypes": ["SMALL_CARTON", "STANDARD_CARTON"],
        "unsupported": [
            "full warehouse",
            "all eight classes",
            "N0-N4 operations",
            "heavy handling",
            "packing",
            "conveyors",
            "Tilek V2 reader",
        ],
        "synthetic_choices": proposal.model_dump(mode="json"),
    }


def confined(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise InvalidInputError("invalid manual artifact path")
    target = (root / name).resolve()
    if target == root.resolve() or not target.is_relative_to(root.resolve()):
        raise InvalidInputError("invalid manual artifact path")
    return target


def restore_inputs(store: ArtifactStore, identifier: str, root: Path) -> Path:
    snapshot = store.read_json("bundles", identifier)
    if snapshot["domain"] != DOMAIN:
        raise InvalidInputError("invalid manual input domain")
    for row in snapshot["files"]:
        target = confined(root, row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(store.read_bytes("run_files", row["sha256"]))
    proposal = root / "proposal.json"
    proposal.write_bytes(store.read_bytes("run_files", snapshot["proposal_sha256"]))
    return proposal
