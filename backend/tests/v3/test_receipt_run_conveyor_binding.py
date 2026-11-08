"""The shared engine cannot execute a different conveyor under already frozen input identity."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from app.v3.flow_profile_wire import record
from app.v3.receipt_run_execute import simulate_receipt
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_receipt_run_fixtures import sample


@pytest.mark.parametrize("forgery", ["speed", "fraction_dict", "document_bytes"])
def test_wrong_conveyor_is_rejected_before_output_and_constructor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    inputs, _ = sample()
    conveyor = receipt_conveyor()
    if forgery == "speed":
        conveyor = replace(conveyor, speed_m_s=conveyor.speed_m_s + Fraction(1, 100))
    elif forgery == "fraction_dict":
        conveyor = replace(conveyor)
        object.__setattr__(conveyor, "speed_m_s", record(conveyor.speed_m_s))
    else:
        conveyor = replace(
            conveyor,
            document=replace(
                conveyor.document, canonical_bytes=conveyor.document.canonical_bytes + b" "
            ),
        )

    def forbidden_constructor(*args: object) -> None:
        raise RuntimeError("mismatched conveyor reached engine construction")

    monkeypatch.setattr("app.v3.receipt_run_execute.ReceiptFlowEngine", forbidden_constructor)
    with pytest.raises(ValueError):
        simulate_receipt(inputs, conveyor, tmp_path / "out")
    assert not (tmp_path / "out").exists()
