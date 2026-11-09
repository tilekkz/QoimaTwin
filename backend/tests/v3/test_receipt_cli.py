"""The receipt command rejects malformed inputs before launching the shared engine."""

import hashlib
import json
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3 import cli_receipt
from app.v3.conveyor_models import ConveyorSource
from app.v3.interface import Json
from app.v3.receipt_profile import CompiledReceiptProfile
from tests.v3.test_receipt_profile_fixtures import receipt_choices


def test_file_loader_binds_declared_receipt_without_crediting_future_stock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "profile.json"
    profile.write_bytes(canonical_bytes(receipt_choices()))
    output = tmp_path / "out"
    calls: list[str] = []

    def observe(inputs: CompiledReceiptProfile, conveyor: ConveyorSource, out: Path) -> Json:
        frozen = json.loads(inputs.frozen_bytes)
        assert inputs.input_hash == hashlib.sha256(inputs.frozen_bytes).hexdigest()
        assert len(inputs.profile.flow.stock.units) == 12256
        assert len(inputs.profile.flow.stock.containers) == 530
        assert frozen["initial_inventory"]["registered_receipts"] == []
        assert frozen["initial_inventory"]["claims"] == []
        assert inputs.profile.receipts[0].definition.quantity_units == 24
        assert out == output and not out.exists()
        calls.append(inputs.input_hash)
        return {"status": "partial", "capabilities": {"full_v3_warehouse": False}}

    monkeypatch.setattr(cli_receipt, "simulate_receipt", observe)
    result = cli_receipt.simulate_receipt_file(Path("data/v3-proposal"), profile, output)
    assert result["status"] == "partial" and len(calls) == 1


@pytest.mark.parametrize("malformed", ["duplicate", "boolean_tick"])
def test_malformed_receipt_profile_never_launches_or_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: str
) -> None:
    profile = tmp_path / "profile.json"
    value = receipt_choices()
    value["horizon_tick"] = True
    raw = b'{"schema_id":1,"schema_id":2}' if malformed == "duplicate" else canonical_bytes(value)
    profile.write_bytes(raw)
    output = tmp_path / "out"

    def forbidden(inputs: CompiledReceiptProfile, conveyor: ConveyorSource, out: Path) -> Json:
        pytest.fail("invalid receipt choices must reject before execution")

    monkeypatch.setattr(cli_receipt, "simulate_receipt", forbidden)
    with pytest.raises(ValueError):
        cli_receipt.simulate_receipt_file(Path("data/v3-proposal"), profile, output)
    assert not output.exists()


def test_existing_output_rejects_before_even_loading_profile(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "keep").write_bytes(b"original")
    with pytest.raises(ValueError, match="empty"):
        cli_receipt.simulate_receipt_file(tmp_path / "absent", tmp_path / "absent.json", output)
    assert (output / "keep").read_bytes() == b"original"
