# ADR0037: pinned V3 conveyor source and static prerequisites

Status: accepted for the bounded backend proposal implementation; not a shared
contract amendment or a conveyor scheduling implementation.

## Context

The pinned V3 L08 source at22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec describes
34nodes,45 directed edges,90 physical cells,15 resource records and87 physical
modules. Its synthetic values are0.55m/s,0.8s transfer dwell,15kg gross ceiling,
0.60×0.40m maximum payload footprint and0.40m maximum height. Existing fourteen-
file V3 source ingestion deliberately does not include this conveyor document.

Source: `docs/v3/contract-proposals/conveyor-v3.json`, Git blob
`d1a97197713f53f883cf49dc60ec469f07f6ae05`, raw94202bytes, SHA256
`3bf8cb57e46f853921bcf322d939e61dfd32db96d4e46184db18923889d17612`.
L08 is a source geometry/policy proposal; it creates no actual throughput.

## Decision

Vendor the exact text as a separate immutable supplement under
`backend/data/v3-conveyor-proposal/`, with its own provenance. The existing V3
pin and provenance remain unchanged. `load_conveyor_source(bundle, supplement)`
requires the verified bundle's same source revision, exact reviewed metadata,
byte length and raw hash. No network or runtime source substitution occurs.

The adapter returns frozen typed maps for nodes, edges, cells, resources and
stations, exact Fraction parameters and an immutable full source document.
Ancillary module/handoff/appearance fields survive in that document; projecting
the operational subset does not manufacture an admission or scheduling claim.
Arc cells retain source angular intervals without inventing Cartesian centres
or lengths. Arc edges retain centre/radius/angles and their declared source length.
Duplicate IDs, bad references, unknown resource/path semantics and malformed
capacities fail. The untrusted structural decoder assigns no verified revision
or raw provenance and is separate from the pinned loader.

Resource interpretations are explicit:

- `V3_MAIN` is67 cells, capacity1 each, not a global exclusive reservation and
  not permission to place arbitrary67 overlapping payloads.
- The complete four-cell entry curve has shared capacity1.
- Feed and each of six T pads have capacity1.
- Each two-cell reversible spur has shared capacity1 through intake, work and
  return. Its reservation is not released merely when the front cell empties.
- Membership partitions all90cells exactly once:67+4+1+6+12. Physical-module
  and graph-edge counts are not capacities.

`edge_requirements(source, edge_id, overlapped_cell_ids)` validates an explicit
nonempty unique cell set including the bound edge's resource. It returns all
declared per-cell requirements and every intersected exclusive resource. Adjacent
resources may appear at seams. The caller must prove complete geometric/swept
overlap; this function does not calculate it or grant live availability. Static
requirements cannot be substituted for an atomic live scheduler reservation.

`ConveyorPayload` requires explicit identity, parent/source identity, body-axis
xyz dimensions, complete gross mass and orientation, using positive Fractions.
`admit_payload` permits only order_tote, sealed_parcel, SMALL_CARTON and
STANDARD_CARTON. Forbidden kinds remain forbidden with falsified small visual
dimensions. Only upright_xyz body orientation is supported; world heading changes
on the declared track are separate. Width/depth, height and mass use exact limits
without epsilon, resizing, axis permutation or omitted tare. This is dimensional
policy admission, not validation of a caller's declared physical measurements or
parent ledger ancestry. A future caller must bind those identities to actual state.

The global payload policy conservatively requires pivot fit as well:
`width²+depth² <= (usable_width-2*clearance)²`. For the maximum footprint,
`.60²+.40²=.52 <= (.82-.04)²=.6084`. This avoids irrational square-root rounding.
It is not a full curved swept-volume or mesh collision proof.

No tote recipe is chosen. Source `payload_admission.tote_outer_target_m` is
`.60×.30×.40`; downstream design notes propose outer`.60×.34×.40`, inner
`.56×.30×.36` and a tray-floor revision`.62→.66`. Both candidate outer heights
are below the separate source.40 height limit, but the adapter does not approve
either package/interactions. STANDARD HU cannot be hidden inside the smaller
candidate tote. Packing recipes, carrier supply and packaging tare remain explicit
future profile decisions.

`edge_timing` obtains length and dwell exclusively from the bound source edge.
Length/speed uses exact Fraction conversion of finite source decimal numbers.
Arc timing uses the source's declared1.9634954084936207m, not an invented exact
pi or recomputed rounded chord. Existing ADR0026 ceiling to microseconds applies
separately to travel and stopped pivot. Divert pivots before C→B; merge pivots
after B→C. Both turn at C. Preserve that ordering and node in the result.
For a.5m edge, travel10/11s→909091ticks plus.8s→800000ticks gives1709091ticks.
The arc gives3569992ticks. A future runtime must retain the T lease during dwell.

## Consequences and checks

These primitives are reusable prerequisites for a later finite conveyor DES.
They do not add events, resources, queues, motion playback, packing times or
carrier recipes to the manual engine. Six station reachability and impossible
upstream return are checked against the source directed graph.

Focused hand-oracle tests cover exact topology/resource counts, membership,
positive and negative payload boundaries, all allowed/forbidden kinds, raw-byte
pin tampering, unknown references, before/after turn order, angular cells,
separate resource requirements and exact operation ticks. Full conveyor runtime,
backpressure/fairness/deadlock, occupied swept cells, actual parent ancestry,
handling, packing and six-port throughput remain unimplemented by this ADR.
