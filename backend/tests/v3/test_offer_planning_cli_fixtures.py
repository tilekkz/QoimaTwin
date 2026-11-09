"""Explicit frozen synthetic source example; fixture creation invokes no producer."""

import json
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from tests.v3.test_forecast_placement_fixtures import explicit_history


def arguments(root: Path, output: Path) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    example = json.loads(Path(__file__).with_name("offer_planning_cli_example.json").read_bytes())
    (root / "history.csv").write_bytes(explicit_history())
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
