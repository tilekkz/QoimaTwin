"""Hand cart release122 precedes picker home126, including backward repeated seek."""

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_multi_release import distant_picker_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def _released(state: CoordinatorSnapshot, paid: int) -> None:
    carts = {cart.cart_id: cart for cart in state.carts}
    picker = next(worker for worker in state.workers if worker.actor_id == "P02")
    assert set(carts) == {"CART01", "CART02"}
    assert carts["CART02"].node == "H"
    assert carts["CART02"].order_id is None and carts["CART02"].operation is None
    assert dict(state.cart_releases) == {"O2": 122 * SECOND}
    assert picker.order_id == "O2" and picker.node is None
    assert picker.operation is not None and picker.operation.kind == "picker_return"
    assert picker.operation.cart_id is None
    assert (picker.operation.start_tick, picker.operation.planned_end_tick) == (
        122 * SECOND,
        126 * SECOND,
    )
    assert picker.paid_ticks == paid


def test_seek_keeps_released_cart_separate_from_open_picker_return() -> None:
    profile, source = distant_picker_profile(), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, source, 128 * SECOND, 128 * SECOND)
    actual = CoordinatorEngine(profile, source).run(128 * SECOND, 128 * SECOND)
    run = build_coordinator_run(inputs, actual)
    before = canonical_bytes(run)
    late = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=125 * SECOND)
    released = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=122 * SECOND)
    earlier = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=122 * SECOND - 1)
    repeated = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=125 * SECOND)
    _released(late, 27 * SECOND)
    _released(released, 24 * SECOND)
    cart = next(c for c in earlier.carts if c.cart_id == "CART02")
    picker = next(w for w in earlier.workers if w.actor_id == "P02")
    assert cart.order_id == picker.order_id == "O2"
    assert cart.operation is not None and cart.operation.planned_end_tick == 122 * SECOND
    assert picker.operation is not None and picker.operation.cart_id == "CART02"
    assert picker.paid_ticks == 24 * SECOND - 1
    assert earlier.cart_releases == ()
    assert late == repeated and late.stock == released.stock == earlier.stock
    assert late.inventory == released.inventory == earlier.inventory
    assert canonical_bytes(run) == before
