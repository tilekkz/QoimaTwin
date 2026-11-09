# 0026. V3 duration quantization and directed candidate graphs

Status: accepted for the isolated V3 runtime primitives; operational scenario and resource
scheduling remain separate decisions. Source: adaptive V3 proposal at
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`. Existing V2 contracts and time grids are unchanged.

## Context

V3 conveyor speed is 0.55 m/s and its entry arc length is 1.9634954084936207 m. Exact conversion
of the declared decimals yields 19634954084936207/5500000000000000 seconds. The V2 LCM clock
would require 5,500,000,000,000,000 ticks/s, exceeding its 1e9 limit. V3 also supplies compiled
directed walk/vehicle arcs, while the V2 path loader automatically adds a reverse edge.

## Decision

V3 operation durations use 1,000,000 integer ticks per second. Interpret decimal inputs exactly,
calculate a complete primitive duration, then take its ceiling to microseconds. Each positive
operation gets at least one tick and finishes no earlier than its declared duration. Its added
rounding error is less than one microsecond. Zero remains zero for explicitly instantaneous
work. Reject negative/nonfinite values and booleans. Compute travel as exact length/speed before
one ceiling; speed must be positive. Do not first round length, speed or each arithmetic term.

The entry arc therefore takes 3,569,992 ticks; the stopped 0.8 s pivot takes 800,000 ticks. Separate
operations round separately: three one-third-second operations take 1,000,002 ticks in total.
The execution profile must fix operation boundaries consistently across compared variants.
This policy does not define arrival generation, timestamp rounding, window endpoint equality,
service profiles or the transition from geometric proposals to operational admission.

The versioned execution identity must include ticks_per_second=1000000 and
duration_rounding=ceil_each_positive_operation. Source geometry and declared service assumptions
remain immutable inputs; integer event timestamps are the authoritative replay clock. The
separate arrival/window policy must be explicit when an execution profile is introduced.

Load `walk_graph` and `vehicle_graph` from the already compiled `layout-links-v3.json`. Preserve
graph-qualified node identity and each explicit directed arc. Never infer reverse arcs. Raw
L06/L07 graphs do not include all later connectors/splits and are not interchangeable inputs.
Validate unique nonempty identifiers, endpoint existence, finite XYZ coordinates, positive
length/cost, equality of declared distance cost and length, permission lists and clearances.
An explicit unsupported-cargo flag cannot coexist with nonempty cargo permissions; malformed
support flags also reject at the boundary.
This structural validation does not recompute geometric collision or loading proofs.

Routing filters requested mode, geometry profile, cargo class, width and height before scoring.
Missing permission or missing requested scalar clearance fails that filter; it is never treated
as unlimited. In particular, a bare-only arc cannot carry cargo just because its endpoint is
reachable. Profile aliases/containment must already be explicitly represented by the source;
the primitive invents no permission expansion. Scalar width absence can coexist with a separate
source sweep proof, but this primitive cannot infer an unknown width from that proof.

Directed Dijkstra runs lazily for the requested source/target, rather than eagerly materializing
all source trees. Outgoing arcs are sorted by target ID and arc ID; equal distances retain the
first stable predecessor, with queue ties ordered by node ID. Inputs are immutable. A connected
self route has zero length; unreachable or an empty graph returns no candidate. An unknown
endpoint in a nonempty graph is an input error. Neither case creates a straight-line fallback.

The output type is CandidateRoute. An unfiltered route is geometry-only; a filtered candidate
still does not grant operational admission. The future scheduler must separately validate actual
handling/support evidence, worker skills, equipment availability, resource leases and complete
load geometry. No worker, vehicle, HU, arrival or completed operation is created here.

## Validation and consequences

Manual tests cover exact decimal/fraction ceilings, invalid scalars, directed/no-path semantics,
stable ties and filtering a cheap incompatible shortcut before route cost. A property test checks
the mathematical non-early/less-than-one-tick bound. Compiled-source tests reject malformed IDs,
nonfinite positions, forged costs and invalid permission lists. Real pinned graph validation is
recorded separately from these independent numerical oracles; its route output is not converted
into expected acceptance numbers.

This is a prerequisite for V3 execution, not a V3 engine run. Port arrivals/windows, whole-HU
versus unit picking, operational stock/packing, finite cart/tote resources, conveyor footprint and
exclusive curve/spur scheduling, role transitions and A/B calendars remain explicit later work.

Sources: [conveyor](https://github.com/tilekkz/QoimaTwin/blob/22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec/docs/v3/contract-proposals/conveyor-v3.json),
[compiled links](https://github.com/tilekkz/QoimaTwin/blob/22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec/docs/v3/contract-proposals/layout-links-v3.json),
[pedestrian rules](https://github.com/tilekkz/QoimaTwin/blob/22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec/docs/v3/contract-proposals/pedestrian-graph-v3.json),
[vehicle handling](https://github.com/tilekkz/QoimaTwin/blob/22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec/docs/v3/contract-proposals/vehicle-handling-v3.json).
