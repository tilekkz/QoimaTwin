"""Short HTTP orchestration with explicit source, bridge and native-reader doubles."""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.api.context import ApiContext
from app.contracts.loader import ContractBundle
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3 import api_forecast_relocation_inputs as inputs
from app.v3 import api_forecast_relocation_validation as validation
from app.v3 import api_forecast_relocation_worker as worker
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile
from app.v3.forecast_relocation_cli import _manifest
from app.v3.forecast_relocation_models import ForecastRelocationChoices, ForecastRelocationInputs
from app.v3.input_pin import LAYOUT_VERSION, SOURCE_REVISION
from app.v3.offer_planning_cli_storage import descriptor, put
from app.v3.relocation_models import RELOCATION_VERSION
from app.v3.relocation_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION
from tests.v3.test_api_offer_planning import ApiCase, api_case, body

__all__ = ["api_case"]


@pytest.fixture(autouse=True)
def no_legacy_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def create(cls: type[ApiContext], store: ArtifactStore, directory: Path) -> ApiContext:
        bundle = cast(
            ContractBundle,
            SimpleNamespace(
                directory=tmp_path,
                layout=SimpleNamespace(layout_version="explicit-unrelated-contract-double"),
            ),
        )
        return ApiContext(store, bundle, "9" * 64, "8" * 64)

    monkeypatch.setattr(ApiContext, "create", classmethod(create))


def declaration(offer: str, profile: str) -> dict[str, Any]:
    return dict(
        schema_version=inputs.DOMAIN,
        offer_request_id=offer,
        actual_profile_id=profile,
        job_id="actual-relocation-1",
        arrival_tick=3,
        layout_version=LAYOUT_VERSION,
        source_revision=SOURCE_REVISION,
        acknowledge_bounded_manual=True,
    )


def bound(
    decision: bytes, common: bytes, choices: ForecastRelocationChoices
) -> ForecastRelocationInputs:
    profile = SimpleNamespace(jobs=(), coordinator=object())
    left = SimpleNamespace(frozen_bytes=b'{"arm":"baseline"}', profile=profile)
    right = SimpleNamespace(frozen_bytes=b'{"arm":"candidate"}', profile=profile)
    pair = SimpleNamespace(
        baseline=left, candidate=right, frozen_bytes=b'{"pair":1}', input_hash="a" * 64
    )
    raw = canonical_bytes(
        dict(
            decision=decision.decode(),
            common=common.decode(),
            job=choices.job_id,
            arrival=choices.arrival_tick,
        )
    )
    return cast(
        ForecastRelocationInputs,
        SimpleNamespace(
            frozen_bytes=raw,
            input_hash=sha256_hex(parse_json(raw)),
            pair=pair,
            decision=SimpleNamespace(input_hash="b" * 64, no_op=True),
        ),
    )


def comparison(value: ForecastRelocationInputs) -> dict[str, Any]:
    return dict(
        comparison_id="c" * 64,
        pair_input_hash=value.pair.input_hash,
        status="partial",
        no_op=True,
        full_n1_acceptance=False,
        baseline={"status": "partial"},
        candidate={"status": "partial"},
    )


def output(value: ForecastRelocationInputs, root: Path) -> dict[str, Any]:
    root.mkdir(exist_ok=False)
    put(root, "inputs.json", value.frozen_bytes)
    put(root, "pair/inputs.json", value.pair.frozen_bytes)
    for arm in ("baseline", "candidate"):
        native = root / "pair" / arm
        arm_inputs = getattr(value.pair, arm).frozen_bytes
        refs = {
            name: put(native, name, raw)
            for name, raw in (
                ("inputs.json", arm_inputs),
                ("catalog.json", b"{}"),
                ("snapshots/0.json", b"{}"),
            )
        }
        manifest = dict(
            transport_version=TRANSPORT_VERSION,
            schema_version=PUBLICATION_VERSION,
            engine_version=RELOCATION_VERSION,
            run_id="d" * 64,
            input_hash="e" * 64,
            common_input_hash="f" * 64,
            registry_common_hash="1" * 64,
            inputs=refs["inputs.json"],
            catalog=refs["catalog.json"],
            event_chunks=[],
            snapshot_chunks=[
                dict(
                    refs["snapshots/0.json"],
                    tick=0,
                    last_seq=-1,
                    roles=["checkpoint", "at_horizon", "at_end"],
                )
            ],
        )
        put(native, "manifest.json", canonical_bytes(manifest))
    report = comparison(value)
    report_ref = put(root, "pair/comparison.json", canonical_bytes(report))
    result = _manifest(
        value, "partial", [descriptor("inputs.json", value.frozen_bytes), report_ref]
    )
    put(root, "manifest.json", canonical_bytes(result))
    return result


@dataclass
class Case:
    api: ApiCase
    offer: str
    profile: str
    compiled: list[Path]
    prepared: list[tuple[bytes, bytes, ForecastRelocationChoices]]
    executed: list[Path]
    read: list[Path]


@pytest.fixture
def case(api_case: ApiCase, monkeypatch: pytest.MonkeyPatch) -> Case:
    compiled: list[Path] = []
    prepared: list[tuple[bytes, bytes, ForecastRelocationChoices]] = []
    executed: list[Path] = []
    reads: list[Path] = []
    common = api_case.store.put_bytes("run_files", b'{"actual_common":"hand","H":1000}')
    registration = api_case.store.put_json("bundles", {"frozen_inputs": common})

    def compile_profile(store: ArtifactStore, source: Path) -> FrozenCoordinatorProfile:
        compiled.append(source)
        return FrozenCoordinatorProfile(
            registration, {"horizon_tick": 1000, "end_tick": 2000, "operational_admission": False}
        )

    def prepare(
        raw: bytes, actual: bytes, choices: ForecastRelocationChoices
    ) -> ForecastRelocationInputs:
        prepared.append((raw, actual, choices))
        return bound(raw, actual, choices)

    def execute(value: ForecastRelocationInputs, root: Path) -> dict[str, Any]:
        assert (root.parent / "decision.json").read_bytes() == prepared[-1][0]
        assert (root.parent / "common-inputs.json").read_bytes() == prepared[-1][1]
        executed.append(root)
        return output(value, root)

    monkeypatch.setattr(worker, "freeze_profile", compile_profile)
    monkeypatch.setattr(
        inputs, "registration", lambda store, identifier: store.read_json("bundles", identifier)
    )
    monkeypatch.setattr(worker, "prepare_forecast_relocation", prepare)
    monkeypatch.setattr(worker, "compare_forecast_relocation", execute)
    _native_doubles(monkeypatch, reads, prepared)
    planned = api_case.client.post("/api/v3/offer-plans", json=body()).json()
    response = api_case.client.get("/api/v3/forecast-relocation-profiles")
    assert response.status_code == 200
    return Case(
        api_case,
        planned["request_id"],
        response.json()["profiles"][0]["actual_profile_id"],
        compiled,
        prepared,
        executed,
        reads,
    )


def _native_doubles(
    monkeypatch: pytest.MonkeyPatch,
    reads: list[Path],
    prepared: list[tuple[bytes, bytes, ForecastRelocationChoices]],
) -> None:
    def read_native(root: Path) -> dict[str, Any]:
        reads.append(root)
        return {"outcome": {"kind": "hand"}, "run_id": "d" * 64}

    monkeypatch.setattr(validation, "read_relocation_run", read_native)
    monkeypatch.setattr(validation, "restore_base", lambda profile, value: object())
    monkeypatch.setattr(validation, "restore_relocation", lambda profile, value: object())
    monkeypatch.setattr(
        validation, "build_pair_report", lambda pair, *args: comparison(prepared_value(prepared))
    )


def prepared_value(
    rows: list[tuple[bytes, bytes, ForecastRelocationChoices]],
) -> ForecastRelocationInputs:
    return bound(*rows[-1])


def submit(case: Case) -> Any:
    return case.api.client.post(
        "/api/v3/forecast-relocation-runs", json=declaration(case.offer, case.profile)
    )


def test_registered_profile_and_partial_pair_use_one_producer(case: Case) -> None:
    first = submit(case)
    assert first.status_code == 200
    result = first.json()
    assert result["calculation_status"] == "completed" and result["comparison_status"] == "partial"
    assert result["no_op"] is True and result["full_n1_acceptance"] is False
    assert result["comparison"]["candidate"]["status"] == "partial"
    assert case.prepared[-1][2] == ForecastRelocationChoices("actual-relocation-1", 3)
    assert submit(case).json() == result
    assert len(case.executed) == 1 and len(case.compiled) >= 3
    url = "/api/v3/forecast-relocation-runs/" + result["run_id"]
    assert case.api.client.get(url + "/result").json() == result
    row = next(row for row in result["files"] if row["path"] == "inputs.json")
    file = case.api.client.get(url + "/files/" + row["sha256"])
    assert file.content == case.api.store.read_bytes("run_files", row["sha256"])
    assert len(case.executed) == 1 and len(case.read) == 8


@pytest.mark.parametrize(
    "change",
    [
        {"arrival_tick": True},
        {"arrival_tick": -1},
        {"job_id": ""},
        {"actual_profile_id": "path"},
        {"acknowledge_bounded_manual": False},
        {"source_revision": "other"},
        {"unknown": 1},
    ],
)
def test_structural_bad_requests_never_execute(case: Case, change: dict[str, Any]) -> None:
    value = declaration(case.offer, case.profile) | change
    assert case.api.client.post("/api/v3/forecast-relocation-runs", json=value).status_code == 422
    assert not case.executed and not case.prepared


def test_horizon_binding_error_is_preserved_before_executor(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject(*args: Any) -> Any:
        raise ValueError("planning H1000 differs from actual H900")

    monkeypatch.setattr(worker, "prepare_forecast_relocation", reject)
    assert submit(case).status_code == 422
    assert not case.executed
    attempts = list(case.api.store.root.glob("forecast-relocation-v3-evidence/attempt-*"))
    assert len(attempts) == 1
    assert (attempts[0] / "common-inputs.json").exists() and (attempts[0] / "failure.json").exists()


def test_rehashed_other_profile_fails_current_recipe_reconstruction(case: Case) -> None:
    profile = case.api.store.read_json("bundles", case.profile)
    profile["metadata"]["horizon_tick"] = 900
    other = case.api.store.put_json("bundles", profile)
    value = declaration(case.offer, other)
    assert case.api.client.post("/api/v3/forecast-relocation-runs", json=value).status_code == 500
    assert not case.executed


def test_native_read_failure_blocks_cached_post_and_get(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = submit(case).json()

    def reject(root: Path) -> Any:
        raise ValueError("native causal authority changed")

    monkeypatch.setattr(validation, "read_relocation_run", reject)
    assert submit(case).status_code == 500
    assert (
        case.api.client.get(
            "/api/v3/forecast-relocation-runs/" + result["run_id"] + "/result"
        ).status_code
        == 500
    )
    assert len(case.executed) == 1


def test_recovery_never_repeats_completed_producer(case: Case) -> None:
    result = submit(case).json()
    case.api.store.path("requests", result["run_id"]).unlink()
    assert submit(case).json() == result
    assert len(case.executed) == 1


def test_unknown_and_nonmember_reads_are_rejected(case: Case) -> None:
    assert (
        case.api.client.get("/api/v3/forecast-relocation-runs/" + "f" * 64 + "/result").status_code
        == 404
    )
    result = submit(case).json()
    url = "/api/v3/forecast-relocation-runs/" + result["run_id"] + "/files/" + "f" * 64
    assert case.api.client.get(url).status_code == 404


def test_profile_registration_is_a_worker_read(case: Case) -> None:
    jobs = case.api.processor.calls
    assert [j.kind for j in jobs] == ["offer-planning-v3", "forecast-relocation-profile-v3"]
    assert not list(case.api.store.root.glob("forecast-relocation-v3-evidence/*"))
