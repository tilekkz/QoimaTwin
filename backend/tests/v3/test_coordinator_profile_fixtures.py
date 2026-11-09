"""Explicit source choices; no expected result is taken from a simulator."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle

ROOT = Path(__file__).resolve().parents[2]


def coordinator_document() -> dict[str, Any]:
    path = ROOT / "docs/proposals/adaptive-v3/coordinator-profile.example.json"
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


@pytest.fixture(scope="module")
def coordinator_sources() -> tuple[V3Bundle, ConveyorSource]:
    bundle = load_v3_bundle(ROOT / "data/v3-proposal")
    return bundle, load_conveyor_source(bundle, ROOT / "data/v3-conveyor-proposal")


def with_whole_receipt(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    source = json.loads(
        (ROOT / "docs/proposals/adaptive-v3/whole-flow-profile.example.json").read_text()
    )
    for key in (
        "receipts",
        "receipt_ports",
        "receipt_buffers",
        "whole_orders",
        "whole_ports",
        "whole_buffers",
        "receipt_times",
        "whole_times",
    ):
        result[key] = source[key]
    known = {row["owner_id"] for row in result["owners"]}
    result["owners"].extend(row for row in source["owners"] if row["owner_id"] not in known)
    actors = {row["actor_id"]: row for row in source["actors"]}
    for actor in result["actors"]:
        if actor["actor_id"].startswith(("R", "S")):
            actor.update(actors[actor["actor_id"]])
    return result
