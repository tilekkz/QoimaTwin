"""Raw, normalized and complete source-bound identities remain distinct."""

from typing import Any

from app.storage.canonical_json import sha256_hex
from app.v3.offer_history_choices import choices_record
from app.v3.offer_history_models import HISTORY_VERSION, MAX_COUNT, OfferHistoryInputs
from app.v3.workload_wire import source_dict


def normalized_hash(value: OfferHistoryInputs) -> str:
    policy = choices_record(value.choices)
    del policy["provenance"]
    return sha256_hex(
        {
            "version": HISTORY_VERSION,
            "measure": policy,
            "source_revision": value.source.source_revision,
            "templates": source_dict(value.source)["templates"],
            "sku_ids": value.sku_ids,
            "counts": value.counts,
            "windows_utc": value.windows_utc,
        }
    )


def history_record(value: OfferHistoryInputs) -> dict[str, Any]:
    return {
        "version": HISTORY_VERSION,
        "choices": choices_record(value.choices),
        "source": source_dict(value.source),
        "raw_history_utf8": value.raw_history.decode("utf-8"),
        "raw_history_sha256": value.raw_history_sha256,
        "normalized_history_hash": value.normalized_history_hash,
        "sku_ids": value.sku_ids,
        "counts": value.counts,
        "windows_utc": value.windows_utc,
        "maximum_exact_count": MAX_COUNT,
        "operational_admission": False,
    }
