from __future__ import annotations

import json
import os
from typing import cast

import httpx
import pytest

from app.explanations import (
    ExplanationError,
    MercurySettings,
    explain_comparison,
    extract_comparison_facts,
)


def test_metric_allowlist_preserves_undefined(comparison: dict[str, object]) -> None:
    side = cast(dict[str, object], comparison["baseline"])
    side["metrics"] = {
        "at_horizon": {
            "arrived_total": 5,
            "dispatched_total": 3,
            "backlog": 2,
            "completion_rate": 0.6,
            "cycle": {"mean_s": None, "p95_s": None},
            "private": "PRIVATE",
            "queue_mean": {"private": "PRIVATE"},
        }
    }
    facts = extract_comparison_facts(comparison)
    values = {fact.fact_id: fact.value for fact in facts.items}
    assert values["baseline.metrics.at_horizon.dispatched_total"] == 3
    assert values["baseline.metrics.at_horizon.cycle.mean_s"] is None
    assert "PRIVATE" not in facts.model_dump_json()


def test_no_credential_echo_in_success(comparison: dict[str, object]) -> None:
    content = json.dumps({"observations": [{"text": "test-secret", "fact_ids": ["swaps"]}]})
    envelope = {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))
        ) as c,
        pytest.raises(ExplanationError, match="invalid_response"),
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key="test-secret"),
            client=c,
        )


def test_backend_env_only_mock_values(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = {"INCEPTION_API_KEY": "test-value", "MERCURY_MODEL": "mercury-2.5"}
    monkeypatch.setattr(os, "environ", environment)
    assert MercurySettings.from_env().model == "mercury-2.5"
    environment["MERCURY_TIMEOUT_S"] = "test-value"
    with pytest.raises(ValueError) as caught:
        MercurySettings.from_env()
    assert "test-value" not in str(caught.value)


@pytest.mark.parametrize(
    "message",
    [
        {"content": ""},
        {"content": "not-json"},
        {"content": '{"observations":[],"observations":[]}'},
        {"content": "{}", "tool_calls": [{"function": {"name": "arbitrary"}}]},
    ],
)
def test_content_failures(comparison: dict[str, object], message: object) -> None:
    envelope = {"choices": [{"finish_reason": "stop", "message": message}]}
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))
        ) as c,
        pytest.raises(ExplanationError, match="invalid_response") as caught,
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key="test-value"),
            client=c,
        )
    assert caught.value.__context__ is None


def test_transport_error(comparison: dict[str, object]) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("test-value", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(ExplanationError, match="transport") as caught,
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key="test-value"),
            client=client,
        )
    assert caught.value.__context__ is None
