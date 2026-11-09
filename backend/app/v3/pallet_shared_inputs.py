"""Strict local-fixture scope and exact C02 inventory identity before shared execution."""

import json
from fractions import Fraction
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.input_json import PREFIX, verified_package
from app.v3.light_flow_models import FlowProfile
from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_plan import validate_timing
from app.v3.pallet_cycle_types import PLATFORM_ID, CycleTimingProfile
from app.v3.pallet_shared_models import PalletSharedError, PalletSharedJob, PalletSharedProfile
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.stock_ledger import StockLedger
from app.v3.stock_source import recipes
from app.v3.whole_flow_models import WholeFlowProfile


def fail(code: str, detail: str) -> None:
    raise PalletSharedError(code, detail)


def validate_inputs(profile: PalletSharedProfile, proof: LocalGeometryProof) -> None:
    if type(profile) is not PalletSharedProfile or type(profile.world) is not WholeFlowProfile:
        fail("TYPED_PALLET_PROFILE_REQUIRED", "exact native profile types required")
    if (
        type(profile.world.receipts) is not ReceiptFlowProfile
        or type(profile.world.receipts.flow) is not FlowProfile
    ):
        fail("TYPED_PALLET_PROFILE_REQUIRED", "exact shared receipt/flow types required")
    _identities(profile)
    flow = profile.world.receipts.flow
    if profile.inventory_scope != "analytical_hand" or flow.source_revision is not None:
        fail(
            "UNSUPPORTED_SOURCE_INITIAL_PLACEMENT",
            "Pinned22296 baseline has no HU at HEAVY_E001; local fixture is not a531st source HU",
        )
    if profile.platform_id != PLATFORM_ID:
        fail("UNSUPPORTED_PALLET_SLOT", "Only the proved HEAVY_E001 local platform is covered")
    _exact_type(
        profile.timing,
        CycleTimingProfile,
        "TYPED_PALLET_TIMING_REQUIRED",
        "explicit exact synthetic timing required",
    )
    validate_timing(profile.timing)
    _exact_type(
        profile.source_approach,
        bool,
        "TYPED_PALLET_BRIDGE_REQUIRED",
        "explicit Boolean bridge choice required",
    )
    _driver(profile)
    _jobs(profile)
    if type(proof) is not LocalGeometryProof or profile.model_sha256 != proof.mesh_sha256:
        fail("PALLET_MODEL_BINDING_MISMATCH", "exact proof model binding required")
    _recipe(profile)


def _exact_type(value: object, expected: type[object], code: str, detail: str) -> None:
    if type(value) is not expected:
        fail(code, detail)


def _identities(profile: PalletSharedProfile) -> None:
    values = (
        profile.hu_id,
        profile.platform_id,
        profile.vehicle_owner_id,
        profile.driver_anchor,
        profile.model_sha256,
        profile.inventory_scope,
        profile.initial_driver_state,
    )
    if any(type(value) is not str or not value.strip() for value in values):
        fail("TYPED_PALLET_IDENTITY_REQUIRED", "exact nonempty physical identities required")


def _driver(profile: PalletSharedProfile) -> None:
    flow = profile.world.receipts.flow
    actor = next((a for a in flow.actors if a.actor_id == "F01"), None)
    if (
        profile.initial_driver_state != "seated_in_FL01"
        or actor is None
        or actor.home != profile.driver_anchor
        or profile.driver_anchor not in flow.graph.node_ids
        or any(profile.driver_anchor in (a.source, a.target) for a in flow.graph.arcs)
    ):
        fail("INITIAL_SEATED_DRIVER_REQUIRED", "declare an isolated logical moving-frame home")
    owners = {o.owner_id: o for o in (*flow.stock.owners, *flow.owners)}
    vehicle = owners.get(profile.vehicle_owner_id)
    platform = owners.get(profile.platform_id)
    if (
        profile.vehicle_owner_id != "vehicle:FL01"
        or vehicle is None
        or vehicle.kind != "vehicle"
        or type(vehicle.capacity) is not int
        or vehicle.capacity != 1
        or platform is None
        or platform.kind != "slot"
        or type(platform.capacity) is not int
        or platform.capacity != 1
    ):
        fail("FINITE_PALLET_OWNERS_REQUIRED", "one actual FL01 owner and source platform required")


def _jobs(profile: PalletSharedProfile) -> None:
    if type(profile.jobs) is not tuple or any(type(j) is not PalletSharedJob for j in profile.jobs):
        fail("TYPED_PALLET_JOBS_REQUIRED", "immutable exact jobs required")
    existing = {o.order_id for o in profile.world.receipts.flow.orders}
    existing |= {o.job_id for o in profile.world.orders}
    existing |= {r.definition.receipt_id for r in profile.world.receipts.receipts}
    for job in profile.jobs:
        if type(job.operation) is not str or type(job.hu_id) is not str:
            fail("INVALID_PALLET_JOB", "exact operation and HU identities required")
        if job.operation != "local_pickup_return":
            fail("UNSUPPORTED_PALLET_RECEIPT", "local pickup-return is not an inbound receipt")
        if type(job.job_id) is not str or not job.job_id.strip() or job.job_id in existing:
            fail("DUPLICATE_PALLET_JOB", "shared work IDs must be unique and nonempty")
        existing.add(job.job_id)
        if type(job.ready_tick) is not int or job.ready_tick < 0 or job.hu_id != profile.hu_id:
            fail("INVALID_PALLET_JOB", "exact arrival and existing fixture HU required")


def _recipe(profile: PalletSharedProfile) -> None:
    root = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    _, documents = verified_package(root)
    document = documents[PREFIX + "cargo-catalog-v3.json"]
    exact = json.loads(canonical_bytes(document), parse_float=Fraction)
    row = next(r for r in exact["records"] if r["archetype_id"] == "PALLET_LOAD")
    unit_recipe, wrapper = recipes(row, "exact pinned C02 local fixture")
    flow = profile.world.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    if profile.hu_id not in {c.container_id for c in flow.stock.containers}:
        fail("EXISTING_PALLET_REQUIRED", "cycle cannot create or credit a future HU")
    contents = ledger.contents(profile.hu_id)
    if any(u.token.recipe.archetype_id != "PALLET_LOAD" for u in contents.units):
        fail("UNSUPPORTED_PALLET_CLASS", "only exact PALLET_LOAD is proved")
    actual = contents.container.recipe
    values = (
        actual.outer,
        actual.tare_kg,
        actual.max_gross_kg,
        actual.max_units,
        actual.allowed_archetypes,
        actual.kind,
        actual.inner,
        actual.clearance_m,
    )
    expected = (
        wrapper.outer,
        wrapper.tare_kg,
        wrapper.max_gross_kg,
        wrapper.max_units,
        wrapper.allowed_archetypes,
        wrapper.kind,
        wrapper.inner,
        wrapper.clearance_m,
    )
    if (
        contents.container.owner_id != profile.platform_id
        or contents.gross_mass_kg != 455
        or len(contents.units) != 24
        or values != expected
        or any(u.token.recipe != unit_recipe for u in contents.units)
    ):
        fail("INVALID_C02_PALLET_RECIPE", "exact intact24-unit455kg original wrapper required")
    if {u.token.ordinal for u in contents.units} != set(range(1, 25)):
        fail("INVALID_C02_PALLET_ANCESTRY", "same original24 unit identities required")
