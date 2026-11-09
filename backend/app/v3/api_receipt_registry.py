"""One immutable lazy registration avoids source compilation on unrelated API routes."""

import asyncio
from pathlib import Path

from app.storage.artifacts import ArtifactStore
from app.v3.api_receipt_inputs import FrozenReceiptProfile, freeze_profile


class ReceiptRegistry:
    def __init__(self, store: ArtifactStore, source: Path) -> None:
        self.store, self.source = store, source
        self.lock = asyncio.Lock()
        self.frozen: FrozenReceiptProfile | None = None

    async def get(self) -> FrozenReceiptProfile:
        async with self.lock:
            if self.frozen is None:
                self.frozen = await asyncio.to_thread(freeze_profile, self.store, self.source)
            return self.frozen
