"""Independent exact-size and resource restrictions precede V3 placement scoring."""

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal as D
from decimal import localcontext

import pytest

from app.v3.admission import candidate_admission, storage_admission
from app.v3.admission_models import Cargo, Handler, RouteProof, Slot, StorageState


def cargo() -> Cargo:
    return Cargo("BOX", (D(".60"), D(".40"), D(".30")), D(8), ("xyz",))


def slot() -> Slot:
    return Slot(
        "S1",
        "M1",
        (D(".65"), D(".45"), D(".35")),
        D(15),
        2,
        D(100),
        ("BOX",),
        ("xyz",),
        D(0),
        D(".20"),
        D("1.20"),
    )


def handler() -> Handler:
    return Handler("manual", ("BOX",), D(15), D("1.50"))


def test_f2_geometry_mass_and_two_boxes() -> None:
    empty = StorageState()
    small = replace(slot(), dimensions=(D(".55"), D(".45"), D(".35")))
    assert storage_admission(cargo(), small, empty, handler()).reasons == ("DIMENSION_MISMATCH",)
    light = replace(slot(), max_payload_kg=D(7))
    assert storage_admission(cargo(), light, empty, handler()).reasons == ("OVERWEIGHT",)
    wide = replace(slot(), dimensions=(D("1.25"), D(".45"), D(".35")))
    assert storage_admission(cargo(), wide, empty, handler()).eligible
    occupied = StorageState(slot_hus=1, slot_mass_kg=D(8), module_mass_kg=D(8))
    assert storage_admission(cargo(), wide, occupied, handler()).reasons == ("OVERWEIGHT",)


def test_exact_clearance_boundary_no_epsilon_or_hover() -> None:
    fragile = replace(cargo(), dimensions=(D(".50"), D(".95"), D(".40")))
    target = replace(slot(), dimensions=(D(1), D("1.05"), D(1)), clearance_m=D(".05"))
    result = storage_admission(fragile, target, StorageState(), handler())
    assert result.eligible
    assert result.bottom_y_m == D(".20")
    assert result.top_y_m == D("1.15")
    assert result.headroom_m == D(".10")
    excess = replace(fragile, dimensions=(D(".50"), D(".95000000001"), D(".40")))
    assert storage_admission(excess, target, StorageState(), handler()).reasons == (
        "DIMENSION_MISMATCH",
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda s: replace(s, reserve_only=True), "RESERVE_ACCESS_BLOCKED"),
        (lambda s: replace(s, allowed_archetypes=("OTHER",)), "TYPE_MISMATCH"),
        (lambda s: replace(s, orientations=("zyx",)), "ORIENTATION_FORBIDDEN"),
        (lambda s: replace(s, max_handling_units=0), "SLOT_CAPACITY"),
        (lambda s: replace(s, module_max_payload_kg=D(7)), "MODULE_OVERWEIGHT"),
        (lambda s: replace(s, required_handler_ids=("forklift",)), "HANDLER_UNAVAILABLE"),
        (lambda s: replace(s, service_height_m=D(2)), "HEIGHT_ACCESS_UNAVAILABLE"),
    ],
)
def test_rejections_precede_score(change: Callable[[Slot], Slot], reason: str) -> None:
    result = storage_admission(cargo(), change(slot()), StorageState(), handler())
    assert result.reasons == (reason,)
    assert not result.eligible
    assert not result.operational_admission
    assert not result.cost_evaluated


def test_occupied_slot_and_module_mass_are_aggregate() -> None:
    full = StorageState(slot_hus=2, slot_mass_kg=D(10), module_mass_kg=D(10))
    assert storage_admission(cargo(), slot(), full, handler()).reasons == (
        "OVERWEIGHT",
        "SLOT_CAPACITY",
    )
    other_slots = StorageState(module_mass_kg=D(95))
    assert storage_admission(cargo(), slot(), other_slots, handler()).reasons == (
        "MODULE_OVERWEIGHT",
    )


def test_route_proof_is_required_before_score_and_bound_to_candidate() -> None:
    proof = RouteProof("layout-hash", cargo(), "S1", handler(), True)
    result = candidate_admission(cargo(), slot(), StorageState(), handler(), proof, "layout-hash")
    assert result.eligible and not result.operational_admission and not result.cost_evaluated
    for wrong in [
        None,
        replace(proof, reachable=False),
        replace(proof, slot_id="S2"),
        replace(proof, layout_hash="other"),
        replace(proof, handler=replace(handler(), handler_id="forklift")),
        replace(proof, cargo=replace(cargo(), gross_mass_kg=D(7))),
    ]:
        result = candidate_admission(
            cargo(), slot(), StorageState(), handler(), wrong, "layout-hash"
        )
        assert result.reasons == ("PATH_CLEARANCE",)


def test_invalid_state_is_not_a_compatible_candidate() -> None:
    with pytest.raises(ValueError, match="invalid storage state"):
        storage_admission(cargo(), slot(), StorageState(module_mass_kg=D(-1)), handler())
    with pytest.raises(ValueError, match="nonfinite"):
        storage_admission(
            replace(cargo(), gross_mass_kg=D("NaN")), slot(), StorageState(), handler()
        )


def test_missing_mass_or_handler_fails_closed() -> None:
    result = storage_admission(
        replace(cargo(), gross_mass_kg=None), slot(), StorageState(), handler()
    )
    assert result.reasons == ("UNKNOWN_MASS",)
    result = storage_admission(cargo(), slot(), StorageState(), None)
    assert result.reasons == ("HANDLER_UNAVAILABLE",)


def test_decimal_context_cannot_allow_excess_dimension() -> None:
    too_tall = replace(cargo(), dimensions=(D(".50"), D(".95000000001"), D(".40")))
    target = replace(slot(), dimensions=(D(1), D("1.05"), D(1)), clearance_m=D(".05"))
    with localcontext() as context:
        context.prec = 6
        result = storage_admission(too_tall, target, StorageState(), handler())
    assert result.reasons == ("DIMENSION_MISMATCH",)
