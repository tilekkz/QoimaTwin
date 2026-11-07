"""Independent cell-overlap boundary and arc-envelope arithmetic."""

from fractions import Fraction as F

import pytest

from app.v3.belt_geometry import angular_halfspan, footprint
from app.v3.belt_models import BeltPose
from app.v3.belt_plan import compile_job
from app.v3.conveyor_models import ConveyorSource
from tests.v3.test_belt_runtime import job, source_catalog


@pytest.fixture(scope="module")
def source() -> ConveyorSource:
    return source_catalog()


def test_actual_cartesian_overlap_changes_at_front_and_tail_not_node_arrivals(
    source: ConveyorSource,
) -> None:
    identity = "v3:conv:PK01:main-approach"
    payload = job("A", (identity,)).payload
    cases = [
        (F(0), {"V3-C-MAIN-055", "V3-C-MAIN-056"}),
        (F(".02"), {"V3-C-MAIN-056"}),
        (F(".08"), {"V3-C-MAIN-056"}),
        (F(".09"), {"V3-C-MAIN-056", "V3-C-MAIN-057"}),
    ]
    for progress, expected in cases:
        assert footprint(source, payload, BeltPose(identity, progress, F(1))) == expected


def test_long_edge_substeps_never_reserve_the_whole_ten_metre_segment(
    source: ConveyorSource,
) -> None:
    steps = compile_job(source, job("A", ("v3:conv:PK01:main-approach",)))
    assert len(steps) == 21  # two .2m ends, ten .6m gaps, nine .4m tail-clear segments
    assert sum(step.duration_tick for step in steps) == 18_181_819
    assert all(step.duration_tick > 0 for step in steps)
    assert all(len([r for r in step.resources if r.startswith("cell:")]) <= 2 for step in steps)


def test_curve_angular_projection_releases_feed_and_acquires_main_at_real_ends(
    source: ConveyorSource,
) -> None:
    identity = "v3:conv:entry-arc"
    payload = job("A", (identity,)).payload
    half = angular_halfspan(source, payload)
    assert F(".207") < half < F(".208")  # atan(.4/(2*1.25-.6))=atan(4/19)
    expected = [
        (F(0), {"V3-C-FEED", "V3-C-ARC-00"}),
        (F(1, 2), {"V3-C-ARC-01", "V3-C-ARC-02"}),
        (F(1), {"V3-C-ARC-03", "V3-C-MAIN-000"}),
    ]
    for progress, cells in expected:
        assert footprint(source, payload, BeltPose(identity, progress, progress)) == cells
