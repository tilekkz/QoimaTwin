from __future__ import annotations

import json

import httpx
import pytest

import app.explanations.prompt as prompt_module
from app.explanations import (
    ExplanationError,
    MercurySettings,
    explain_comparison,
    explanation_cache_key,
    extract_comparison_facts,
)


def test_owned_client_is_closed_without_environment_proxy(
    comparison: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_client = httpx.Client
    clients: list[httpx.Client] = []
    content = json.dumps({"observations": [{"text": "Consider review.", "fact_ids": ["swaps"]}]})
    envelope = {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}

    def factory(*, trust_env: bool) -> httpx.Client:
        assert trust_env is False
        client = real_client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope)),
            trust_env=False,
        )
        clients.append(client)
        return client

    monkeypatch.setattr(httpx, "Client", factory)
    explain_comparison(
        "id", extract_comparison_facts(comparison), settings=MercurySettings(api_key="test-value")
    )
    assert len(clients) == 1
    assert clients[0].is_closed


def test_redirect_never_followed(comparison: dict[str, object]) -> None:
    calls: list[str] = []

    def redirect(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://example.invalid/steal"})

    with (
        httpx.Client(transport=httpx.MockTransport(redirect), follow_redirects=True) as client,
        pytest.raises(ExplanationError, match="provider_rejected"),
    ):
        explain_comparison(
            "id",
            extract_comparison_facts(comparison),
            settings=MercurySettings(api_key="test-value"),
            client=client,
        )
    assert calls == ["https://api.inceptionlabs.ai/v1/chat/completions"]


def test_cache_version_and_ignored_source_timing(
    comparison: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = MercurySettings()
    facts = extract_comparison_facts(comparison)
    key = explanation_cache_key("id", facts, settings=settings)
    comparison["elapsed_ms"] = 999
    assert key == explanation_cache_key(
        "id", extract_comparison_facts(comparison), settings=settings
    )
    monkeypatch.setattr(prompt_module, "PROMPT_VERSION", "next-test-version")
    assert key != explanation_cache_key("id", facts, settings=settings)
