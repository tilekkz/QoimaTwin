"""Strict typed decoding of the pinned C11 horizon documents (unclocked planning periods)."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.v3.adaptation_decode import decode_horizon
from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package

BACKEND = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def package() -> AdaptationPackage:
    return load_adaptation_package(
        BACKEND / "data/v3-adaptation-proposal", BACKEND / "data/v3-proposal"
    )


def test_decoded_horizons_keep_proxy_flags_and_unclocked_periods(
    package: AdaptationPackage,
) -> None:
    for periods in (1, 2, 4, 8):
        plan = decode_horizon(package.horizon_document(periods), periods)
        assert plan.periods == periods
        assert plan.period_unit == "unclocked_planning_period"
        assert plan.actual_engine_run is False
        assert plan.operational_admission is False
        assert len(plan.rows) == 530
    assert [
        len(decode_horizon(package.horizon_document(p), p).transfers) for p in (1, 2, 4, 8)
    ] == [
        0,
        2,
        8,
        8,
    ]


def _set(path: tuple[Any, ...], value: Any) -> Callable[[Any], None]:
    def change(document: Any) -> None:
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _duplicate_transfer(document: Any) -> None:
    document["transfers"].append(copy.deepcopy(document["transfers"][0]))


def _duplicate_row(document: Any) -> None:
    document["assignments"].append(copy.deepcopy(document["assignments"][0]))


CORRUPTIONS: dict[str, Callable[[Any], None]] = {
    "engine_claim": _set(("actual_engine_run",), True),
    "admission_claim": _set(("operational_admission",), True),
    "admission_as_int": _set(("operational_admission",), 0),
    "foreign_schema": _set(("schema_id",), "qoima.baseline-assignment.v3-proposal"),
    "bool_periods": _set(("summary", "evaluation_horizon_periods"), True),
    "nonfinite_length": _set(("transfers", 0, "loaded_route", "length_m"), float("inf")),
    "string_length": _set(("transfers", 0, "loaded_route", "length_m"), "86.9"),
    "teleport_tag": _set(("transfers", 0, "transport_tag"), "teleport"),
    "unknown_graph": _set(("transfers", 0, "loaded_route", "graph"), "air"),
    "bool_sequence": _set(("transfers", 0, "sequence"), True),
    "duplicate_transfer": _duplicate_transfer,
    "duplicate_hu_row": _duplicate_row,
    "transfer_admission_claim": _set(("transfers", 0, "operational_admission"), True),
}


@pytest.mark.parametrize("name", sorted(CORRUPTIONS))
def test_malformed_horizon_document_is_rejected(package: AdaptationPackage, name: str) -> None:
    document = copy.deepcopy(package.horizon_document(2))
    CORRUPTIONS[name](document)
    with pytest.raises(ValueError):
        decode_horizon(document, 2)


def test_swapped_period_declaration_is_rejected(package: AdaptationPackage) -> None:
    with pytest.raises(ValueError, match="period"):
        decode_horizon(package.horizon_document(2), 4)


def test_decoding_never_mutates_the_pinned_document(package: AdaptationPackage) -> None:
    document = package.horizon_document(4)
    before = copy.deepcopy(document)
    decode_horizon(document, 4)
    assert document == before
