"""Explicit synthetic caller uses the matching authenticated stock offer identity."""

import json
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.offer_projection_wire import choices_from_wire
from tests.v3.test_forecast_placement_fixtures import explicit_history


def arguments(root: Path, output: Path, stock: ForecastBoundStock) -> list[str]:
    example = json.loads(Path(__file__).with_name("offer_planning_cli_example.json").read_bytes())
    history = json.loads(stock.projection.forecast_bytes)["history"]
    raw_history = explicit_history()
    assert example["history_choices"] == history["choices"]
    assert raw_history == history["raw_history_utf8"].encode("utf-8")
    assert choices_from_wire(example["projection_choices"]) == stock.projection.choices
    candidate = example["placement_choices"]["candidates"][0]
    rows = [
        row
        for row in stock.allocations
        if row.status == "original_bound"
        and row.hu is not None
        and row.hu.hu_id == candidate["hu_id"]
    ]
    assert len(rows) == 1 and rows[0].offer.port_id == candidate["customer"]["port_id"]
    candidate["customer"]["offer_id"] = rows[0].offer.job_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "history.csv").write_bytes(raw_history)
    for key in ("history_choices", "projection_choices", "placement_choices"):
        (root / (key + ".json")).write_bytes(canonical_bytes(example[key]))
    return [
        "v3",
        "plan-offers",
        "--history",
        str(root / "history.csv"),
        "--history-choices",
        str(root / "history_choices.json"),
        "--model",
        "mean28",
        "--projection-choices",
        str(root / "projection_choices.json"),
        "--placement-choices",
        str(root / "placement_choices.json"),
        "--out",
        str(output),
    ]
