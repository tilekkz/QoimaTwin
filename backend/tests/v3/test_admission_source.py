"""C04/C05 source oracles, independent of any simulation output."""

import json
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from app.v3.admission_models import Handler
from app.v3.admission_source import SelectedCapability, SourceAdmissionCatalog, SourcePlacement
from app.v3.admission_source_decode import decode_cargo, decode_slot, document
from app.v3.input_models import ImmutableDocument, V3Bundle
from app.v3.inputs import load_v3_bundle

D = Decimal


@pytest.fixture(scope="module")
def bundle() -> V3Bundle:
    return load_v3_bundle(Path("data/v3-proposal"))


@pytest.fixture(scope="module")
def catalog(bundle: V3Bundle) -> SourceAdmissionCatalog:
    return SourceAdmissionCatalog.from_bundle(bundle)


def capability(archetype: str, *, forklift: bool = False) -> SelectedCapability:
    return SelectedCapability(
        Handler(
            "forklift_operator" if forklift else "manual_operator",
            (archetype,),
            D(1000) if forklift else D(15),
            D("1.5") if forklift else D("1.25"),
        ),
        "forklift_assisted" if forklift else "manual_hand_carry",
        frozenset(("forklift", "approved_load_support")) if forklift else frozenset(),
    )


def hu_for(catalog: SourceAdmissionCatalog, archetype: str) -> str:
    return next(key for key, value in catalog.hu_archetypes.items() if value == archetype)


def test_all_530_real_placements_preserve_exact_static_fit(catalog: SourceAdmissionCatalog) -> None:
    assert len(catalog.cargo) == 8
    assert len(catalog.slots) == 776
    assert len(catalog.baseline) == 530
    assert sum(
        catalog.cargo[a].cargo.gross_mass_kg or D(0) for a in catalog.hu_archetypes.values()
    ) == D("9403.85")
    for placement in catalog.baseline:
        archetype = catalog.hu_archetypes[placement.handling_unit_id]
        selected = capability(
            archetype, forklift=archetype not in ("SMALL_CARTON", "STANDARD_CARTON")
        )
        result = catalog.evaluate(
            placement.handling_unit_id, placement.slot_id, selected, placements=catalog.baseline
        )
        assert result.eligible, (placement, result)
        assert result.operational_admission is False
        assert result.cost_evaluated is False


def test_all_188_reserve_slots_remain_blocked(catalog: SourceAdmissionCatalog) -> None:
    reserved = [s for s in catalog.slots.values() if s.slot.reserve_only]
    assert len(reserved) == 188
    hu = hu_for(catalog, "FRAGILE_CRATE")
    for target in reserved:
        assert catalog.evaluate(
            hu, target.slot.slot_id, capability("FRAGILE_CRATE", forklift=True), placements=()
        ).reasons == ("RESERVE_ACCESS_BLOCKED",)


def test_fragile_ground_support_and_handler_intersection(catalog: SourceAdmissionCatalog) -> None:
    hu = hu_for(catalog, "FRAGILE_CRATE")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    good = capability("FRAGILE_CRATE", forklift=True)
    result = catalog.evaluate(hu, target, good, placements=())
    assert (result.bottom_y_m, result.top_y_m, result.headroom_m) == (D(".20"), D("1.15"), D(".10"))
    for selected in (
        None,
        capability("FRAGILE_CRATE"),
        replace(good, equipment_tags=frozenset({"forklift"})),
    ):
        assert catalog.evaluate(hu, target, selected, placements=()).reasons == (
            "HANDLER_UNAVAILABLE",
        )
    standard = hu_for(catalog, "STANDARD_CARTON")
    assert catalog.evaluate(
        standard, target, capability("STANDARD_CARTON", forklift=True), placements=()
    ).reasons == ("HANDLER_UNAVAILABLE",)


def test_cart_requires_equipment_and_declared_transport(catalog: SourceAdmissionCatalog) -> None:
    hu = hu_for(catalog, "SMALL_CARTON")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    cart = replace(capability("SMALL_CARTON"), transport_tag="manual_cart")
    assert catalog.evaluate(hu, target, cart, placements=()).reasons == ("HANDLER_UNAVAILABLE",)
    assert catalog.evaluate(
        hu, target, replace(cart, equipment_tags=frozenset({"manual_cart"})), placements=()
    ).eligible


def test_explicit_occupancy_excludes_only_moving_hu(catalog: SourceAdmissionCatalog) -> None:
    first, second = catalog.baseline[:2]
    selected = capability("SMALL_CARTON")
    occupied = (SourcePlacement(second.handling_unit_id, first.slot_id),)
    assert catalog.evaluate(
        first.handling_unit_id, first.slot_id, selected, placements=occupied
    ).reasons == ("SLOT_CAPACITY",)
    assert catalog.evaluate(
        first.handling_unit_id, first.slot_id, selected, placements=(first,)
    ).eligible


def test_exact_source_height_boundary_has_no_epsilon(catalog: SourceAdmissionCatalog) -> None:
    hu = hu_for(catalog, "FRAGILE_CRATE")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    rule = catalog.cargo["FRAGILE_CRATE"]
    enlarged = replace(
        rule, cargo=replace(rule.cargo, dimensions=(D("1.10"), D(".95000000001"), D(".85")))
    )
    changed = replace(catalog, cargo={**catalog.cargo, "FRAGILE_CRATE": enlarged})
    assert changed.evaluate(
        hu, target, capability("FRAGILE_CRATE", forklift=True), placements=()
    ).reasons == ("DIMENSION_MISMATCH",)


def test_gross_mass_includes_tare(catalog: SourceAdmissionCatalog) -> None:
    hu = hu_for(catalog, "FRAGILE_CRATE")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    selected = capability("FRAGILE_CRATE", forklift=True)
    assert catalog.cargo["FRAGILE_CRATE"].cargo.gross_mass_kg == D(88)
    selected = replace(selected, handler=replace(selected.handler, max_payload_kg=D(73)))
    assert catalog.evaluate(hu, target, selected, placements=()).reasons == ("HANDLER_UNAVAILABLE",)


@pytest.mark.parametrize(
    ("archetype", "expected"),
    [
        ("SMALL_CARTON", 488),
        ("STANDARD_CARTON", 72),
        ("HEAVY_BOX", 24),
        ("PALLET_LOAD", 24),
        ("IBC", 24),
        ("LONG_BUNDLE", 12),
        ("DRUM", 24),
        ("FRAGILE_CRATE", 64),
    ],
)
def test_c05_candidate_counts_are_overlapping_not_additive(
    catalog: SourceAdmissionCatalog,
    archetype: str,
    expected: int,
) -> None:
    hu = hu_for(catalog, archetype)
    selected = capability(archetype, forklift=archetype not in ("SMALL_CARTON", "STANDARD_CARTON"))
    assert (
        sum(catalog.evaluate(hu, key, selected, placements=()).eligible for key in catalog.slots)
        == expected
    )


def test_family_intersection_precedes_even_generous_slot_permissions(
    catalog: SourceAdmissionCatalog,
) -> None:
    hu = hu_for(catalog, "SMALL_CARTON")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    cargo = replace(catalog.cargo["SMALL_CARTON"], storage_families=("HEAVY",))
    changed = replace(catalog, cargo={**catalog.cargo, "SMALL_CARTON": cargo})
    assert changed.evaluate(hu, target, capability("SMALL_CARTON"), placements=()).reasons == (
        "TYPE_MISMATCH",
    )


def test_selected_height_limit_and_hu_orientation_remain_required(
    catalog: SourceAdmissionCatalog,
) -> None:
    hu = hu_for(catalog, "SMALL_CARTON")
    target = next(p.slot_id for p in catalog.baseline if p.handling_unit_id == hu)
    selected = capability("SMALL_CARTON")
    too_low = replace(selected, handler=replace(selected.handler, max_service_height_m=D(0)))
    assert catalog.evaluate(hu, target, too_low, placements=()).reasons == (
        "HEIGHT_ACCESS_UNAVAILABLE",
    )
    changed = replace(catalog, hu_orientations={**catalog.hu_orientations, hu: "yaw90"})
    assert changed.evaluate(hu, target, selected, placements=()).reasons == (
        "ORIENTATION_FORBIDDEN",
    )


def test_aggregate_module_mass_uses_other_slots_and_gross_mass(
    catalog: SourceAdmissionCatalog,
) -> None:
    first, second = catalog.baseline[:2]
    target = catalog.slots[first.slot_id]
    alternate = next(
        key
        for key, slot in catalog.slots.items()
        if slot.slot.module_id == target.slot.module_id and key != first.slot_id
    )
    limited = replace(target, slot=replace(target.slot, module_max_payload_kg=D("1.87999999999")))
    changed = replace(catalog, slots={**catalog.slots, first.slot_id: limited})
    with localcontext() as context:
        context.prec = 3
        result = changed.evaluate(
            first.handling_unit_id,
            first.slot_id,
            capability("SMALL_CARTON"),
            placements=(SourcePlacement(second.handling_unit_id, alternate),),
        )
    assert result.reasons == ("MODULE_OVERWEIGHT",)  # .94 + .94 = 1.88 exactly


@pytest.mark.parametrize("kind", ["duplicate", "unknown_hu", "unknown_slot", "overfull"])
def test_invalid_explicit_occupancy_is_rejected(catalog: SourceAdmissionCatalog, kind: str) -> None:
    first, second = catalog.baseline[:2]
    cases = {
        "duplicate": (first, first),
        "unknown_hu": (SourcePlacement("absent", first.slot_id),),
        "unknown_slot": (SourcePlacement(first.handling_unit_id, "absent"),),
        "overfull": (first, SourcePlacement(second.handling_unit_id, first.slot_id)),
    }
    with pytest.raises(ValueError):
        catalog.evaluate(
            first.handling_unit_id,
            first.slot_id,
            capability("SMALL_CARTON"),
            placements=cases[kind],
        )


@pytest.mark.parametrize("flag", ["retrieval_blocked", "active_pick_candidate"])
def test_source_retrieval_flags_are_not_lost(bundle: V3Bundle, flag: str) -> None:
    data = document(bundle, "storage-slots-v3.json")
    slot = data["slots"][0]
    slot[flag] = flag == "retrieval_blocked"
    slot["reserve_only"] = False
    decoded = decode_slot(slot, data["modules"][0])
    assert decoded.slot.reserve_only is True


def test_source_extra_orientation_is_not_silently_granted(bundle: V3Bundle) -> None:
    cargo = document(bundle, "cargo-catalog-v3.json")["records"][0]
    cargo["orientation"]["permitted_orientations"][0]["local_axes_in_destination"] = [
        "+Z",
        "+Y",
        "-X",
    ]
    with pytest.raises(ValueError, match="orientation"):
        decode_cargo(cargo)
    data = document(bundle, "storage-slots-v3.json")
    data["slots"][0]["allowed_orientation_ids"].append("yaw90")
    with pytest.raises(ValueError, match="orientation"):
        decode_slot(data["slots"][0], data["modules"][0])


def test_stricter_source_module_hu_limit_fails_closed(bundle: V3Bundle) -> None:
    key = "docs/v3/contract-proposals/storage-slots-v3.json"
    data = bundle.documents[key].decode()
    data["modules"][0]["max_handling_units"] = 9  # Ten SMALL slots no longer imply this cap.
    changed = replace(
        bundle,
        documents={
            **bundle.documents,
            key: ImmutableDocument(json.dumps(data).encode()),
        },
    )
    with pytest.raises(ValueError, match="aggregate gate"):
        SourceAdmissionCatalog.from_bundle(changed)


@pytest.mark.parametrize("restriction", ["cargo_mode", "manual_pick", "manual_mass"])
def test_source_manual_restrictions_survive_typed_projection(
    catalog: SourceAdmissionCatalog,
    restriction: str,
) -> None:
    first = catalog.baseline[0]
    cargo = catalog.cargo["SMALL_CARTON"]
    slot = catalog.slots[first.slot_id]
    if restriction == "cargo_mode":
        cargo = replace(cargo, modes=())
    elif restriction == "manual_pick":
        slot = replace(slot, manual_pick_allowed=False)
    else:
        slot = replace(slot, manual_mass_limit_kg=D(".93"))
    changed = replace(
        catalog,
        cargo={**catalog.cargo, "SMALL_CARTON": cargo},
        slots={**catalog.slots, first.slot_id: slot},
    )
    assert changed.evaluate(
        first.handling_unit_id, first.slot_id, capability("SMALL_CARTON"), placements=()
    ).reasons == ("HANDLER_UNAVAILABLE",)
