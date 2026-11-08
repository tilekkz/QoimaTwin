"""Projection may remove immutable detail only after confirming it matches source authority."""

from dataclasses import replace
from fractions import Fraction

import pytest

from app.v3.receipt_run import build_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


@pytest.mark.parametrize("field", ["recipe", "definition", "token"])
def test_native_projection_cannot_hide_changed_immutable_values(field: str) -> None:
    inputs, outcome = sample()
    end = outcome.at_end
    if field == "recipe":
        rows = end.stock.containers
        bad = replace(rows[0], recipe=replace(rows[0].recipe, tare_kg=Fraction(999)))
        changed = (bad, *rows[1:])
        end = replace(
            end,
            stock=replace(end.stock, containers=changed),
            inventory=replace(end.inventory, containers=changed),
        )
        outcome = replace(
            outcome,
            at_end=end,
            checkpoints=tuple(s for s in outcome.checkpoints if s.tick != end.tick),
        )
    elif field == "definition":
        definitions = end.inventory.registered_receipts
        bad_definition = replace(definitions[0], quantity_units=999)
        end = replace(end, inventory=replace(end.inventory, registered_receipts=(bad_definition,)))
        outcome = replace(
            outcome,
            at_end=end,
            checkpoints=tuple(s for s in outcome.checkpoints if s.tick != end.tick),
        )
    else:
        index = next(i for i, e in enumerate(outcome.events) if e.kind == "picked")
        event = outcome.events[index]
        assert event.delta is not None
        row = event.delta.before[0]
        unit = row.units[0]
        changed_unit = replace(unit, token=replace(unit.token, lot_id="invented"))
        changed_row = replace(row, units=(changed_unit, *row.units[1:]))
        delta = replace(event.delta, before=(changed_row, *event.delta.before[1:]))
        event = replace(event, delta=delta)
        outcome = replace(
            outcome, events=(*outcome.events[:index], event, *outcome.events[index + 1 :])
        )
    with pytest.raises(ValueError):
        build_receipt_run(inputs, outcome)
