"""Internal hand registration probes reader binding; it is not a source HTTP profile."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.api.context import Json
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.api_receipt_inputs import FrozenReceiptProfile
from app.v3.api_receipt_worker import publish_output
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_transport import write_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


@cache
def partial_native() -> tuple[bytes, Json]:
    inputs, outcome = sample(24_000_000, 28_000_000)
    return inputs.frozen_bytes, build_receipt_run(inputs, outcome)


@dataclass(frozen=True)
class HandRegistration:
    store: ArtifactStore
    frozen: FrozenReceiptProfile
    response: Json
    evidence_hash: str


def registered_hand(root: Path) -> HandRegistration:
    inputs, run = partial_native()
    store = ArtifactStore(root / "store")
    evidence = store.put_json("run_files", {"scope": "internal_hand_reader_test_only"})
    snapshot = {
        "scope": "internal_hand_reader_test_only",
        "input_hash": run["input_hash"],
        "frozen_inputs": store.put_bytes("run_files", inputs),
        "profile_sha256": store.put_json("run_files", parse_json(inputs)["choices"]),
        "files": [{"path": "hand-evidence.json", "sha256": evidence}],
        "conveyor_files": [],
    }
    bundle = store.put_json("bundles", snapshot)
    frozen = FrozenReceiptProfile(bundle, {"input_hash": run["input_hash"]})
    output = root / "native"
    write_receipt_run(run, output, inputs=inputs)
    response = publish_output(store, bundle, output, snapshot)
    return HandRegistration(store, frozen, response, evidence)


def replace_run_index(store: ArtifactStore, identifier: str, value: Json) -> None:
    store.path("runs", identifier).write_bytes(
        canonical_bytes({"content_sha256": sha256_hex(value), "value": value})
    )
