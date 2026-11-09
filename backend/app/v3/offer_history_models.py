"""Declared synthetic offered-HU history; no stock, receipt or runtime grant."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.v3.workload_models import WorkloadSource

HISTORY_VERSION = "qoima-v3-offered-hu-history-0.1.0"
TARGET_UNIT = "outbound_whole_hu_offers"
MAX_COUNT = 2**53


@dataclass(frozen=True, slots=True)
class OfferProvenance:
    kind: str
    dataset_id: str
    generator_id: str
    generator_version: str
    seed: int | None


@dataclass(frozen=True, slots=True)
class OfferHistoryChoices:
    target_unit: str
    test_day: date
    timezone_name: str
    window_start_second: int
    window_end_second: int
    provenance: OfferProvenance


@dataclass(frozen=True, slots=True)
class OfferHistoryInputs:
    source: WorkloadSource
    choices: OfferHistoryChoices
    raw_history: bytes
    sku_ids: tuple[str, ...]
    counts: tuple[tuple[int, ...], ...]
    windows_utc: tuple[tuple[str, str, str], ...]
    raw_history_sha256: str
    normalized_history_hash: str
    frozen_bytes: bytes
    input_hash: str

    @property
    def operational_admission(self) -> Literal[False]:
        return False
