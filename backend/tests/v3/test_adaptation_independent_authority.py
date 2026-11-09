"""Root review: pinned planning sources cannot be changed through returned views."""

from fractions import Fraction
from typing import Any

import pytest

from app.v3.adaptation_decode import decode_horizon
from app.v3.adaptation_source import AdaptationSourceError, load_adaptation_package
from tests.v3.test_adaptation_source import BASE, PACKAGE


def test_baseline_accessor_cannot_mutate_later_verified_reads() -> None:
    package = load_adaptation_package(PACKAGE, BASE)
    view = package.base_document("baseline-assignment-v3.json")
    assert view["summary"]["SKU_count"] == 200
    view["summary"]["SKU_count"] = 0
    assert package.base_document("baseline-assignment-v3.json")["summary"]["SKU_count"] == 200


@pytest.mark.parametrize("alias", [True, 1.0, Fraction(1)])
def test_horizon_accessor_requires_exact_integer_identity(alias: Any) -> None:
    package = load_adaptation_package(PACKAGE, BASE)
    with pytest.raises(AdaptationSourceError):
        package.horizon_document(alias)


@pytest.mark.parametrize("alias", [True, 1.0, Fraction(1)])
def test_decoder_rejects_alias_for_requested_period_count(alias: Any) -> None:
    package = load_adaptation_package(PACKAGE, BASE)
    with pytest.raises(ValueError):
        decode_horizon(package.horizon_document(1), alias)
