"""Explicit explanation requests read server facts and keep provider failures sanitized."""

import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.explanations import (
    PROMPT_VERSION,
    ComparisonFacts,
    ExplanationError,
    ExplanationResult,
    MercurySettings,
    Observation,
    explanation_cache_key,
    extract_comparison_facts,
)
from app.storage.artifacts import ArtifactStore
from tests.api.test_routes import FakeProcessor


def _stored_comparison(store: ArtifactStore, status: str = "complete") -> str:
    scenario_id = store.put_json("scenarios", {"provenance": {"kind": "synthetic"}})
    window = {
        "gross_labor_saved_picker_s": 0,
        "gross_labor_saved_all_roles_s": 0,
        "net_labor_saved_picker_s": 0,
        "net_labor_saved_all_roles_s": 0,
        "blocked_delta_s": 0,
        "wait_resource_delta_s": 0,
        "verdict": "unchanged",
        "baseline": {"cutoff_s": 60, "total_labor_s": 0},
        "candidate": {"cutoff_s": 60, "total_labor_s": 0},
    }
    side = {
        "outcome": {
            "status": status,
            "termination": "drained" if status == "complete" else "max_drain",
            "horizon_s": 60,
            "end_s": 60,
        }
    }
    comparison = {
        "artifact_version": "qoima-compare-v1",
        "experiment_type": "slotting",
        "relocation_labor_s": 0,
        "relocation_distance_m": 0,
        "budget_swaps": 0,
        "swaps": 0,
        "is_noop": True,
        "semantic_identical": True,
        "at_horizon": {**window, "window": "at_horizon"},
        "at_end": {**window, "window": "at_end"},
        "baseline": side,
        "candidate": side,
    }
    return store.put_json("comparisons", {"comparison": comparison, "scenario_id": scenario_id})


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("unavailable", 503),
        ("timeout", 504),
        ("authentication", 502),
        ("invalid_facts", 422),
        ("rate_limited", 429),
    ],
)
def test_explanation_provider_errors_are_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str, status: int
) -> None:
    identifier = _stored_comparison(ArtifactStore(tmp_path))

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise ExplanationError(code)

    monkeypatch.setattr("app.api.explanations.explain_comparison", fail)
    app = create_app(tmp_path, processor=FakeProcessor(), explanation_settings=MercurySettings())
    with TestClient(app) as client:
        response = client.post(f"/api/compares/{identifier}/explanation", json={})
        assert response.status_code == status
        assert response.json()["error"]["code"] == f"explanation_{code}"


def test_explanation_rejects_client_facts(tmp_path: Path) -> None:
    app = create_app(tmp_path, processor=FakeProcessor(), explanation_settings=MercurySettings())
    with TestClient(app) as client:
        response = client.post(
            f"/api/compares/{'a' * 64}/explanation",
            json={"facts": {}, "api_key": "test-private-value"},
        )
        assert response.status_code == 422
        assert "test-private-value" not in response.text


@pytest.mark.parametrize("outcome_status", ["failed", "running"])
def test_explanation_rejects_unfinished_or_failed_runs(tmp_path: Path, outcome_status: str) -> None:
    identifier = _stored_comparison(ArtifactStore(tmp_path), outcome_status)
    app = create_app(tmp_path, processor=FakeProcessor(), explanation_settings=MercurySettings())
    with TestClient(app) as client:
        response = client.post(f"/api/compares/{identifier}/explanation", json={})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "explanation_invalid_facts"


@pytest.mark.parametrize("outcome_status", ["complete", "partial"])
def test_explanation_reuses_immutable_cache_after_app_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome_status: str
) -> None:
    identifier = _stored_comparison(ArtifactStore(tmp_path), outcome_status)
    settings, provider_threads = MercurySettings(), []
    from app.api import explanations

    event_threads: list[int] = []

    def track_extract(*args: Any, **kwargs: Any) -> ComparisonFacts:
        event_threads.append(threading.get_ident())
        return extract_comparison_facts(*args, **kwargs)

    def explain(comparison_id: str, facts: ComparisonFacts, **kwargs: Any) -> ExplanationResult:
        provider_threads.append(threading.get_ident())
        return ExplanationResult(
            comparison_id=comparison_id,
            facts=facts,
            model=settings.model,
            observations=(Observation(text="No swaps were applied.", fact_ids=("swaps",)),),
            prompt_version=PROMPT_VERSION,
            cache_key=explanation_cache_key(comparison_id, facts, settings=settings),
        )

    monkeypatch.setattr(explanations, "extract_comparison_facts", track_extract)
    monkeypatch.setattr(explanations, "explain_comparison", explain)
    results = []
    for _ in range(2):
        app = create_app(tmp_path, processor=FakeProcessor(), explanation_settings=settings)
        with TestClient(app) as client:
            response = client.post(f"/api/compares/{identifier}/explanation", json={})
            assert response.status_code == 200
            results.append(response.json())
    assert results[0] == results[1]
    assert len(provider_threads) == 1
    assert provider_threads[0] != event_threads[0]
    assert results[0]["facts"]["provenance"] == "synthetic"
    facts = {row["fact_id"]: row["value"] for row in results[0]["facts"]["items"]}
    assert facts["baseline.outcome.status"] == outcome_status
