"""Unused resources remain part of the common physical authority, not unchecked extras."""

from dataclasses import replace
from typing import cast

import pytest

from app.v3.coordinator_units_models import ParcelPort
from app.v3.coordinator_units_validate import validate_resources
from app.v3.light_flow_models import FlowStation
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


@pytest.mark.parametrize("windows", [((True, 10),), ((5, 4),), ((0, 10), (9, 20)), ()])
def test_unused_port_requires_valid_exact_windows(windows: tuple[tuple[int, int], ...]) -> None:
    p = multi_profile()
    r = p.unit_resources
    assert r is not None
    extra = ParcelPort(replace(r.ports[0].port, port_id="unused", windows=windows), "shipped")
    p = replace(p, unit_resources=replace(r, ports=(*r.ports, extra)))
    with pytest.raises(ValueError):
        validate_resources(p, receipt_conveyor())


def test_nested_station_requires_typed_value_before_reference_access() -> None:
    p = multi_profile()
    r = p.unit_resources
    assert r is not None
    bad = replace(r.stations[0], station=cast(FlowStation, {"station_id": "PK01"}))
    p = replace(p, unit_resources=replace(r, stations=(bad, *r.stations[1:])))
    with pytest.raises(ValueError):
        validate_resources(p, receipt_conveyor())


def test_default_cart_alias_must_name_a_real_registered_cart() -> None:
    p = multi_profile()
    r = p.unit_resources
    assert r is not None
    carts = (replace(r.carts[0], cart=replace(r.carts[0].cart, cart_id="RENAMED")),)
    r = replace(
        r,
        carts=carts,
        pickers=tuple(replace(v, cart_ids=("RENAMED",)) for v in r.pickers),
        assignments=tuple(replace(v, cart_id="RENAMED") for v in r.assignments),
    )
    with pytest.raises(ValueError):
        validate_resources(replace(p, unit_resources=r), receipt_conveyor())


@pytest.mark.parametrize("fault", ["picker", "assignment", "cart", "station", "release"])
def test_explicit_resource_registration_rejects_aliases_and_missing_binding(fault: str) -> None:
    p = multi_profile()
    r = p.unit_resources
    assert r is not None
    if fault == "picker":
        r = replace(r, pickers=r.pickers[:-1])
    elif fault == "assignment":
        r = replace(r, assignments=(r.assignments[0], r.assignments[0]))
    elif fault == "cart":
        r = replace(r, assignments=(replace(r.assignments[0], cart_id="absent"), r.assignments[1]))
    elif fault == "station":
        r = replace(
            r,
            stations=(replace(r.stations[0], belt_route=r.stations[5].belt_route), *r.stations[1:]),
        )
    else:
        r = replace(r, carts=(replace(r.carts[0], release_tick=True),))
    with pytest.raises(ValueError):
        validate_resources(replace(p, unit_resources=r), receipt_conveyor())
