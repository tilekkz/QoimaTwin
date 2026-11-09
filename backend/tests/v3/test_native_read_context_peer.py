"""Independent exact-type and request-snapshot controls with portable hand evidence."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from shutil import copytree
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import coordinator_transport
from app.v3.coordinator_run import _validate_native, validate_coordinator_run
from app.v3.coordinator_seek import _replay_context, replay_coordinator
from app.v3.coordinator_transport_schema import validate_manifest
from app.v3.storage_fullness_publication import _fullness_from_context, build_fullness_report
from tests.v3.test_native_read_context_fixtures import NativeCase, forbid_engine, native_case

__all__ = ["native_case"]


class IntegerAlias(int):
    pass


class RecordAlias(dict[str, Any]):
    pass


@pytest.mark.parametrize("entry", ["validate", "fullness", "replay"])
def test_public_reader_rejects_alias_before_json_can_erase_its_type(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    forbid_engine(monkeypatch)
    wrong = deepcopy(native_case.run)
    if entry == "validate":
        wrong["outcome"]["events"] = tuple(wrong["outcome"]["events"])
    elif entry == "fullness":
        wrong["outcome"]["at_end"] = RecordAlias(wrong["outcome"]["at_end"])
    else:
        first = wrong["outcome"]["events"][0]
        first["tick"] = IntegerAlias(first["tick"])
    assert canonical_bytes(wrong) == canonical_bytes(native_case.run)
    with pytest.raises(ValueError):
        if entry == "validate":
            validate_coordinator_run(wrong, inputs=native_case.inputs.frozen_bytes)
        elif entry == "fullness":
            build_fullness_report(wrong, inputs=native_case.inputs.frozen_bytes)
        else:
            replay_coordinator(wrong, inputs=native_case.inputs.frozen_bytes, tick=0)


def test_context_keeps_the_validated_snapshot_after_caller_mutation(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbid_engine(monkeypatch)
    caller = deepcopy(native_case.run)
    before = canonical_bytes(caller)
    context = _validate_native(caller, inputs=native_case.inputs.frozen_bytes)
    caller["outcome"]["events"].clear()
    caller["metrics"].clear()
    caller["run_id"] = "0" * 64
    detached = context.run()
    detached["outcome"]["at_end"]["tick"] = -1
    report = _fullness_from_context(context)
    assert report["native_run_sha256"] == sha256(before).hexdigest()
    assert report["source_run_id"] == native_case.run["run_id"]
    assert context.run_bytes == canonical_bytes(context.run()) == before
    assert len(context.outcome.events) == len(native_case.run["outcome"]["events"])


def test_repeated_backward_context_seek_uses_fresh_journal_state(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbid_engine(monkeypatch)
    context = _validate_native(native_case.run, inputs=native_case.inputs.frozen_bytes)
    outcome = context.outcome
    horizon = outcome.at_horizon.tick
    first = _replay_context(context, horizon)
    assert first == outcome.at_horizon
    assert _replay_context(context, 0) == next(p for p in outcome.checkpoints if p.tick == 0)
    assert _replay_context(context, outcome.at_end.tick) == outcome.at_end
    assert _replay_context(context, horizon) == first
    assert canonical_bytes(context.run()) == canonical_bytes(native_case.run)


def test_schema_valid_wrong_sequence_descriptor_fails_before_context_validation(
    native_case: NativeCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbid_engine(monkeypatch)
    root = tmp_path / "bundle"
    copytree(native_case.root / "run", root)
    manifest = parse_json((root / "manifest.json").read_bytes())
    manifest["event_chunks"][-1]["last_seq"] += 1
    validate_manifest(manifest)
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Descriptor/payload consistency must precede semantic admission")

    monkeypatch.setattr(coordinator_transport, "_validate_native", forbidden)
    with pytest.raises(ValueError, match="chunk observed sequence differs"):
        coordinator_transport.read_coordinator_run(root)
