# V3 analytical fixtures F1–F3

These pure functions implement section 8 of the adaptive V3 design brief at
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`. They use exact rational arithmetic, run without
the engine, and return analytical evidence rather than throughput or operational admission.
See [ADR 0029](adr/0029-v3-independent-analytical-fixtures.md).

## F1: the same port mix for both placements

```python
from fractions import Fraction as F
from app.v3.analytical_port_mix import PortMixFixture, compare_placements

fixture = PortMixFixture(
    slot_port_distances_m=((F(120), F(168), F(144)), (F(168), F(120), F(144))),
    sku_port_moves=((72, 18, 10), (18, 72, 10)),
)
result = compare_placements(fixture, baseline=(0, 1), candidate=(1, 0))
assert result.baseline_m == 26208
assert result.candidate_m == 31392
assert result.candidate_minus_baseline_m == 5184
```

There is one shared immutable fixture, so a placement comparison cannot silently substitute
another demand mix. Positive candidate-minus-baseline means worsening distance. Reversing the
mix before both evaluations reverses placement preference. A no-op yields zero difference.
The metric is `weighted_route_metres`, source kind `analytical_fixture`.

## F2: geometry and total mass

```python
from app.v3.analytical_capacity import BoxFixture, SlotFixture, evaluate_fixture_fit

box = BoxFixture((F("0.60"), F("0.40"), F("0.30")), F(8))
slot = SlotFixture((F("1.25"), F("0.45"), F("0.35")), F(15))
one = evaluate_fixture_fit(box, slot)
two = evaluate_fixture_fit(box, slot, quantity=2)
assert one.accepted
assert two.geometric_capacity == 2
assert two.gross_mass_kg == 16
assert two.reason == "OVERWEIGHT"
```

`reason` is one of `DESIGN_COMPATIBLE`, `DIMENSION_MISMATCH`, `OVERWEIGHT`,
`ORIENTATION_FORBIDDEN`, or `SLOT_CAPACITY`. Malformed physical inputs, counts or axis orders
raise `ValueError`. Provide `orientations=((0, 1, 2),)` for the fixture's identity orientation
alone; the default is the six axis permutations explicitly permitted by F2.

This evaluator handles only a uniform grid of identical boxes with zero clearance. It does not
authorize rotations of canonical production HUs, solve general mixed-orientation packing,
check actors/routes/module payload, or return operational admission. The production admission
module has separate ownership and semantics.

## F3: duration differs from labor

```python
from app.v3.analytical_labor import CrewFixture, TravelFixture, compare_crews

travel = TravelFixture((F(4), F(6), F(4)), F("1.4"))
light = CrewFixture(people=1, take_s=F(6), place_s=F(6))
heavy = CrewFixture(people=2, take_s=F(20), place_s=F(20))
result = compare_crews(travel, light, heavy)
assert result.baseline.elapsed_s == 32
assert result.baseline.labor_person_s == 32
assert result.candidate.elapsed_s == 60
assert result.candidate.labor_person_s == 120
assert result.elapsed_difference_s == 28
assert result.labor_difference_person_s == 88
```

The outbound detour is 14 m and return is another 14 m. At 1.4 m/s travel takes 20 s.
All members of the declared crew accompany the travel and participate in both handling phases;
F3's two-person rule is a synthetic fixture assumption, not a universal lifting standard.

## Validation

From `backend/`:

```bash
uv run pytest -q tests/v3/test_analytical_port_mix.py tests/v3/test_analytical_capacity.py tests/v3/test_analytical_labor.py
```

Physical scalar constructors require `Fraction`, not float. Use `Fraction("0.60")` to preserve
the exact decimal declaration. Immutable tuple inputs and strict integer counts are intentional.
These fixtures do not need network access, the large V3 source package, or shared V2 files.
