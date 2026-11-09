"""Accepted shared schema, original semantic checks, plus explicit derived transitions."""

from typing import Any

from app.exporter.validation import _validator, validate_run_semantics
from app.settings import default_contracts_dir


def validate_tilek_run(run: dict[str, Any]) -> None:
    schema = (default_contracts_dir() / "run.schema.json").read_text(encoding="utf-8")
    _validator(schema).validate(run)
    _validate_binding(run)
    previous = (-1.0, -1, -1)
    for seq, event in enumerate(run["events"]):
        key = (event["at_s"], event["phase"], event["seq"])
        if key < previous or seq != event["seq"] or not 0 <= event["phase"] <= 4:
            raise ValueError("invalid visual event sequence or phase")
        previous = key
        if event["kind"] == "actor_state_changed":
            payload = event["payload"]
            required = {"actor_id", "state", "action_id", "transition", "visual_projection"}
            if not required <= payload.keys():
                raise ValueError("visual transition lacks actor/projection binding")
    semantic = dict(run)
    semantic["events"] = [
        dict(e, seq=i)
        for i, e in enumerate(e for e in run["events"] if e["kind"] != "actor_state_changed")
    ]
    validate_run_semantics(semantic)


def _validate_binding(run: dict[str, Any]) -> None:
    events = run["events"]
    binding = events[0]["payload"].get("visual_projection") if events else None
    if (
        not isinstance(binding, dict)
        or binding.get("wire_version") != "tilek-visual-v1"
        or not isinstance(binding.get("source_run_id"), str)
        or not binding["source_run_id"]
        or binding["source_run_id"] == run["run_id"]
        or not isinstance(binding.get("visual_projection_limitations"), list)
    ):
        raise ValueError("visual projection lacks distinct source identity binding")
