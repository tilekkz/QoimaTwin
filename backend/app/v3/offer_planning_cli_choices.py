"""Reuse closed producer decoders; no clocks, budgets or physical choices are defaulted."""

from app.storage.canonical_json import parse_json
from app.v3.offer_history_choices import parse_choices
from app.v3.offer_planning_cli_models import PlanningChoices
from app.v3.offer_projection_validation import validate_choices as validate_projection
from app.v3.offer_projection_wire import choices_from_wire
from app.v3.outbound_placement_decode import decode_choices
from app.v3.outbound_placement_validation import validate_choices as validate_placement


def decode_request_choices(raw: dict[str, bytes]) -> PlanningChoices:
    history = parse_choices(parse_json(raw["history-choices.json"]))
    projection = choices_from_wire(parse_json(raw["projection-choices.json"]))
    placement = decode_choices(parse_json(raw["placement-choices.json"]))
    validate_projection(projection)
    validate_placement(placement)
    return PlanningChoices(history, projection, placement)
