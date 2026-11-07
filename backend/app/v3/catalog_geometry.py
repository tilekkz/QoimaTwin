"""Exact signed-axis transforms for the four rotations declared by the V3 source."""

from fractions import Fraction
from math import pi

from app.v3.interface import Json, V3InterfaceError


def quarter_turn(yaw: float) -> tuple[int, int]:
    rotations = {0.0: (1, 0), pi / 2: (0, 1), pi: (-1, 0), 3 * pi / 2: (0, -1)}
    if yaw not in rotations:
        raise V3InterfaceError("initial module rotation is not a declared quarter turn")
    return rotations[yaw]


def floor_pose(placement: Json, module: Json) -> list[float]:
    x, _y, z = [Fraction(str(value)) for value in placement["centre_local_xyz_m"]]
    ox, oy, oz = [Fraction(str(value)) for value in module["world_pos"]]
    c, s = quarter_turn(module["yaw_rad"])
    return [
        float(ox + x * c + z * s),
        float(oy + Fraction(str(placement["bottom_y_m"]))),
        float(oz - x * s + z * c),
    ]


def hu_bounds(unit: Json) -> tuple[list[Fraction], list[Fraction]]:
    x, y, z = [Fraction(str(value)) for value in unit["pose"]["world_pos"]]
    width, height, depth = [Fraction(str(value)) for value in unit["dimensions_xyz_m"]]
    c, s = quarter_turn(unit["pose"]["yaw_rad"])
    half_x, half_z = (abs(c) * width + abs(s) * depth) / 2, (abs(s) * width + abs(c) * depth) / 2
    return [x - half_x, y, z - half_z], [x + half_x, y + height, z + half_z]
