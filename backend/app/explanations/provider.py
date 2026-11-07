"""Fixed official HTTPS transport and strict cited response validation."""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.explanations.errors import ExplanationError
from app.explanations.models import ComparisonFacts, GeneratedObservations
from app.explanations.prompt import SYSTEM_PROMPT
from app.explanations.settings import ENDPOINT, MercurySettings
from app.storage.canonical_json import parse_json


def _response_format(facts: ComparisonFacts) -> dict[str, Any]:
    known = sorted({fact.fact_id for fact in facts.items})
    if not known:
        raise ExplanationError("invalid_facts")
    schema = GeneratedObservations.model_json_schema()
    # Inline the only local reference, retaining every model bound and closed object.
    observation = schema.pop("$defs")["Observation"]
    observation["properties"]["fact_ids"]["items"]["enum"] = known
    schema["properties"]["observations"]["items"] = observation
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "qoima_comparison_observations",
            "strict": True,
            "schema": schema,
        },
    }


def _decode(
    response: httpx.Response, facts: ComparisonFacts, api_key: str | None
) -> GeneratedObservations:
    try:
        envelope = parse_json(response.content)
        choice = envelope["choices"][0]
        if choice.get("finish_reason") != "stop" or choice["message"].get("tool_calls"):
            raise ValueError("incomplete or tool response")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty content")
        if api_key and api_key in content:
            raise ValueError("credential echo")
        # Strict JSON tuple fields are accepted from JSON arrays by Pydantic.
        parse_json(content)
        result = GeneratedObservations.model_validate_json(content)
        known = {fact.fact_id for fact in facts.items}
        if any(set(item.fact_ids) - known for item in result.observations):
            raise ValueError("unknown citation")
        if any(not item.text.strip() for item in result.observations):
            raise ValueError("empty observation")
        return result
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ValidationError):
        pass
    raise ExplanationError("invalid_response")


def request_observations(
    client: httpx.Client, facts: ComparisonFacts, settings: MercurySettings
) -> GeneratedObservations:
    payload = {
        "model": settings.model,
        "max_completion_tokens": settings.max_completion_tokens,
        "reasoning_effort": "instant",
        "response_format": _response_format(facts),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(facts.model_dump(mode="json"))},
        ],
    }
    error = "transport"
    try:
        response = client.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=settings.timeout_s,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        error = "timeout"
    except httpx.HTTPError:
        pass
    else:
        if response.status_code == 200:
            return _decode(response, facts, settings.api_key)
        errors = {401: "authentication", 403: "authentication", 429: "rate_limited"}
        error = errors.get(response.status_code, "provider_rejected")
        if response.status_code >= 500:
            error = "provider_unavailable"
    raise ExplanationError(error)
