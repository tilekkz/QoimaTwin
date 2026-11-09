"""Simulation defaults contract (contracts/simulation_defaults.json)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt

from app.contracts.base import FrozenModel, NonEmptyStr


class Staffing(FrozenModel):
    picker: PositiveInt
    packer: PositiveInt
    receiver: PositiveInt
    shipper: PositiveInt
    forklift_driver: PositiveInt

    def total(self) -> int:
        return self.picker + self.packer + self.receiver + self.shipper + self.forklift_driver


class LoadProfile(FrozenModel):
    orders_per_hour: PositiveInt
    preview_horizon_s: PositiveInt
    shift_horizon_s: PositiveInt


class Profiles(FrozenModel):
    large_normal: LoadProfile = Field(alias="large-normal")
    large_peak: LoadProfile = Field(alias="large-peak")


class Policies(FrozenModel):
    inventory_shortage: Literal["unfulfilled_inventory_no_partial_reservation"]
    order_dispatch: Literal["eligible_fifo_by_arrival_and_order_id"]
    picker_home: Literal["four_per_induction_fixed"]
    pack_target: Literal["min_reserved_wip_then_pack_id"]
    conveyor_merge: Literal["round_robin"]
    conveyor_transfer: Literal["one_hop_per_tick_atomic"]
    empty_tote_return: Literal["instant_virtual_at_pack_complete"]
    staff_breaks: Literal["not_modelled"]
    replenishment: Literal["not_modelled"]
    truck_capacity: Literal["external_unbounded"]


class SimulationConfig(FrozenModel):
    schema_version: Literal["2.0"]
    config_version: NonEmptyStr
    layout_version: NonEmptyStr
    staffing: Staffing
    walk_speed_mps: PositiveFloat
    pick_base_s: NonNegativeFloat
    pick_per_unit_s: NonNegativeFloat
    handoff_s: NonNegativeFloat
    pack_base_s: NonNegativeFloat
    pack_per_line_s: NonNegativeFloat
    pack_per_unit_s: NonNegativeFloat
    conveyor_cell_m: PositiveFloat
    conveyor_speed_mps: PositiveFloat
    conveyor_tick_s: PositiveFloat
    pack_buffer_capacity: PositiveInt
    shipping_buffer_capacity: PositiveInt
    totes_total: PositiveInt
    receiving_queue_capacity: PositiveInt
    reserve_staging_capacity: PositiveInt
    sealed_pallet_queue_capacity: PositiveInt
    receiving_pallets_per_hour: PositiveInt
    receive_service_s: NonNegativeFloat
    forklift_speed_mps: PositiveFloat
    forklift_pickup_s: NonNegativeFloat
    forklift_drop_s: NonNegativeFloat
    shipping_scan_s: NonNegativeFloat
    parcels_per_pallet: PositiveInt
    pallet_max_age_s: PositiveFloat
    open_pallet_count: Literal[1]
    relocation_take_or_place_s: NonNegativeFloat
    relocation_worker_count: Literal[1]
    ground_units_per_sku: PositiveInt
    reserve_bins_per_sku: PositiveInt
    reserve_units_per_bin: PositiveInt
    receipt_units_per_pallet: PositiveInt
    max_drain_s: PositiveFloat
    snapshot_interval_s: PositiveFloat
    chunk_duration_s: PositiveFloat
    profiles: Profiles
    policies: Policies
