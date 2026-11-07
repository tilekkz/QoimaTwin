"""Forecast and relocation-plan semantics in RunInputs and run identity (ADR 0008, 0016).

Expected hashes are recomputed from the semantic JSON with the canonical hasher, never copied
from engine output. The forecast dict mimics ForecastSnapshot.semantic_dict() of the forecast
worker (protocol qoima-forecast-temporal-1, per full 8 h day).
"""

from __future__ import annotations

import dataclasses
import pickle
from pathlib import Path
from typing import Any

import pytest

from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.planning import plan_swaps
from app.simulation.context import InputError, RunInputs, SemanticJson
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import sha256_hex
from tests.planning_support import forecast_semantics, two_sku_inputs


@pytest.fixture(scope="module")
def base(bundle: ContractBundle, contracts_dir: Path) -> RunInputs:
    return fixture_inputs(bundle, load_fixture(contracts_dir))


def test_omitted_semantics_hash_as_none(base: RunInputs) -> None:
    hashes = fingerprint(base)["hashes"]
    assert base.forecast_snapshot is None and base.relocation_plan is None
    assert hashes["forecast_snapshot"] == sha256_hex(None)
    assert hashes["relocation_plan"] == sha256_hex(None)


def test_six_positional_arguments_still_work(base: RunInputs) -> None:
    again = RunInputs(
        base.layout, base.config, base.actors, base.assignment, base.scenario, "fixture"
    )
    assert fingerprint(again) == fingerprint(base)


def test_forecast_hash_is_the_semantic_content_hash(base: RunInputs) -> None:
    semantics = forecast_semantics()
    inputs = dataclasses.replace(base, forecast_snapshot=semantics)
    assert fingerprint(inputs)["hashes"]["forecast_snapshot"] == sha256_hex(semantics)
    frozen = inputs.forecast_json()
    assert frozen is not None
    assert frozen.sha256 == sha256_hex(semantics)
    assert frozen.to_dict() == semantics


def test_forecast_hash_is_key_order_independent(base: RunInputs) -> None:
    semantics = forecast_semantics()
    reordered = dict(reversed(list(semantics.items())))
    first = dataclasses.replace(base, forecast_snapshot=semantics)
    second = dataclasses.replace(base, forecast_snapshot=reordered)
    assert fingerprint(first) == fingerprint(second)


@pytest.mark.parametrize(
    "changed", [forecast_semantics(visits_y=11.0), forecast_semantics(model="hgb")]
)
def test_semantic_forecast_change_changes_identity(
    base: RunInputs, changed: dict[str, Any]
) -> None:
    first = dataclasses.replace(base, forecast_snapshot=forecast_semantics())
    second = dataclasses.replace(base, forecast_snapshot=changed)
    assert (
        fingerprint(first)["hashes"]["forecast_snapshot"]
        != (fingerprint(second)["hashes"]["forecast_snapshot"])
    )


@pytest.mark.parametrize("key", ["cpu_time_s", "final_fit_cpu_time_s", "semantic_id"])
def test_runtime_or_declared_forecast_fields_are_rejected(base: RunInputs, key: str) -> None:
    semantics = {**forecast_semantics(), key: 0.5 if "cpu" in key else "f" * 64}
    with pytest.raises(InputError, match=key):
        dataclasses.replace(base, forecast_snapshot=semantics)


def test_caller_mutation_after_replace_cannot_change_identity(base: RunInputs) -> None:
    semantics = forecast_semantics()
    inputs = dataclasses.replace(base, forecast_snapshot=semantics)
    before = fingerprint(inputs)
    semantics["model"] = "hgb"
    predictions = semantics["predictions"]["visits_by_sku"]
    predictions["SKU_Y"] = 99.0
    assert fingerprint(inputs) == before
    frozen = inputs.forecast_json()
    copy = frozen.to_dict() if frozen else {}
    copy["model"] = "edited"
    assert fingerprint(inputs) == before


def test_non_json_semantics_are_rejected(base: RunInputs) -> None:
    with pytest.raises(InputError):
        dataclasses.replace(base, forecast_snapshot={"protocol": float("nan")})
    with pytest.raises(InputError):
        dataclasses.replace(base, forecast_snapshot={"protocol": object()})
    with pytest.raises(InputError):
        dataclasses.replace(base, relocation_plan=["not", "an", "object"])  # type: ignore[arg-type]


def test_relocation_plan_hash_is_the_verified_plan_id(
    base: RunInputs, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    data = plan.model_dump(mode="json")
    inputs = dataclasses.replace(base, relocation_plan=data)
    assert fingerprint(inputs)["hashes"]["relocation_plan"] == plan.plan_id
    reordered = dataclasses.replace(base, relocation_plan=dict(reversed(list(data.items()))))
    assert fingerprint(reordered) == fingerprint(inputs)
    with pytest.raises(InputError, match="plan_id"):
        dataclasses.replace(base, relocation_plan={**data, "plan_id": "0" * 64})
    with pytest.raises(InputError, match="plan_id"):
        dataclasses.replace(base, relocation_plan={**data, "forecast_id": "edited"})


def test_semantics_survive_replace_and_pickle(base: RunInputs) -> None:
    inputs = dataclasses.replace(base, forecast_snapshot=forecast_semantics())
    again = dataclasses.replace(inputs, experiment_type="slotting")
    assert again.forecast_snapshot == inputs.forecast_snapshot
    restored = pickle.loads(pickle.dumps(inputs))
    assert fingerprint(restored) == fingerprint(inputs)


def test_hand_built_semantic_json_with_false_hash_is_rejected(base: RunInputs) -> None:
    good = dataclasses.replace(base, forecast_snapshot=forecast_semantics()).forecast_json()
    assert good is not None
    forged = SemanticJson(good.canonical, "0" * 64)
    with pytest.raises(InputError, match="content"):
        dataclasses.replace(base, forecast_snapshot=forged)
