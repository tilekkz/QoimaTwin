"""Stable independent stream identities (ADR 0009)."""

from __future__ import annotations

from numpy.random import PCG64, Generator, SeedSequence

MASTER_SEED = 20261107
HISTORY = 1
ORDERS = 2
RECEIPTS = 3


def stream_rng(code: int, master_seed: int = MASTER_SEED) -> Generator:
    """Create a fresh stream; no global generator state is shared."""
    return Generator(PCG64(SeedSequence([master_seed, code])))
