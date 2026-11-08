"""Lazy immutable registration uses the same source proof in routes and worker restoration."""

import asyncio
from pathlib import Path

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json
from app.v3.api_coordinator_binding import _validated_registration, verified_registration
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile, freeze_profile


def load_registered(store: ArtifactStore, identifier: str) -> FrozenCoordinatorProfile:
    frozen = FrozenCoordinatorProfile(
        identifier, parse_json(_validated_registration(str(store.root), identifier))
    )
    verified_registration(store, frozen)
    return frozen


class CoordinatorRegistry:
    def __init__(self, store: ArtifactStore, source: Path) -> None:
        self.store, self.source = store, source
        self.lock = asyncio.Lock()
        self.frozen: FrozenCoordinatorProfile | None = None

    async def get(self) -> FrozenCoordinatorProfile:
        async with self.lock:
            if self.frozen is None:
                self.frozen = await asyncio.to_thread(freeze_profile, self.store, self.source)
            return self.frozen
