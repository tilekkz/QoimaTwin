"""Exact source-decimal boundaries; serialized summaries are not capacity gates."""

from decimal import localcontext
from typing import Any

import pytest

from app.v3.input_catalogs import validate_cargo_arithmetic
from app.v3.input_models import V3InputError
from app.v3.input_ports import validate_port
from app.v3.input_stock import (
    validate_assignment,
    validate_mix,
    validate_module_mass,
    validate_sku_templates,
    validate_static_fit,
)
from app.v3.inputs import load_v3_bundle

from .input_helpers import PACKAGE, PREFIX, catalog_context


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("height", [0.95000000001, 0.9500000000000001])
def test_dimension_excess_has_no_epsilon(axis: int, height: float) -> None:
    dimensions = [0.95, 0.95, 0.95]
    dimensions[axis] = height
    with localcontext() as context:
        context.prec = 3
        with pytest.raises(V3InputError, match=f"slot_fit/{axis}"):
            validate_static_fit(
                {"dimensions_xyz_m": dimensions},
                {"usable_dimensions_xyz_m": [1.05] * 3, "clearance_each_side_m": 0.05},
                "boundary",
            )


def test_exact_dimension_equality_is_accepted() -> None:
    validate_static_fit(
        {"dimensions_xyz_m": [0.1, 0.95, 0.95]},
        {"usable_dimensions_xyz_m": [0.3, 1.05, 1.05], "clearance_each_side_m": 0.05},
        "boundary",
    )


@pytest.mark.parametrize(
    "masses,capacity,reject", [([0.1, 0.7], 0.7999999999999999, True), ([0.1, 0.2], 0.3, False)]
)
def test_module_payload_uses_exact_sum(masses: list[float], capacity: float, reject: bool) -> None:
    documents = {
        PREFIX + "baseline-assignment-v3.json": {"module_mass_kg": {"module": sum(masses)}},
        PREFIX + "storage-slots-v3.json": {
            "modules": [
                {"module_id": "module", "max_module_payload_kg": capacity, "max_handling_units": 2}
            ]
        },
    }
    cargo = {str(i): {"handling_unit": {"gross_mass_kg": m}} for i, m in enumerate(masses)}
    assignments = [{"module_id": "module", "archetype_id": str(i)} for i in range(2)]
    with localcontext() as context:
        context.prec = 3
        if reject:
            with pytest.raises(V3InputError, match="module payload exceeded"):
                validate_module_mass(documents, assignments, cargo)
        else:
            validate_module_mass(documents, assignments, cargo)


@pytest.fixture(scope="module")
def source_documents() -> dict[str, Any]:
    return {name: doc.decode() for name, doc in load_v3_bundle(PACKAGE).documents.items()}


@pytest.mark.parametrize(
    "corruption", ["slot_orientation", "cargo_axes", "storage_type", "scale", "scale_bool", "port"]
)
def test_assignment_preserves_source_permissions(
    source_documents: dict[str, Any], corruption: str
) -> None:
    import copy

    documents = copy.deepcopy(source_documents)
    cargo, skus, slots, ports = catalog_context(documents)
    assignment = documents[PREFIX + "baseline-assignment-v3.json"]["assignments"][0]
    archetype, slot = cargo[assignment["archetype_id"]], slots[assignment["slot_id"]]
    if corruption == "slot_orientation":
        slot["allowed_orientation_ids"] = ["unlisted_rotation"]
    elif corruption == "cargo_axes":
        archetype["orientation"]["permitted_orientations"][0]["local_axes_in_destination"] = [
            "+Z",
            "+Y",
            "-X",
        ]
    elif corruption == "storage_type":
        archetype["compatibility"]["storage_type_tags"] = ["LONG"]
    elif corruption == "scale":
        assignment["model_scale_factor"] = 0.5
    elif corruption == "scale_bool":
        assignment["model_scale_factor"] = True
    else:
        assignment["planning_legs"][0]["port_id"] = "IN_W_BULK"
    with pytest.raises(V3InputError):
        validate_assignment(assignment, cargo, skus, slots, ports, "assignment")


def test_mass_ledger_cannot_hide_small_excess(source_documents: dict[str, Any]) -> None:
    import copy

    record = copy.deepcopy(source_documents[PREFIX + "cargo-catalog-v3.json"]["records"][0])
    record["handling_unit"]["gross_mass_kg"] -= 1e-10
    with pytest.raises(V3InputError, match="mass"):
        validate_cargo_arithmetic(record, "cargo")


def test_port_allocation_count_is_exact_integer(source_documents: dict[str, Any]) -> None:
    import copy

    port = copy.deepcopy(source_documents[PREFIX + "ports-v3.inbound.json"]["ports"][0])
    port["finite_buffer_capacity"]["allocations"][0]["max_handling_units"] -= 1e-10
    with pytest.raises(V3InputError):
        validate_port(port, "port", "inbound", set(port["allowed_cargo_archetype_ids"]))


def test_mix_does_not_admit_extra_weight() -> None:
    ports = {"port": {"direction": "inbound", "allowed_cargo_archetype_ids": ["cargo"]}}
    with pytest.raises(V3InputError):
        validate_mix({"port": 1.0000000001}, ports, "cargo", "inbound", "mix")


def test_sku_scale_must_be_numeric() -> None:
    catalog = {
        "identity_only_import": True,
        "skus": [
            {
                "archetype_id": "cargo",
                "cargo_template_pointer": "/records/0",
                "model_scale_factor": True,
            }
        ],
    }
    documents = {PREFIX + "cargo-catalog-v3.json": {"records": [{"archetype_id": "cargo"}]}}
    with pytest.raises(V3InputError, match="scaling forbidden"):
        validate_sku_templates(catalog, {"cargo": {}}, documents)
