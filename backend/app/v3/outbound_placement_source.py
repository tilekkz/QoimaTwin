"""Fresh source geometry plus explicit customer buffer; no substitute common profile."""

from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

from app.v3.execution_types import PlaceSpec
from app.v3.input_models import Port, V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.outbound_placement_models import (
    PlacementCandidate,
    PlacementChoices,
    PlacementCostFacts,
    PlacementCustomer,
)
from app.v3.outbound_placement_validation import buffer_choice
from app.v3.outbound_stock_models import BoundOutboundStock, StockHU
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.profile_build import document
from app.v3.profile_connectors import add_connectors
from app.v3.profile_models import BufferChoice
from app.v3.runtime_graph import DirectedGraph
from app.v3.runtime_graph_source import compiled_graph
from app.v3.runtime_time import operation_ticks
from app.v3.whole_profile_geometry import project_whole_manual_cargo
from app.v3.workload_models import WorkloadJob, WorkloadSource


@dataclass(frozen=True, slots=True)
class _Connector:
    proposal_id: str
    buffers: tuple[BufferChoice, ...]


def source_bundle() -> V3Bundle:
    return load_v3_bundle(Path(__file__).resolve().parents[2] / "data/v3-proposal")


def _customer_port(
    bundle: V3Bundle, customer: PlacementCustomer, hu: StockHU, offer: WorkloadJob
) -> Port:
    require(
        (customer.offer_id, customer.port_id) == (offer.job_id, offer.port_id),
        "CUSTOMER_BINDING_MISMATCH",
    )
    ports = [p for p in bundle.ports if p.port_id == customer.port_id and p.direction == "outbound"]
    require(len(ports) == 1, "UNKNOWN_CUSTOMER_PORT")
    port = ports[0]
    services = dict(port.seconds_by_archetype)
    require(
        hu.archetype_id in port.allowed_cargo_archetype_ids and hu.archetype_id in services,
        "UNSUPPORTED_CUSTOMER_PROCESS",
    )
    require(
        customer.service_ticks == operation_ticks(F(str(services[hu.archetype_id]))),
        "SOURCE_SERVICE_DURATION_MISMATCH",
    )
    return port


def _buffer_graph(
    bundle: V3Bundle,
    choices: PlacementChoices,
    customer: PlacementCustomer,
    hu: StockHU,
    dimensions: tuple[F, F, F],
) -> tuple[DirectedGraph, PlaceSpec]:
    choice = buffer_choice(customer)
    require(choice.port_id == customer.port_id, "CUSTOMER_BUFFER_PORT_MISMATCH")
    links = document(bundle, "layout-links-v3.json")
    place = add_connectors(bundle, _Connector(choices.policy_id, (choice,)), links)[0][1]
    require(
        hu.gross_mass_kg <= place.max_payload_kg
        and all(
            size + 2 * choices.path_clearance_m <= room
            for size, room in zip(dimensions, place.usable_dimensions_xyz_m, strict=True)
        ),
        "CUSTOMER_BUFFER_FIT",
    )
    project_whole_manual_cargo(links)
    return compiled_graph(links, "walk"), place


def customer_facts(
    bundle: V3Bundle,
    stock: BoundOutboundStock,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
    hu: StockHU,
    offer: WorkloadJob,
) -> tuple[DirectedGraph, PlacementCostFacts]:
    return customer_source_facts(
        bundle, stock.inputs.scenario.baseline, choices, candidate, hu, offer
    )


def customer_source_facts(
    bundle: V3Bundle,
    source: WorkloadSource,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
    hu: StockHU,
    offer: WorkloadJob,
) -> tuple[DirectedGraph, PlacementCostFacts]:
    """Source template seam for already authenticated C11 or forecast planning inputs."""
    customer = candidate.customer
    require(customer is not None, "MISSING_CUSTOMER_BINDING")
    assert customer is not None
    port = _customer_port(bundle, customer, hu, offer)
    template = next(t for t in source.templates if t.sku_id == hu.sku_id)
    graph, place = _buffer_graph(bundle, choices, customer, hu, template.dimensions_xyz_m)
    nodes = {
        s["slot_id"]: s["service_node_id"]
        for s in document(bundle, "storage-slots-v3.json")["slots"]
    }
    facts = PlacementCostFacts(
        candidate.actor,
        nodes[candidate.from_slot_id],
        nodes[candidate.to_slot_id],
        place.node_id,
        port.service_node_id,
        hu.archetype_id,
        template.dimensions_xyz_m,
        candidate.take_ticks,
        candidate.place_ticks,
        customer.pickup_ticks,
        customer.place_ticks,
        customer.service_ticks,
        choices.min_width_m,
        choices.min_height_m,
        choices.path_clearance_m,
    )
    return graph, facts
