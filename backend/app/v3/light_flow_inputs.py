"""Required finite handoff places and clock/route assumptions are checked before execution."""

from fractions import Fraction

from app.v3.belt_plan import valid_tick
from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_models import FlowProfile


def handoff_inputs(profile: FlowProfile, conveyor: ConveyorSource) -> None:
    _route_ends(profile, conveyor)
    margin = profile.path_clearance_m
    if type(margin) is not Fraction or margin < 0:
        raise ValueError("Explicit exact nonnegative path clearance required")
    if not valid_tick(profile.port.service_tick) or not profile.port.service_tick:
        raise ValueError("Positive integer port service duration required")
    previous_end = 0
    for start, end in profile.port.windows:
        if not valid_tick(start) or not valid_tick(end) or not previous_end <= start < end:
            raise ValueError("Port windows require ordered nonnegative integer bounds")
        previous_end = end
    if not profile.port.windows:
        raise ValueError("Explicit port windows required")
    picker = next(a for a in profile.actors if a.actor_id == profile.picker_id)
    if picker.home != profile.cart.home:
        raise ValueError("Bounded picker must initially share the declared cart home")
    _owners(profile)


def _route_ends(profile: FlowProfile, source: ConveyorSource) -> None:
    route = profile.belt_route
    if not route or any(identity not in source.edges for identity in route):
        raise ValueError("Explicit known source belt route required")
    if (
        source.edges[route[0]].source != source.edges["v3:conv:feed"].source
        or source.edges[route[-1]].target != source.edges["v3:conv:main-tail"].target
    ):
        raise ValueError("Connected workflow must use actual source intake and output endpoints")


def _owners(profile: FlowProfile) -> None:
    owners = {o.owner_id: o for o in profile.owners}
    required = (
        (profile.carrier_pool_owner, "material"),
        (profile.package_pool_owner, "material"),
        (profile.cart.owner_id, "workstation"),
        ("actor:" + profile.picker_id, "workstation"),
        ("actor:" + profile.shipper_id, "workstation"),
        (profile.station.bench_owner, "workstation"),
        (profile.station.empty_owner, "workstation"),
        (profile.shipped_owner, "shipped"),
        *(("belt:" + order.order_id, "workstation") for order in profile.orders),
    )
    if len({key for key, _ in required}) != len(required):
        raise ValueError("Physical handoff owners must be distinct")
    for key, kind in required:
        if key not in owners or owners[key].kind != kind:
            raise ValueError("Missing or wrongly typed physical handoff owner")
    exclusive = {
        profile.cart.owner_id,
        profile.station.bench_owner,
        "actor:" + profile.picker_id,
        "actor:" + profile.shipper_id,
    }
    exclusive.update("belt:" + o.order_id for o in profile.orders)
    if any(owners[key].capacity != 1 for key in exclusive):
        raise ValueError("Cart, actor, bench and carrier handoff positions are capacity one")
