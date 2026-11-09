"""Conservative exact swept rectangles for explicit synthetic local connectors."""

from fractions import Fraction
from itertools import pairwise
from typing import Any

from app.v3.materialize import number
from app.v3.profile_models import BufferChoice

type Rect = tuple[Fraction, Fraction, Fraction, Fraction]
type Point = tuple[Fraction, Fraction]


def overlaps(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def segment_bounds(a: Point, b: Point, radius: Fraction) -> Rect:
    if a == b or (a[0] != b[0] and a[1] != b[1]):
        raise ValueError("connector requires nonzero axis-aligned explicit legs")
    return (
        min(a[0], b[0]) - radius,
        min(a[1], b[1]) - radius,
        max(a[0], b[0]) + radius,
        max(a[1], b[1]) + radius,
    )


def rectangle(row: Any) -> Rect:
    lo, hi = row["min"], row["max"]
    return Fraction(str(lo[0])), Fraction(str(lo[1])), Fraction(str(hi[0])), Fraction(str(hi[1]))


def contains(outer: Rect, inner: Rect) -> bool:
    return all(
        (outer[0] <= inner[0], outer[1] <= inner[1], outer[2] >= inner[2], outer[3] >= inner[3])
    )


def validate_buffer_separation(choices: tuple[BufferChoice, ...]) -> None:
    for choice in choices:
        bounds = rectangle({"min": choice.bounds_xz[:2], "max": choice.bounds_xz[2:]})
        if not choice.place_id.strip():
            raise ValueError("buffer identity must be nonempty")
        points = tuple(
            (number(x, positive=False), number(z, positive=False)) for x, z in choice.path_xz
        )
        for other in choices:
            if other is choice:
                continue
            obstacle = rectangle({"min": other.bounds_xz[:2], "max": other.bounds_xz[2:]})
            if overlaps(bounds, obstacle) or any(
                overlaps(segment_bounds(a, b, Fraction("0.4")), obstacle)
                for a, b in pairwise(points)
            ):
                raise ValueError("finite buffers or their access paths overlap another buffer")


def validate_connector(
    choice: BufferChoice, zones: Any, modules: Any, service: Point
) -> tuple[Point, ...]:
    x0, z0, x1, z1 = (number(v, positive=False) for v in choice.bounds_xz)
    bounds = x0, z0, x1, z1
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError("buffer bounds must have positive extent")
    selected = [z for z in zones["zones"] if z["zone_id"] == choice.zone_id]
    if len(selected) != 1 or selected[0]["kind"] != "staging":
        raise ValueError("unknown staging zone")
    if not contains(rectangle(selected[0]["floor_bounds_xz_m"]), bounds):
        raise ValueError("buffer leaves its finite staging zone")
    points = tuple(
        (number(x, positive=False), number(z, positive=False)) for x, z in choice.path_xz
    )
    center = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
    if len(points) < 2 or points[0] != service or points[-1] != center:
        raise ValueError("connector must bind actual service to actual buffer centre")
    for overlay in zones["port_approach_context"]:
        if overlaps(bounds, rectangle(overlay["keep_clear_overlay_xz_m"])):
            raise ValueError("buffer occupies keep-clear approach")
    for a, b in pairwise(points):
        _clear_segment(segment_bounds(a, b, Fraction("0.4")), choice.zone_id, zones, modules)
    return points


def _clear_segment(swept: Rect, zone_id: str, zones: Any, modules: Any) -> None:
    if not contains((Fraction(0), Fraction(0), Fraction(144), Fraction(72)), swept):
        raise ValueError("connector swept envelope leaves building")
    for zone in zones["zones"]:
        if (
            zone["kind"] != "circulation"
            and zone["zone_id"] != zone_id
            and overlaps(swept, rectangle(zone["floor_bounds_xz_m"]))
        ):
            raise ValueError("connector swept envelope enters forbidden zone")
    for module in modules["modules"]:
        box = module["outer_bounds_world"]
        rack = rectangle(
            {"min": [box["min"][0], box["min"][2]], "max": [box["max"][0], box["max"][2]]}
        )
        if overlaps(swept, rack):
            raise ValueError("connector swept envelope intersects rack")
