"""Closed bundle inventory rejects altered evidence before expensive reconstruction."""

import json
from pathlib import Path
from shutil import copytree

import pytest

from app.v3.offer_planning_cli_validation import validate_offer_plan
from tests.v3.test_forecast_placement_fixtures import stock
from tests.v3.test_offer_planning_cli import bundle

__all__ = ["bundle", "stock"]


@pytest.mark.parametrize("mutation", ["extra", "missing", "modified", "manifest_alias"])
def test_inventory_or_hash_mismatch_rejected(bundle: Path, tmp_path: Path, mutation: str) -> None:
    target = tmp_path / "copy"
    copytree(bundle, target)
    if mutation == "extra":
        (target / "ignored.json").write_bytes(b"{}")
    elif mutation == "missing":
        (target / "history.json").unlink()
    elif mutation == "modified":
        with (target / "stock.json").open("ab") as stream:
            stream.write(b" ")
    else:
        path = target / "manifest.json"
        value = json.loads(path.read_bytes())
        value["semantic"]["engine_calls"] = False
        path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_offer_plan(target)
