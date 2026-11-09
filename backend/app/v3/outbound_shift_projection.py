"""Pure field projection; source authentication belongs to outbound_shift_source."""

from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.workload_source import _indexed


def project_rows(
    before: object,
    after: object,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Keep every C10 field except each SKU's explicitly selected C11 outbound mix."""
    baseline, shifted = _indexed(before, "sku_id"), _indexed(after, "sku_id")
    if baseline.keys() != shifted.keys():
        raise ValueError("Outbound shift must retain the exact baseline SKU identities")
    projected, excluded = [], []
    for sku, row in sorted(baseline.items()):
        change = shifted[sku]
        if row["archetype_id"] != change["archetype_id"]:
            raise ValueError("Outbound shift SKU archetype differs from C10")
        mix = change.get("outbound_port_mix")
        if type(mix) is not dict:
            raise ValueError("Outbound shift requires an explicit C11 port mix")
        projected.append({**row, "outbound_port_mix": dict(mix)})
        if canonical_bytes(row["inbound_port_mix"]) != canonical_bytes(change["inbound_port_mix"]):
            excluded.append(sku)
    return projected, tuple(excluded)
