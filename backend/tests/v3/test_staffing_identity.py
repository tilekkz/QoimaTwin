"""Allocation choices have their own bounded identity, separate from common registry facts."""

from dataclasses import replace

from app.v3.staff_registry import compile_staff_registry
from app.v3.staffing_identity import analytical_allocation_hash
from tests.v3.test_staff_registry_fixtures import SECOND, registry_document
from tests.v3.test_staffing_analytical import covers


def test_allocation_order_is_canonical_and_choice_changes_only_allocation_identity() -> None:
    registry = compile_staff_registry(registry_document())
    common = registry.registry_common_hash
    first = analytical_allocation_hash(registry, covers())
    assert first == analytical_allocation_hash(registry, tuple(reversed(covers())))
    changed = (replace(covers()[0], start_tick=110 * SECOND), covers()[1])
    assert first != analytical_allocation_hash(registry, changed)
    assert first != analytical_allocation_hash(registry, ())
    assert registry.registry_common_hash == common
