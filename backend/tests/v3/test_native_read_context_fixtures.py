"""Portable existing whole-HU hand evidence; registration is explicitly analytical."""

from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3 import api_coordinator_readers, api_coordinator_worker
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile
from app.v3.coordinator_run_inputs import HandCoordinatorInputs
from app.v3.coordinator_transport import write_coordinator_run
from app.v3.interface import Json
from tests.v3.test_api_coordinator_fixtures import _result
from tests.v3.test_coordinator_seek_fixtures import fresh_run


@dataclass(frozen=True)
class NativeCase:
    root: Path
    store: ArtifactStore
    inputs: HandCoordinatorInputs
    run: Json
    frozen: FrozenCoordinatorProfile
    identifier: str


@pytest.fixture(scope="module")
def native_case(tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeCase]:
    root = tmp_path_factory.mktemp("native-read-context")
    inputs, run, _ = fresh_run("whole")
    write_coordinator_run(run, root / "run", inputs=inputs.frozen_bytes)
    choices = canonical_bytes({"scope": "analytical test only"})
    request = canonical_bytes({k: run[k] for k in ("input_hash", "registry_common_hash")})
    snapshot = {
        "input_hash": inputs.input_hash,
        "registry_common_hash": inputs.registry_common_hash,
        "profile_sha256": sha256(choices).hexdigest(),
        "request_sha256": sha256(request).hexdigest(),
        "frozen_inputs": inputs.input_hash,
    }
    (root / "profile.json").write_bytes(choices)
    (root / "request.json").write_bytes(request)
    _result(root, run, snapshot)
    store = ArtifactStore(root / "store")
    frozen = FrozenCoordinatorProfile("b" * 64, dict(snapshot))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(api_coordinator_worker, "verified_registration", lambda *args: snapshot)
        patch.setattr(api_coordinator_readers, "verified_registration", lambda *args: snapshot)
        # Keep the closed outer-evidence root separate from its public store.
        artifact = tmp_path_factory.mktemp("native-read-context-artifact")
        for path in root.rglob("*"):
            if path.is_file() and store.root not in path.parents:
                target = artifact / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        response = api_coordinator_worker.publish_output(store, frozen, artifact)
        yield NativeCase(root, store, inputs, run, frozen, str(response["run_id"]))


def forbid_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.v3.coordinator_engine import CoordinatorEngine
    from app.v3.light_flow_engine import LightFlowEngine
    from app.v3.receipt_flow_engine import ReceiptFlowEngine
    from app.v3.whole_flow_engine import WholeFlowEngine

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("A native evidence read must not construct or run an engine")

    for engine in (CoordinatorEngine, LightFlowEngine, ReceiptFlowEngine, WholeFlowEngine):
        monkeypatch.setattr(engine, "__init__", forbidden)
        monkeypatch.setattr(engine, "run", forbidden)
