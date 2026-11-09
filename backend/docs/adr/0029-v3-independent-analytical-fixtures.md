# ADR 0029: Independent V3 analytical fixtures

Status: accepted for the analytical fixture layer.

## Context

The adaptive V3 design brief section 8 defines three hand-checkable fixtures: weighted port
mix, independent geometric and mass constraints, and elapsed time versus person labor.
These are synthetic analytical examples. They are not a warehouse scenario, a production
admission decision, a forecast uplift claim or an engine benchmark.

Source revision: `tilekkz/QoimaTwin@22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`,
`docs/adaptive-v3/brief/02_DESIGN_V3.md`, section 8. Later checked revision
`4cfccae9dddb13559c5e891cfdf1f57dcdf9e289` does not change that brief or the proposal inputs.

## Decision

Implement the fixtures as pure functions under `app/v3/analytical_*.py`, independently of
the DES, typed production bundle and admission implementation. All physical scalars use exact
`Fraction` values; counts and indices require actual integers, excluding booleans. Frozen
dataclasses and tuple inputs prevent comparisons from changing shared assumptions.

F1 evaluates both placements against one immutable matrix of slot-to-port distances and
SKU-to-port move counts. Slots are distinct. The result is weighted route metres only.
`candidate_minus_baseline_m > 0` means more distance, not an improvement. Its 5184 m difference
is not net labor or profit; relocation, full jobs and resource scheduling are outside F1.

F2 is explicitly a zero-clearance, identical-box, uniform axis-aligned grid fixture. It permits
the six axis permutations declared for this hypothetical case, not arbitrary continuous tilt,
mixed-orientation bin packing or production cargo rotations. Failure reasons are deterministic:
no allowed orientation, no single-box dimensional fit, quantity beyond geometric grid capacity,
then total gross mass beyond payload. A positive result is `DESIGN_COMPATIBLE`, never operational
admission. Production cargo's identity-upright restriction remains separate and unchanged.

F3 takes a declared allowed outbound route and its reverse return. It is not a shortest-path
algorithm: the hand fixture supplies the rack-avoiding 4+6+4 m route. Every crew member travels
both legs and participates in both sequential handling operations. Thus person-seconds equal
crew size times elapsed seconds. This assumption belongs to F3, not to every production job.

## Validation and consequences

Tests contain literal hand expectations from the brief: 26208/31392/5184 m; geometric fit with
8/16 kg against 7/15 kg limits; 32/60 elapsed seconds and 32/120 person-seconds. Expected values
are not captured from the engine or derived from a stored solver result. Tests also check no-op,
predeclared reversed port mix, exact rational boundaries, invalid counts and forbidden rotations.

The production admission layer may later be cross-checked against these fixtures through an
explicit adapter. It must not import this deliberately limited F2 evaluator as a complete cargo,
slot, handler, route, staging or resource admission policy. Existing V2 schemas and analytical
timeline are untouched. Result provenance remains `analytical_fixture`.
