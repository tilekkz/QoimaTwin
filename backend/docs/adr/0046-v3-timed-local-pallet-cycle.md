# ADR 0046: Time and own the proved local PALLET pickup/return component

Status: backend proposal; isolated mechanical component. Inventory integration
and warehouse operational admission remain false.

## Context

ADR 0042 independently verifies the fixed PALLET GLB action, thirteen affine
intervals and finite support. It does not define an engine clock, driver schedule
or warehouse receipt. The published visual 30-second timeline is not a duration
authority. This component supplies explicit synthetic timing and finite shared
resources while retaining the complete original geometry proof unchanged.

## Input and proof authority

`CycleTimingProfile` requires positive exact Fraction values for root, lift and
reach speeds, attach/release handling and zero-displacement hold. It declares a
synthetic source and an initially seated F01 in FL01. A nonempty profile identity
and provenance explanation are required. No production speed defaults are added.
The seated driver is a logical resource state; this does not certify a new human
mesh or a walking/seating operation.

One immutable physical registry entry is the proved PALLET model: PALLET_LOAD,
24 units, gross 455 kg and its exact mesh hash. Repeated CycleJob requests reference
that same HU ID. Unknown HU/model/class, duplicate job IDs and noninteger or
negative ready timestamps are rejected. The fixed 24 actor IDs remain in the
exposure report; only F01 operates this component. No actor or vehicle is created.

Before execution, every raw ADR 0042 input is rehashed. A trusted full proof is
recomputed once per method/source set and cached immutably. The supplied proof
must match its complete canonical representation, including method, binding,
interval and contact fields. A caller PASS flag, edited measurement, stale hash,
or a modified source hidden behind the cache cannot authorize movement. The
original thirteen-interval proof remains a separate outcome field.

## Exact operation clock

Read original declared coordinate decimals as Decimal and then Fraction before
subtraction. Do not subtract binary floats, use GLB roundoff as a duration input,
or read the visual timestamp field. ADR 0026's one-million ticks/second and ceiling
of each complete positive operation apply. Simultaneous affine components, if
present in the pinned path, take the maximum component distance/speed duration;
all components therefore stay at or below their declared rate after rounding.

The thirteen original geometric intervals remain in order. A positive attach
handling interval precedes the transfer to vehicle ownership; a positive release
handling interval precedes the transfer back to platform ownership. The source
zero-motion hold receives its explicitly supplied positive duration. All movement,
handling, holding and safe return time is charged to the driver and vehicle.

Independent hand profile: root 1 m/s, lift 0.52 m/s, reach 0.4 m/s, hold 1 s,
attach 0.2 s and release 0.3 s. Root travel 4.2 m costs 4.2 s, vertical travel
2.08 m costs 4 s, reach travel 1.6 m costs 4 s; hold/handling add 1.5 s, so the
total is 13.7 s. Owner transfers occur at 3.25 s and 10.65 s; the empty safe
return completes at 13.7 s. These numbers predate execution output.

## Separately proved source approach and return

The optional source approach binds the original source node root
`[120.8,0,17.5]` to the proved action start `[120.85,0,17.5]`. The fixture origin is
`[119.8,0,17.5]`, yaw-minus-pi/2. Local root Z consequently moves from-1 to-1.05
on approach and back after the cycle. Both movements are exactly 0.05 m.

Require both original directed arcs ending `HEAVY_E:001:B1:vehicle:segment:002:r`
and `002:f`, their own INBOUND_FORKLIFT_PAIR (F01, FL01) and nonlong_forklift /
PALLET_LOAD permissions, fixed yaw and straight geometry. Do not create a reverse
permission. Validate the source platform and support height. Partial-arc progress
uses exact root coordinate differences; the slightly rounded serialized full-arc
length is retained in source and does not inflate a 0.05 m movement by one tick.

Each bridge direction is additionally checked through ADR 0042's actual triangle
sweep method against the fixed fixture and action-space bounds. Separate
CycleBridge retains the two source arc references, exact fractions, source
hashes and two checked-cover counts. It does not replace the thirteen original
intervals. At the hand root speed, the two bridges add 0.05 s each: total 13.8 s,
attach at 3.30 s and release at 10.70 s.

The intermediate stop is an explicit local proposal inside this reserved handling
space, not a new unrestricted warehouse stopping node. Dynamics/braking forces
are outside the quasi-static geometry proof; the timing model changes speed at
operation boundaries. Full warehouse obstacles and IN_W support are not inferred.

## Resource and HU ownership

Atomically acquire the shared worker:F01, vehicle:FL01, source platform slot,
physical HU and action-space resources, in stable ID order. When the approach is
enabled, also hold the union of both arcs' source traffic resources conservatively.
Hold all these leases through the actual safe return, including the outbound 0.05 m
bridge. Reserving the platform while HU is carried prevents replacement stock
from blocking the proved return. Another request waits FIFO by ready_tick/job_id.

Attachment changes exactly one owner from platform to vehicle; release changes
it back. Both preserve the same physical HU and coincident world pose. The
registry is immutable, and mandatory settled invariants verify the original frozen
HU object identity, exact resource set, matching resource/job IDs, integer acquisition
time, active interval, continuous pose and attachment ownership. Numeric equality
alone is insufficient: Fraction(24) must not replace an integer unit count, and
a boolean must not stand in for an integer acquisition tick. These checks use
explicit exceptions under both normal and optimized Python.

These leases belong to this local component. Coordinating the same identities
with other warehouse components is a separate unified allocator task; the
result does not claim that integration already exists.

## Horizon, observation and exposure

T observes all events with integer tick<=T. Completion precedes arrival, then
dispatch, through PhaseScheduler. A request may start exactly at H; it has zero
actor exposure at H and an explicitly planned future end. Waiting work never
starts after H. A started cycle may drain to the declared end limit.

Active operations expose observed interpolated Fraction poses separately from
their planned end tick. A cap never emits an unobserved completion or releases
the actor/HU/resources early. If all work finishes before H, actual at_end can be
earlier than H while at_horizon remains the settled state at H. Idle incomplete
work after admission closes is labeled horizon_closed, not falsely attributed to
an occupied resource. An empty job list retains the existing HU and zero exposure.

Actor paid ticks and time-weighted waiting-job exposure integrate [0,T), while
counts/ownership use settled state through T. Releasing a HU to the platform is
distinct from completing the paid safe return. The requested end limit is stored
separately from actual end, and all future plans remain distinguishable from
observed events.

## Validation and limits

TDD uses the 13.7/13.8-second hand oracle, individual microsecond ceilings, FIFO
competition, repeated HU identity, exact attach-at-H, cap interpolation, paid
return, stale proof/contact/source rejection, both missing directed arcs, wrong
equipment pair and deliberately corrupted registry/lease state. A fresh actual
source artifact is executed under python-O after focused/static checks.

No shared schema, frontend, source model, source pin or frozen mesh proof changes.
This does not complete IN_W receiving, N2, all cargo classes, actual personnel
geometry, inventory ledger integration, warehouse traffic scheduling or OEM
physical certification.
