"""Runtime settings resolved from the environment."""

from __future__ import annotations

import os
from pathlib import Path

CONTRACTS_DIR_ENV = "QOIMA_CONTRACTS_DIR"


def repository_root() -> Path:
    """Return the repository root (the directory that contains `backend/`)."""
    return Path(__file__).resolve().parents[2]


def default_contracts_dir() -> Path:
    """Return the contracts directory; `QOIMA_CONTRACTS_DIR` overrides the repository default."""
    override = os.environ.get(CONTRACTS_DIR_ENV)
    if override:
        return Path(override).resolve()
    return repository_root() / "contracts"
