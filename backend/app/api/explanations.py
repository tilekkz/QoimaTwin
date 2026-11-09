"""Optional paid explanation request: server facts, off-loop transport, immutable cache."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from app.api.context import Json
from app.contracts.base import FrozenModel
from app.errors import AppError
from app.explanations import (
    ComparisonFacts,
    ExplanationError,
    MercurySettings,
    explain_comparison,
    explanation_cache_key,
    extract_comparison_facts,
)
from app.settings import repository_root
from app.storage.artifacts import ArtifactStore


class ExplanationRequest(FrozenModel):
    pass


class ExplanationApiError(AppError):
    def __init__(self, code: str) -> None:
        self.code = f"explanation_{code}"
        self.http_status = {
            "invalid_facts": 422,
            "unavailable": 503,
            "timeout": 504,
            "rate_limited": 429,
        }.get(code, 502)
        super().__init__(f"Mercury explanation {code}")


class ExplanationService:
    def __init__(self, store: ArtifactStore, settings: MercurySettings | None) -> None:
        self.store, self.settings = store, settings
        self.active: dict[str, asyncio.Task[Json]] = {}

    async def submit(self, comparison_id: str) -> Json:
        envelope = self.store.read_json("comparisons", comparison_id)
        scenario = self.store.read_json("scenarios", envelope["scenario_id"])
        try:
            facts = extract_comparison_facts(
                envelope["comparison"], provenance=scenario["provenance"]["kind"]
            )
            settings = self.settings or MercurySettings.from_env(
                env_file=repository_root() / "backend" / ".env"
            )
            key = explanation_cache_key(comparison_id, facts, settings=settings)
        except ExplanationError as exc:
            raise ExplanationApiError(exc.code) from None
        except ValueError:
            raise ExplanationApiError("unavailable") from None
        cached = self.store.read_reference("explanations", key)
        if cached is not None:
            return dict(cached)
        if key not in self.active:
            self.active[key] = asyncio.create_task(
                asyncio.to_thread(self._execute, comparison_id, facts, settings, key)
            )
            self.active[key].add_done_callback(lambda task: self._completed(key, task))
        return await asyncio.shield(self.active[key])

    def _completed(self, key: str, task: asyncio.Task[Json]) -> None:
        self.active.pop(key, None)
        if not task.cancelled():
            task.exception()  # Consume an error even if the HTTP waiter disconnected.

    def _execute(
        self, comparison_id: str, facts: ComparisonFacts, settings: MercurySettings, key: str
    ) -> Json:
        try:
            result = explain_comparison(comparison_id, facts, settings=settings)
        except ExplanationError as exc:
            raise ExplanationApiError(exc.code) from None
        except Exception:
            raise ExplanationApiError("provider_unavailable") from None
        payload = result.model_dump(mode="json")
        self.store.publish_reference("explanations", key, payload)
        return payload

    async def finish(self) -> None:
        await asyncio.gather(*self.active.values(), return_exceptions=True)


def attach_explanation_route(app: FastAPI, service: ExplanationService) -> None:
    @app.post("/api/compares/{comparison_id}/explanation")
    async def explanation(comparison_id: str, body: ExplanationRequest) -> Json:
        return await service.submit(comparison_id)
