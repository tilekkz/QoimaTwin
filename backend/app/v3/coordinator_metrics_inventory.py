"""Current inventory from actual credited units; immutable source defines storage zones."""

from collections import Counter
from fractions import Fraction
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_metrics_observed_values import rational, unavailable
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.stock_models import UnitToken
from app.v3.stock_receipts import ReceiptDelta


def _tokens(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    tick: int,
) -> dict[str, UnitToken]:
    tokens = {u.unit_id: u for u in profile.world.receipts.flow.stock.units}
    for event in outcome.events:
        delta = event.delta
        if event.tick > tick or not isinstance(delta, ReceiptDelta):
            continue
        for token in delta.created_tokens:
            if token.unit_id in tokens:
                raise ValueError("KPI receipt token created more than once")
            tokens[token.unit_id] = token
    return tokens


def source_zones(profile: CoordinatorProfile) -> dict[str, str] | None:
    flow = profile.world.receipts.flow
    if flow.source_revision is None:
        return None
    root = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    bundle = load_v3_bundle(root)  # Reload/rehash raw source; no caller-owned mapping authority.
    hashes = dict(flow.source_hashes)
    if (
        type(flow.source_revision) is not str
        or flow.source_revision != bundle.source_revision
        or len(hashes) != len(flow.source_hashes)
        or any(hashes.get(row.path) != row.raw_sha256 for row in bundle.source_inventory)
    ):
        raise ValueError("KPI source zone binding differs from profile source identity")
    rows = bundle.documents["docs/v3/contract-proposals/storage-slots-v3.json"].decode()["slots"]
    return {row["slot_id"]: row["zone_id"] for row in rows}


def _owners(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> list[Json]:
    flow = profile.world.receipts.flow
    owners = {o.owner_id: o for o in (*flow.stock.owners, *flow.owners)}
    containers = {c.container_id: c for c in point.stock.containers}
    tokens = _tokens(profile, outcome, point.tick)
    if len(containers) != len(point.stock.containers):
        raise ValueError("KPI duplicate physical container")
    rows: dict[str, Json] = {
        key: {
            "owner_id": key,
            "kind": owner.kind,
            "containers": 0,
            "units_by_sku": Counter(),
            "gross_mass": Fraction(0),
        }
        for key, owner in owners.items()
    }
    for container in containers.values():
        if container.owner_id not in rows:
            raise ValueError("KPI container has unknown owner")
        row = rows[container.owner_id]
        row["containers"] += 1
        row["gross_mass"] += container.recipe.tare_kg
    seen: set[str] = set()
    for location in point.stock.locations:
        if (
            location.unit_id in seen
            or location.unit_id not in tokens
            or location.container_id not in containers
        ):
            raise ValueError("KPI unit identity/location differs from credited inventory")
        seen.add(location.unit_id)
        token, container = tokens[location.unit_id], containers[location.container_id]
        row = rows[container.owner_id]
        row["units_by_sku"][token.sku_id] += 1
        row["gross_mass"] += token.recipe.gross_mass_kg
    if seen != set(tokens):
        raise ValueError("KPI captured inventory loses credited units")
    return [
        {**row, "units_by_sku": dict(sorted(row["units_by_sku"].items()))}
        for _, row in sorted(rows.items())
    ]


def _quantities(rows: list[Json], point: CoordinatorSnapshot) -> Json:
    all_units: Counter[str] = Counter()
    shipped: Counter[str] = Counter()
    for row in rows:
        all_units.update(row["units_by_sku"])
        if row["kind"] == "shipped":
            shipped.update(row["units_by_sku"])
        if row["kind"] == "disposal" and row["units_by_sku"]:
            raise ValueError("KPI disposal must not contain product units")
    onsite = all_units - shipped
    expected = (
        dict(point.balance.units_by_sku),
        dict(point.balance.onsite_units_by_sku),
        dict(point.balance.shipped_units_by_sku),
    )
    if canonical_bytes((all_units, onsite, shipped)) != canonical_bytes(expected):
        raise ValueError("KPI owner SKU quantities differ from native accounting")
    return {
        "onsite_units": sum(onsite.values()),
        "shipped_units": sum(shipped.values()),
        "units_by_sku": dict(all_units),
        "onsite_units_by_sku": dict(onsite),
        "shipped_units_by_sku": dict(shipped),
    }


def _zones(rows: list[Json], mapping: dict[str, str] | None) -> Json:
    if mapping is None:
        return unavailable("Analytical profile has no authoritative source zone table")
    values: dict[str, Json] = {
        zone: {"zone_id": zone, "units": 0, "containers": 0, "gross_mass": Fraction(0)}
        for zone in set(mapping.values())
    }
    for row in rows:
        if row["kind"] != "slot":
            continue
        if row["owner_id"] not in mapping:
            raise ValueError("KPI source slot has no authoritative zone")
        value = values[mapping[row["owner_id"]]]
        value["units"] += sum(row["units_by_sku"].values())
        value["containers"] += row["containers"]
        value["gross_mass"] += row["gross_mass"]
    return {
        "available": True,
        "scope": "source_storage_slots_only; non-slot custody is in owners",
        "rows": [
            {
                "zone_id": row["zone_id"],
                "units": row["units"],
                "containers": row["containers"],
                "gross_mass_kg": rational(row["gross_mass"]),
            }
            for _, row in sorted(values.items())
        ],
    }


def inventory(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> Json:
    rows = _owners(profile, outcome, point)
    mass = {
        kind: sum((r["gross_mass"] for r in rows if r["kind"] == kind), Fraction(0))
        for kind in {r["kind"] for r in rows}
    }
    total = sum(mass.values(), Fraction(0))
    shipped, disposed = mass.get("shipped", Fraction(0)), mass.get("disposal", Fraction(0))
    if (
        total != point.balance.gross_mass_kg
        or shipped != point.balance.shipped_mass_kg
        or disposed != point.balance.disposed_mass_kg
    ):
        raise ValueError("KPI owner masses differ from native accounting")
    return {
        "gross_mass_kg": rational(total),
        "onsite_mass_kg": rational(total - shipped - disposed),
        "shipped_mass_kg": rational(shipped),
        "disposed_mass_kg": rational(disposed),
        **_quantities(rows, point),
        "owners": [
            {
                "owner_id": r["owner_id"],
                "kind": r["kind"],
                "containers": r["containers"],
                "units_by_sku": r["units_by_sku"],
                "gross_mass_kg": rational(r["gross_mass"]),
            }
            for r in rows
        ],
        "zones": _zones(rows, source_zones(profile)),
    }
