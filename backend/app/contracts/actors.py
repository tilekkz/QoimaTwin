"""Actor registry contract (contracts/actors.example.json)."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import FrozenModel, NonEmptyStr, Vec3

Role = Literal["picker", "packer", "receiver", "shipper", "forklift_driver"]


class Actor(FrozenModel):
    actor_id: NonEmptyStr
    role: Role
    initial_pos: Vec3
    home_node_id: NonEmptyStr | None = None
    pack_id: NonEmptyStr | None = None
    vehicle_id: NonEmptyStr | None = None


class Vehicle(FrozenModel):
    vehicle_id: NonEmptyStr
    driver_actor_id: NonEmptyStr
    graph_id: Literal["inbound", "outbound"]


class ActorRegistry(FrozenModel):
    schema_version: Literal["2.0"]
    layout_version: NonEmptyStr
    actors: tuple[Actor, ...]
    vehicles: tuple[Vehicle, ...]

    def by_role(self, role: Role) -> tuple[Actor, ...]:
        return tuple(sorted((a for a in self.actors if a.role == role), key=lambda a: a.actor_id))
