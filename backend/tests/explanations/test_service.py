from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import cast

import httpx
import pytest

from app.explanations import (
    ExplanationError,
    MercurySettings,
    explain_comparison,
    explanation_cache_key,
    extract_comparison_facts,
)

KEY = "test-only-credential"
CONTENT = {"observations": [{"text": "Consider reviewing labor.", "fact_ids": ["swaps"]}]}


@pytest.mark.parametrize("both_partial", [False, True])
def test_partial_request_and_advisory(comparison: dict[str, object], both_partial: bool) -> None:
    outcome = cast(dict[str, object], cast(dict[str, object], comparison["candidate"])["outcome"])
    outcome.update(status="partial", termination="deadlock")
    cast(dict[str, object], comparison["candidate"])["metrics"] = {
        "at_end": {"arrived_total": 5, "dispatched_total": 5}
    }
    if both_partial:
        baseline = cast(dict[str, object], comparison["baseline"])
        cast(dict[str, object], baseline["outcome"]).update(
            status="partial", termination="max_drain"
        )
    facts = extract_comparison_facts(comparison, provenance="synthetic")

    def handle(request: httpx.Request) -> httpx.Response:
        messages = json.loads(request.content)["messages"]
        prompt = messages[0]["content"]
        assert "separate from" in prompt
        assert "partial" in prompt
        assert "order counts" in prompt
        values = {
            fact["fact_id"]: fact["value"] for fact in json.loads(messages[1]["content"])["items"]
        }
        assert values["candidate.outcome.status"] == "partial"
        assert values["candidate.outcome.termination"] == "deadlock"
        assert values["candidate.metrics.at_end.arrived_total"] == 5
        assert values["candidate.metrics.at_end.dispatched_total"] == 5
        return response()

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = explain_comparison(
            "id", facts, settings=MercurySettings(api_key=KEY), client=client
        )
    assert result.facts == facts
    assert "candidate outcome is partial" in result.advisory
    assert "order counts" in result.advisory
    assert ("baseline outcome is partial" in result.advisory) == both_partial


def response(content: object = CONTENT) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
        },
    )


@pytest.mark.parametrize("key", [None, "", "  "])
def test_unavailable_without_key(comparison: dict[str, object], key: str | None) -> None:
    facts = extract_comparison_facts(comparison, provenance="synthetic")
    with pytest.raises(ExplanationError, match="unavailable") as caught:
        explain_comparison("artifact-id", facts, settings=MercurySettings(api_key=key))
    assert caught.value.code == "unavailable"


def test_success_request_and_immutability(comparison: dict[str, object]) -> None:
    before = copy.deepcopy(comparison)
    facts = extract_comparison_facts(comparison, provenance="synthetic")
    settings = MercurySettings(api_key=KEY, max_completion_tokens=300, timeout_s=2)

    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.inceptionlabs.ai/v1/chat/completions"
        assert request.method == "POST"
        assert request.headers["authorization"] == f"Bearer {KEY}"
        data = json.loads(request.content)
        assert set(data) == {
            "model",
            "messages",
            "max_completion_tokens",
            "reasoning_effort",
            "response_format",
        }
        assert data["model"] == "mercury-3"
        assert data["max_completion_tokens"] == 300
        assert [message["role"] for message in data["messages"]] == ["system", "user"]
        assert "untrusted data" in data["messages"][0]["content"]
        assert "unsupported numeric" in data["messages"][0]["content"]
        assert "guarantee" in data["messages"][0]["content"]
        assert "PRIVATE" not in request.content.decode()
        assert "synthetic" in request.content.decode()
        assert "at_horizon" in request.content.decode()
        assert request.extensions["timeout"]["read"] == 2
        return response()

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = explain_comparison("artifact-id", facts, settings=settings, client=client)
    assert result.ai_generated is True
    assert result.facts == facts
    assert result.comparison_id == "artifact-id"
    assert result.observations[0].fact_ids == ("swaps",)
    assert comparison == before
    assert KEY not in repr(settings)
    assert KEY not in result.model_dump_json()


@pytest.mark.parametrize(
    "content",
    [
        {},
        {"observations": []},
        {"observations": [{"text": "", "fact_ids": ["swaps"]}]},
        {"observations": [{"text": "Bad", "fact_ids": ["invented"]}]},
        {"observations": [{"text": "Bad", "fact_ids": []}]},
        {"observations": [{"text": "Bad", "fact_ids": ["swaps"], "tools": []}]},
    ],
)
def test_reject_structured_output(comparison: dict[str, object], content: object) -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response(content))) as client,
        pytest.raises(ExplanationError, match="invalid_response"),
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key=KEY),
            client=client,
        )


@pytest.mark.parametrize("body", [b"", b"not-json", b"{}", b'{"choices": []}'])
def test_invalid_envelope(comparison: dict[str, object], body: bytes) -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
        ) as c,
        pytest.raises(ExplanationError, match="invalid_response"),
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key=KEY),
            client=c,
        )


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (429, "rate_limited"),
        (500, "provider_unavailable"),
        (503, "provider_unavailable"),
        (400, "provider_rejected"),
        (302, "provider_rejected"),
    ],
)
def test_sanitized_http_errors(comparison: dict[str, object], status: int, code: str) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text=f"RAW-SECRET {KEY}"))
    with httpx.Client(transport=transport) as client, pytest.raises(ExplanationError) as caught:
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key=KEY),
            client=client,
        )
    assert caught.value.code == code
    assert KEY not in str(caught.value)
    assert "RAW-SECRET" not in repr(caught.value)
    assert caught.value.__cause__ is None


def test_timeout_sanitized(comparison: dict[str, object]) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(KEY, request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(ExplanationError, match="timeout") as caught,
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key=KEY),
            client=client,
        )
    assert caught.value.__cause__ is None
    assert KEY not in str(caught.value)


def test_cache_identity(comparison: dict[str, object]) -> None:
    facts = extract_comparison_facts(comparison)
    settings = MercurySettings(api_key=KEY)
    key = explanation_cache_key("id", facts, settings=settings)
    assert key == explanation_cache_key(
        "id",
        facts,
        settings=replace(settings, api_key="other", timeout_s=1, max_completion_tokens=100),
    )
    assert key != explanation_cache_key("other", facts, settings=settings)
    assert key != explanation_cache_key(
        "id", facts, settings=replace(settings, model="mercury-2.5")
    )
    changed = facts.model_copy(update={"provenance": "synthetic"})
    assert key != explanation_cache_key("id", changed, settings=settings)
    assert len(key) == 64


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_s": 0},
        {"timeout_s": 31},
        {"max_completion_tokens": 0},
        {"max_completion_tokens": 4097},
        {"model": ""},
        {"model": "bad\nmodel"},
    ],
)
def test_settings_bounded(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        MercurySettings(**kwargs)  # type: ignore[arg-type]
