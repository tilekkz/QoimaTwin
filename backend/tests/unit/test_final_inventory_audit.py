"""The final independent audit catches corruption outside supported ledger mutations."""

from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine, RunStatus, Termination
from app.simulation.invariants import InvariantViolation
from app.simulation.scheduler import Phase
from tests.builders import run_inputs, scenario


def test_final_full_audit_checks_an_untouched_sku(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)
    ledger = engine.ctx.ledger
    holding = sorted(ledger._balances)[0]

    def corrupt_without_public_mutation() -> None:
        ledger._balances[holding] += 1

    engine.ctx.sched.schedule(1, Phase.COMPLETION, corrupt_without_public_mutation)
    with pytest.raises(InvariantViolation, match=holding.sku_id):
        engine.run()
    outcome = engine.last_outcome
    assert outcome is not None
    assert outcome.status is RunStatus.FAILED
    assert outcome.termination_reasons[0] is Termination.ERROR
