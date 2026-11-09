"""Use the same frozen execution capability gate when validating serialized inputs."""

from app.v3.execution_types import BoundGraph
from app.v3.execution_validate import validate_profile
from app.v3.interface import Json
from app.v3.run_decode import profile_from_wire
from app.v3.runtime_graph import DirectedGraph


def validate_profile_wire(run: Json, graph: DirectedGraph) -> None:
    profile = profile_from_wire(run["profile"])
    document = run["graph_document"]
    if not document.get("connector_provenance"):
        raise ValueError("manual graph lacks declared connector provenance")
    bound = BoundGraph(graph, document["layout_version"], profile.graph_sha256)
    validate_profile(profile, bound)
    if any(job.arrival_tick >= run["at_horizon"]["tick"] for job in profile.jobs):
        raise ValueError("manual timed arrival must precede the horizon")
