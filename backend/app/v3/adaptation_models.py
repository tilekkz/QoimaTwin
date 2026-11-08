"""Immutable C11 planning records. Periods are unclocked; "_s" values are proxy route-seconds.

Nothing here is an executed move, paid relocation, engine event or operational admission.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True, slots=True)
class RouteDoc:
    graph: str
    from_node_id: str
    to_node_id: str
    arc_ids: tuple[str, ...]
    reported_length_m: float


@dataclass(frozen=True, slots=True)
class LegDoc:
    direction: str
    port_id: str
    reported_moves: float
    route: RouteDoc


@dataclass(frozen=True, slots=True)
class RowDoc:
    hu_id: str
    sku_id: str
    lot_id: str
    archetype_id: str
    quantity_units: int
    slot_id: str
    module_id: str
    orientation_id: str
    legs: tuple[LegDoc, ...]
    reported_cost_s: float


@dataclass(frozen=True, slots=True)
class TransferDoc:
    sequence: int
    hu_id: str
    sku_id: str
    archetype_id: str
    from_slot_id: str
    from_module_id: str
    to_slot_id: str
    to_module_id: str
    transport_tag: str
    handling_allowance_s: Fraction
    loaded: RouteDoc
    reverse: RouteDoc
    reported_relocation_s: float
    reported_gross_s: float
    reported_net_s: float


@dataclass(frozen=True, slots=True)
class ReportedSummary:
    """Source-reported floating diagnostics; never used to compute the comparison."""

    baseline_under_same_shifted_flow_cost_s: float
    adapted_under_same_shifted_flow_cost_s: float
    one_off_relocation_cost_s: float
    net_transport_cost_reduction_s: float
    relocation_count: int
    no_op: bool


@dataclass(frozen=True, slots=True)
class HorizonDoc:
    periods: int
    period_unit: str
    rows: tuple[RowDoc, ...]
    transfers: tuple[TransferDoc, ...]
    reported: ReportedSummary
    actual_engine_run: Literal[False]
    operational_admission: Literal[False]


@dataclass(frozen=True, slots=True)
class ExactRoute:
    graph: str
    from_node_id: str
    to_node_id: str
    arc_ids: tuple[str, ...]
    length_m: Fraction


@dataclass(frozen=True, slots=True)
class PlannedTransfer:
    """One planned (not executed) single-HU move in the disposable projection."""

    sequence: int
    hu_id: str
    archetype_id: str
    from_slot_id: str
    to_slot_id: str
    transport_tag: str
    loaded_route: ExactRoute
    reverse_route: ExactRoute
    relocation_proxy_s: Fraction
    gross_proxy_s: Fraction
    net_proxy_s: Fraction
    released_by_sequence: int | None


@dataclass(frozen=True, slots=True)
class InventoryTotals:
    handling_units: int
    units: int
    gross_mass_kg: Fraction


@dataclass(frozen=True, slots=True)
class PlanningComparison:
    periods: int
    period_unit: str
    no_op: bool
    transfers: tuple[PlannedTransfer, ...]
    baseline_proxy_s: Fraction
    adapted_proxy_s: Fraction
    relocation_proxy_s: Fraction
    net_proxy_s: Fraction
    inventory: InventoryTotals
    reported: ReportedSummary
    actual_engine_run: Literal[False] = False
    operational_admission: Literal[False] = False
