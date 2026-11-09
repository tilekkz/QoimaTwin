"""The bounded Mercury request explicitly asks for immediate, cited structured output."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator, ValidationError

import app.explanations.prompt as prompt_module
from app.explanations import (
    ExplanationError,
    MercurySettings,
    explain_comparison,
    explanation_cache_key,
    extract_comparison_facts,
)
from app.explanations.models import ComparisonFacts, ExplanationResult, Fact

CONTENT = {"observations": [{"text": "Consider review.", "fact_ids": ["swaps"]}]}


def _request(facts: ComparisonFacts) -> tuple[dict[str, Any], ExplanationResult]:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(CONTENT)}}]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = explain_comparison(
            "id", facts, settings=MercurySettings(api_key="test-only-value"), client=client
        )
    assert len(requests) == 1
    return requests[0], result


def test_request_uses_instant_strict_schema_and_default_budget(
    comparison: dict[str, object],
) -> None:
    facts = extract_comparison_facts(comparison)
    payload, result = _request(facts)
    assert payload["reasoning_effort"] == "instant"
    assert payload["max_completion_tokens"] == 1024
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    descriptor = response_format["json_schema"]
    assert descriptor["name"] == "qoima_comparison_observations"
    assert descriptor["strict"] is True
    schema = descriptor["schema"]
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(CONTENT)
    observation = schema["properties"]["observations"]["items"]
    assert observation["properties"]["fact_ids"]["items"]["enum"] == sorted(
        {fact.fact_id for fact in facts.items}
    )
    assert "$ref" not in json.dumps(schema)
    assert "$defs" not in schema
    assert result.observations[0].text == "Consider review."
    assert result.observations[0].fact_ids == ("swaps",)
    assert result.prompt_version == "qoima-mercury-explanations-v3"


@pytest.mark.parametrize(
    "invalid",
    [
        {"observations": [{"text": "Review", "fact_ids": ["unknown"]}]},
        {"observations": [{"text": "Review", "fact_ids": ["swaps"], "extra": True}]},
        {**CONTENT, "extra": True},
        {"observations": []},
        {"observations": CONTENT["observations"] * 9},
        {"observations": [{"text": "", "fact_ids": ["swaps"]}]},
        {"observations": [{"text": "x" * 1501, "fact_ids": ["swaps"]}]},
        {"observations": [{"text": "Review", "fact_ids": []}]},
        {"observations": [{"text": "Review", "fact_ids": ["swaps"] * 17}]},
    ],
)
def test_provider_schema_retains_local_response_bounds(invalid: object) -> None:
    facts = ComparisonFacts(items=(Fact(fact_id="swaps", value=1),))
    payload, _ = _request(facts)
    schema = payload["response_format"]["json_schema"]["schema"]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(invalid)


def test_fact_enum_is_fresh_per_request() -> None:
    first = ComparisonFacts(items=(Fact(fact_id="swaps", value=1),))
    second = ComparisonFacts(items=(*first.items, Fact(fact_id="another.known", value=2)))
    one, _ = _request(first)
    two, _ = _request(second)
    one_schema = one["response_format"]["json_schema"]["schema"]
    two_schema = two["response_format"]["json_schema"]["schema"]
    changed = {"observations": [{"text": "Review", "fact_ids": ["another.known"]}]}
    Draft202012Validator(two_schema).validate(changed)
    with pytest.raises(ValidationError):
        Draft202012Validator(one_schema).validate(changed)


def test_empty_facts_are_rejected_before_provider_request() -> None:
    calls = 0

    def respond(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ExplanationError, match="invalid_facts"),
    ):
        explain_comparison(
            "id", ComparisonFacts(items=()), settings=MercurySettings(api_key="test"), client=client
        )
    assert calls == 0


@pytest.mark.parametrize("content", [None, json.dumps(CONTENT)])
def test_length_completion_stays_sanitized_and_is_not_retried(content: str | None) -> None:
    calls = 0

    def respond(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": content}}]}
        )

    facts = ComparisonFacts(items=(Fact(fact_id="swaps", value=1),))
    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ExplanationError, match="invalid_response") as caught,
    ):
        explain_comparison(
            "id", facts, settings=MercurySettings(api_key="test-only-value"), client=client
        )
    assert calls == 1
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_protocol_v3_invalidates_v2_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    facts = ComparisonFacts(items=(Fact(fact_id="swaps", value=1),))
    settings = MercurySettings()
    assert prompt_module.PROMPT_VERSION == "qoima-mercury-explanations-v3"
    current = explanation_cache_key("id", facts, settings=settings)
    monkeypatch.setattr(prompt_module, "PROMPT_VERSION", "qoima-mercury-explanations-v2")
    assert current != explanation_cache_key("id", facts, settings=settings)
