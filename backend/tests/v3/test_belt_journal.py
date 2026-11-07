"""Real source journal contains continuous movement and releases before conflicting starts."""

from app.v3.belt_engine import BeltEngine
from app.v3.belt_models import BeltPose
from app.v3.conveyor_models import ConveyorSource
from tests.v3.test_belt_runtime import full_route, job, source_catalog


def same_position(source: ConveyorSource, previous: BeltPose, current: BeltPose) -> bool:
    if previous.edge_id == current.edge_id:
        return previous.progress == current.progress
    return (
        previous.progress == 1
        and current.progress == 0
        and source.edges[previous.edge_id].target == source.edges[current.edge_id].source
    )


def test_source_journal_never_teleports_and_repeated_routes_preserve_input_order_independence() -> (
    None
):
    source = source_catalog()
    jobs = (job("A", full_route(), "PK06"), job("B", ("v3:conv:entry-arc",)))
    first = BeltEngine(source, jobs).run(100_000_000, 200_000_000)
    second = BeltEngine(source, tuple(reversed(jobs))).run(100_000_000, 200_000_000)
    assert first == second
    last: dict[str, BeltPose] = {}
    owned: dict[str, str] = {}
    for event in first.events:
        if event.kind == "leases_acquired":
            for resource in event.resources:
                assert resource not in owned
                owned[resource] = event.job_id
        elif event.kind == "leases_released":
            for resource in event.resources:
                assert owned.pop(resource) == event.job_id
        elif event.kind.endswith("_started") and event.pose is not None:
            if event.job_id in last:
                assert same_position(source, last[event.job_id], event.pose)
            assert event.planned_end_tick is not None and event.planned_end_tick > event.tick
        elif event.kind.endswith("_completed") and event.pose is not None:
            last[event.job_id] = event.pose
    assert owned == {}
