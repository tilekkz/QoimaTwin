"""Hand whole traces use prewritten runtime arithmetic, never source timing as an oracle."""

from functools import cache

from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_flow_models import WholeFlowOutcome
from app.v3.whole_run_inputs import WholeRunInputs, freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile
from tests.v3.test_whole_flow_shared_fixtures import standard_receipt_chain


@cache
def sample(
    future: bool = False, horizon: int = 100 * SECOND, end: int = 200 * SECOND
) -> tuple[WholeRunInputs, WholeFlowOutcome]:
    profile = standard_receipt_chain() if future else whole_hand_profile()
    conveyor = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, horizon, end)
    return inputs, WholeFlowEngine(profile, conveyor).run(horizon, end)
