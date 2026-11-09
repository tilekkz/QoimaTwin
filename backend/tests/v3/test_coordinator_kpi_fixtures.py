"""Pure hand observations for reducers; not fabricated native-publication evidence."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.belt_models import BeltSnapshot
from app.v3.coordinator_models import (
    CoordinatorOutcome,
    CoordinatorProfile,
    CoordinatorSnapshot,
    RoleExposure,
)
from app.v3.light_flow_models import (
    FlowCartView,
    FlowEvent,
    FlowOperation,
    FlowOrderView,
    FlowWorker,
)
from app.v3.runtime_graph import CandidateRoute
from app.v3.stock_ledger import StockLedger
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_profile

S = 1_000_000


def profile() -> CoordinatorProfile:
    value = staffing_profile()
    flow = replace(hand_profile(orders=2), orders=())
    return replace(
        value,
        intents=(),
        world=replace(
            value.world,
            receipts=replace(value.world.receipts, flow=flow, receipts=()),
            orders=(),
        ),
    )


def point(
    value: CoordinatorProfile, tick: int, ledger: StockLedger | None = None
) -> CoordinatorSnapshot:
    flow = value.world.receipts.flow
    stock = ledger or StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    workers = tuple(FlowWorker(a.actor_id, a.home, None, None, None, 0, 0) for a in flow.actors)
    orders = tuple(FlowOrderView(o.order_id, "waiting", None, None) for o in flow.orders)
    cart = FlowCartView(flow.cart.cart_id, flow.cart.home, None, None)
    return CoordinatorSnapshot(
        tick,
        stock.snapshot(),
        stock.balance(),
        workers,
        orders,
        (),
        BeltSnapshot(tick, 0, 0, (), (), 0),
        -1,
        cart,
        stock.inventory_snapshot(),
        (),
        (),
        (),
        (),
        (),
        RoleExposure((), 0, 0),
        carts=(cart,),
    )


def outcome(value: CoordinatorSnapshot, events: tuple[FlowEvent, ...] = ()) -> CoordinatorOutcome:
    return CoordinatorOutcome("partial", events, value, value, observation_end_tick=value.tick)


def move(seq: int, start: int, end: int, metres: int, *, actor: str = "P01") -> FlowEvent:
    route = CandidateRoute("hand", ("A", "B"), ("AB",), F(metres), F(metres))
    operation = FlowOperation("travel", "O1", start, end, "A", "B", route)
    return FlowEvent(seq, start, "operation_started", "O1", actor, operation)
