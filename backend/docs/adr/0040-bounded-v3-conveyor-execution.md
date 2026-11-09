# ADR0040: bounded source-conveyor execution with physical-cell reservations

Status: accepted for the isolated backend V3 proposal. This is not a shared wire
contract or a complete warehouse picking/packing process.

## Context and explicit scope

ADR0037 freezes the L08 conveyor supplement at upstream22296bc. It supplies
90 physical cells,15 resources, source geometry and positive movement/pivot
durations, but no operational packing recipe or timed carrier population.
The source requires all footprint-overlapped cells, downstream reservations,
one carrier on the whole curve and one job per reversible station spur.
Locking a complete10/11m MAIN edge would contradict that physical-cell model.

`BeltEngine(source, jobs, check_invariants=True).run(horizon_tick, end_tick)` now
executes an explicit, finite population. Each frozen job supplies unique job,
carrier and whole-HU identity, arrival tick, an explicit sequence of directed
source edge IDs and optional station identity with exact dwell ticks. Its source
and sink are the first/last declared route nodes. Local initial placements are
allowed for component fixtures; only the actual intake→station→output route is
labelled a complete pass through this bounded conveyor.

Arrival means the external caller offers the unchanged carrier at that declared
source. It stays outside until initial physical cells/resources can be acquired.
Completion means handoff at the declared sink with all belt leases released.
These are not receipts/shipping confirmations or paid human loading actions.
No parent/lot/quantity transformation, wrapper/tare change, order packing or
warehouse inventory mutation is invented. The caller remains responsible for
binding supplied HU/carrier/parent identities to its actual stock ledger.

## Body convention and provable geometry

The explicit upright body has source xyz dimensions: width transverse to travel,
height vertical, depth longitudinal. This convention matches L08's.40m base
depth: intake centreZ5.05 ends at5.25 and station stopZ5.3 ends at5.5. The source
does not grant tipping or automatic dimensions changes. Positive world yaw
quarters are recorded separately: intake0, westward MAIN1, station inbound2.
Spur reversal keeps yaw2, rather than snapping the body180degrees. Divert pivots
1→2 before its edge; merge pivots2→1 after its edge, at the source C node.

For straight motion, each typed source Cartesian cell supplies its centre and
length. MAIN has longitudinal one-metre intervals and source usable deck width;
spur/feed use their vertical-in-plan centreline and the same usable width. T
cells are their one-metre transfer pads. A cell is physically occupied when the
upright rectangular body has positive planar area intersection; pure touching
at a boundary has zero occupancy. Cell ownership remains capacity1 regardless
of whether two smaller rectangles might otherwise fit into one cell.

Movement is split at the exact Fraction progress where a leading or trailing
body edge crosses a cell boundary. A chunk reserves all cells overlapped at
its start, interior intervals and end **before** movement. Tail cells release
only at the chunk's observed completion. A10m source edge therefore has21
chunks for the explicit.40m longitudinal fixture, each needing at most two
cells; no global MAIN lease exists. Neighbouring resources are included at
seams. The source body-size limit and grid spacing prevent unobserved long
jumps; same-tick sub-boundaries are merged with their complete swept cell union.

The source entry arc is a quarter-annulus, radiusR=1.25m. Its four cells are
angular sectors, not fictitious straight cells. For transverse widthw and depthd,
the rectangular body fits the padded annulus when:

```text
R - w/2 >= R - usable_width/2 + clearance
(R + w/2)^2 + (d/2)^2 <= (R + usable_width/2 - clearance)^2
```

Its angular shadow about the radius is bounded by
`alpha = atan(d / (2R - w))`. The supported source limit gives a ratio at most
4/19 <1/4. An exact25-term alternating Fraction series gives an upper bound,
then rounds outward to1e-18rad. The omitted series error is bounded by the next
term; there is no arbitrary geometry epsilon or binary-float comparison. This
enclosure can conservatively retain/acquire a boundary cell up to one extra
microsecond; it never releases earlier than the physical footprint. It is not
claimed to be an exact irrational angle or a general mesh swept-volume solver.

The angular shadow intersects source angular intervals to derive occupied arc
cells. Feed stays reserved only while the shadow extends past the entry angle;
the first MAIN cell is acquired when the shadow reaches the exit. On adjoining
straight edges, actual leading/trailing depth crossing the source endpoint plane
controls the curve overlap. The complete curve resource is exclusive throughout,
independent of which of its four cells the body currently overlaps.

The upright pivot fits inside one T pad by ADR0037's squared diagonal proof.
The pivot event has positive duration and a continuous yaw interval at a fixed
C centre. Intermediate yaw conservatively occupies that pad; it never cuts the
orthogonal corner while moving. This proof is specific to the reviewed L08
topology and admitted upright dimensions, not arbitrary conveyor meshes.

## Time, reservations and station lifecycle

One source edge is one timed movement operation. Its duration is exact declared
source length divided by0.55m/s and ceiled once to microseconds, including the
source's finite decimal arc length. Occupancy checkpoints use cumulative
`ceil(edge_seconds * progress * 1e6)`; differences form positive chunk durations.
Coincident checkpoint ticks merge. Thus cell subdivision does not accumulate
extra ceil drift:10m still takes18181819ticks if unblocked. Any blocked checkpoint
adds actual waiting before the remaining movement, not hidden speed or teleport.
Stopped pivot is its own800000tick operation, before/after as the source declares.

Before entering a station T, a station job also acquires the whole spur guard.
It retains that guard through intake, the caller's explicit stationary dwell,
reverse travel and return merge/pivot. This prevents a following station job
from occupying the return T while waiting for the same spur. Other through-route
carriers can use free MAIN/T cells subject to physical capacity. No extra packing
station buffer, worker, cart or time is inferred from the six table meshes.
An explicitly supplied zero dwell is allowed and adds no service interval.

All needed cells and exclusive resources are acquired atomically. At one tick,
all scheduled completions release their obsolete leases before waiting jobs
dispatch. Waiting priority is stable `(waiting_since, job_id)`, independent of
input array order. It is deterministic FIFO arbitration at reservation attempts,
not a proof of arbitrary traffic-network deadlock freedom or maximal throughput.

## Horizons, journal and invariants

Materialized arrivals must satisfy0 <= arrival < H. H is an observation boundary,
not a port service window: all released carriers may continue draining/admitting
from their finite outside queue until the explicit end cap. This differs from
manual whole-HU port-window admission because this source belt has no port window.
No after-H arrivals are silently filtered or synthesized.

At H and at_end, state includes all events with tick <= cutoff. An active movement,
pivot or station interval retains its planned future end, but the journal never
reports that future completion. Observed progress/yaw is clipped to the cutoff.
If all jobs finish, at_end is the actual final operational tick, possibly beforeH;
otherwise it is the end cap with statuspartial. Empty input completes at0.

Queue exposure is carrier-microseconds over[0,T): time outside waiting for initial
admission plus admitted waiting for the next resource reservation. It excludes
movement, pivot and explicit station dwell. Counts are settled/inclusive while
integrals are half-open. This is not worker utilization or productive labor.

The immutable journal records actual arrival/admission, resource acquisitions/
releases, positive phase starts with planned ends, phase completions and final
handoffs. HU/carrier IDs remain unchanged; checkpoints use the source edge plus
exact progress/yaw instead of fabricated Cartesian coordinates on the curve.
Existing warehouse exporter/replay formats are not silently extended by this ADR.

Settled invariants run after each event tick and both observations: physical
footprints and the active compiled step's complete swept-cell/guard requirements
have all required leases, including reservations acquired before body entry.
The active phase, endpoints and duration must match that immutable compiled step.
An admitted waiting carrier retains guards spanning its previous and next steps;
a newly required guard may still be blocked and is not falsely treated as held.
No cell has two owners, exclusive resources
have one owner, identities are unique, lifecycle/queue values are valid and no
completed carrier retains resources. Unknown keys/owners and a global
`resource:V3_MAIN` lease are invalid. Checks remain ordinary runtime exceptions
under Python-O; they are not removable assert statements.

## Hand acceptance and remaining integration

- One10m edge:18181819ticks. A second offered at0 can enter at2181819ticks when
  the first tail clears its source cell, well before the first finishes the edge.
- Local station roundtrip:.5m+1.8m+1.8m+.5m, two.8s pivots and explicit2s dwell:
 11963638ticks; second station job waits through the complete guarded return.
- Two local source-arc carriers:2×3569992=7139984ticks; one shared curve owner.
- Actual source intake→PK06 work→output with explicit2s dwell:149170000ticks,
  from independent per-source-edge arithmetic. A six-carrier/six-station test
  checks completion, immutable IDs, finite reservations and absence of leaks;
  it makes no measured shift-rate claim.
- Tests check exact H handoff, finite-end clipping, no pre-arrival queue exposure,
  journal continuity, input-order determinism, unknown/upstream route rejection,
  heavy-kind rejection, malformed identities and deliberate invariant corruption.

Human/cart induction, human discharge, actual pick/pack recipes and labor,
warehouse stock conservation across those transformations, transport publication,
general snapshot seek and full normal/peak warehouse runs remain separate work.
