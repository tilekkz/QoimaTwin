"""Lazy immutable registration uses the same source proof in routes and worker restoration."""

import asyncio
from pathlib import Path

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json
from app.v3.api_whole_binding import _validated_registration, verified_registration
from app.v3.api_whole_inputs import FrozenWholeProfile, freeze_profile


def load_registered(store: ArtifactStore, identifier: str) -> FrozenWholeProfile:
    frozen = FrozenWholeProfile(
        identifier, parse_json(_validated_registration(str(store.root), identifier))
    )
    verified_registration(store, frozen)
    return frozen


class WholeRegistry:
    def __init__(self, store: ArtifactStore, source: Path) -> None:
        self.store, self.source = store, source
        self.lock = asyncio.Lock()
        self.frozen: FrozenWholeProfile | None = None

    async def get(self) -> FrozenWholeProfile:
        async with self.lock:
            if self.frozen is None:
                self.frozen = await asyncio.to_thread(freeze_profile, self.store, self.source)
            return self.frozen
