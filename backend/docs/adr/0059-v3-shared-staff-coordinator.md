# ADR 0059: Shared-clock staffing coordinator, bounded B0/B1

Status: accepted for B0 protected defaults, B1 actual staffing transitions and the bounded
B2 helper packing extension below. Multiple picking/cart/station choices and the paired
six-station N4 workload remain future C stages. No existing publication or input contract
changes. The B1 decision below is retained as the previous native boundary.

## Source and scope

The adaptive brief `docs/adaptive-v3/brief/02_DESIGN_V3.md` sections 7/10 and
`docs/adaptive-v3/DOWNSTREAM_DESIGN_NOTES.md` at immutable revision
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` require the same 24 identities and six existing
stations, common downtime/skills, genuine release, paid movement and restoration. Their
K05/K06 and P11/P12 example is a candidate design, not a service norm or completed N4 test.
ADR0057 validates that source subset and explicit common registry assumptions. Its
analytical cover is not actual worker assignment or proof of complete physical A/B inputs.

This package uses the existing connected light/receipt/whole runtime and the same stock
ledger, worker objects, heap, belt and finite resources. It does not instantiate an engine
per station or duplicate actors in a staffing map. Role metadata stores intentions and
actual stage timestamps; all positions, paid operations and custody remain in the one
inherited worker/ledger world. All 24 actors and declared initial inventory remain present.
Existing unit and whole-HU capabilities remain available; staffing B1 does not narrow the
whole V3 project to the synthetic SMALL demonstration.

`CoordinatorEngine(CoordinatorProfile, ConveyorSource).run(H, end)` is a new native Python
entry point with version `qoima-staff-coordinator-v3-proposal-1`. It takes an explicitly
typed physical profile plus a freshly revalidated Registry A. It has no source compiler,
JSON input/API/CLI, run ID, published schema, replay or frontend adapter. Six station
bindings in the hand fixture are explicit synthetic physical nodes and exclusive bench
owners, not a claim that source six-station cargo dispatch has been implemented. Source
role identities and primary roles remain source facts; cross-training and windows remain
declared common assumptions. The existing source compilers and older entry points are
unchanged.

## Compatibility seam

The old light engine exposes protected due-completion, dispatch-round, eligibility and
early-stop defaults. Default bodies preserve the original order and availability tests.
Receipt and whole dispatch call the same eligibility hook for their actual R/S workers.
Only the new coordinator overrides these defaults. Old light/receipt/whole outcome and
event canonical hashes were captured before editing and are controlled separately; these
are byte compatibility controls, not numeric acceptance oracles derived from engine output.

The new same-tick order is: account the preceding half-open interval; complete actual human
operations and release their custody; complete belt motion; apply remaining arrivals,
availability and role calendar facts; settle actual dispatch; check all invariants; capture
state. Thus a real return completing at 160 precedes primary reavailability at 160. Old
namespaces keep their historical ordering. Checkpoints and H/end state include all events
at or before the boundary. Planned future completion is never an actual completion.

## Role admission and actual ownership

Station IDs must be precisely the six source IDs, each once, with distinct actual nodes and
one-place workstation owners. The existing flow station must match its physical node/bench
and actual primary packer in this catalog; checking a different idle packer cannot release
the real station. Role intents have unique work IDs, exact nonnegative integer microseconds
(no bool aliases), nonempty request/return/deadline periods, known references and no shared
actor/station overlap. An explicitly pack-capable non-primary actor may cover only a common
primary break that spans the proposal. The helper cannot have common downtime during it.
For B1 restoration means the helper's actual declared home, with directed outward and
return routes. Arbitrary primary task continuation anchors are a future context extension.

A request first quiesces the helper: it blocks new primary admission but does not interrupt
an owned task. The helper must actually finish its operation, empty its custody, release its
cart/receipt/whole leases and return before departure. The primary station actor must be
unavailable **and actually clean**, and the bench must be physically empty. An unavailability
interval alone does not release a person or station. Rejected or waiting proposals never
move stock, discard work or create an extra worker.

At actual departure, reserve the helper and station. Pay directed travel from the worker's
real node using exact length/speed with one microsecond ceiling, using the normal human
operation/calendar machinery. Activate the packing role only at actual route completion.
B1 grants no helper packing job; its active interval is availability exposure. At the
declared return start, release the station only when the helper is clean, pay the actual
return, and retain exclusive actor ownership until arrival. Strict settled checks bind role
phase/timestamps, leases, station bindings, current operation/step/route and actual anchor.

The current bounded no-goods role transition must fit its declared return and restoration
deadline. A one-tick miss is rejected without travel. If a future operation prevents return,
retain real custody and report a deadline violation; do not teleport or invent a handoff.
B2 packing admission will need a proven local pack/clear/return bound and pre-reserved
finite resources. Unbounded downstream waiting cannot be converted into an invented worst
case. Current B1 role eligibility is not permission to bypass those future checks.

Common breaks prevent new unit, receipt or whole-worker admission. Previously admitted
work keeps its paid steps and custody through the break. A busy actor at break start emits
`PRIMARY_BREAK_NOT_CLEAN`; operational completion can still occur, but `staffing_status`
is `violated`. This separates a completed physical drain from compliance with a staffing
proposal. Primary capabilities alone never constitute a live admission grant.

## Horizon, completion and exposure

Retain the established asymmetry explicitly: unit and whole outbound arrivals must be
inside `[0,H)` and are rejected at/after H. This follows ADR0031, ADR0056, the existing
`LightFlowEngine.run`/`WholeFlowEngine.run` checks and
`test_flow_profile_independent_contract`. Future receipt definitions may remain registered
as declarations but uncredited outside the warehouse: `test_receipt_flow_windows` explicitly
covers receipt arrival at H. Only receipts with arrival `<H` belong to business completion.
No future unit/whole offer is silently excluded or counted under a changed rule.

Role requests likewise must start before H; already admitted physical work and paid role
restoration may drain after H up to the end cap. The new coordinator observes the common
calendar through H even if goods finished earlier. It exposes separately:

- `business_complete_tick`: actual final unit/whole shipment or in-scope receipt placement;
  zero if that business scope is empty. It is absent while business is incomplete.
- `resource_drained_tick`: final actual transition from busy to fully released physical
  resources (zero if never busy), absent if current resources remain occupied.
- `observation_end_tick`: actual native state coverage, at least H for a complete run, or
  the finite end cap for a partial run. This is not an invented paid activity duration.
- `staffing_status` and explicit `constraint_violations`: compliance independent of drain.

At every captured view, role exposure partitions `[0,T)` across source primary/effective
roles, paid role transition and unavailable categories, counting each of 24 identities
once. It measures role/calendar exposure, **not utilization or productive labor**. Actual
worker `paid_ticks` still measures executed human operations, including travel. A break
violation can therefore have paid labor while categorized unavailable; the explicit
violation prevents interpreting that schedule as valid staffing. Future role-aware work
metrics must use actual assignments and may not infer role from actor ID prefixes.

## Independent hand arithmetic and limits

With common K05/K06 break `[100,160)` seconds and explicit clean helper routes 6/9 metres
at 1.5 m/s, P11 departs 100, arrives 104, returns 156..160; P12 arrives 106 and returns
154..160. Packing-role exposure gains 52+48=100 person-seconds; paid transitions consume
2*4+2*6=20. At H200, baseline packing exposure is 6*200-2*60=1080 and candidate is 1180;
unavailability is 120 and total exposure is 24*200. Business is empty/complete at zero,
resources drain at 160 and observation continues to 200. At H105 only P11 has arrived:
transition exposure 4+5=9, packing exposure 6*100+4*5+1=621. P12's completion at 106
remains a plan. At H159 both returns are physically open; transition exposure is 18.

Additional real-world composition controls retain a busy P01's original 20-second paid
pick/cart cycle before a requested transition, preserve an occupied bench, delay R01
receipt work until actual shared availability (credit32/place43/return53 after start20),
and delay STANDARD whole shipment (ship67/return72 after start20). These are conditional
hand fixtures, not source workload measurements. No hidden service duration or extra
staff/material is introduced. Exact operation and custody tests protect those boundaries.

B2 must next connect an actual helper to the existing finite packing workflow through a
per-order context. C must exercise multiple carts/orders and all six actual station paths
with shared receipts/whole shipments. A genuine N4 result additionally needs frozen full
common physical inputs, role-aware business/resource metrics and an honest paired run.
Registry identity alone is not that proof. This B0/B1 package does not claim N4 PASS,
all-archetype execution, throughput improvement, human contact/mesh validation or arbitrary
seek. C12 examples and unclocked planning periods remain outside runtime authority.

## B2: Atomic local packing on the same coordinator

The native version becomes `qoima-staff-coordinator-v3-proposal-2`. This extends the existing
CoordinatorEngine; it does not instantiate a second engine, worker map, stock authority or
calendar. Old light/receipt/whole entry points, engine versions and published bytes remain
unchanged. The previously frozen B0/B1 package remains independently reproducible.

Each actual admitted unit order records an immutable `UnitContext`: actual picker/cart,
station/shipper/port and source/intake/output references. B2 freezes those from the current
single-flow profile rather than swapping that global profile during work. Multiple unit
orders may use the same existing cart/station sequentially, with distinct unit tokens and
materials. Distinct concurrent cart/station routing is still C work. A `PackingState` binds
an order to its actual packer and optional live role intent. It contains reservation and
stage facts, never another physical worker or copied worker position. Current contexts,
packing views and deferred reasons appear in native snapshots and events.

The primary packer may start only under the same common calendar and actual-clean checks.
An additional helper is considered only if the actual station binding names that actor,
the effective packing role is active and the worker has actually arrived and released its
prior custody. Skill eligibility alone cannot select an arbitrary worker. The existing
primary cannot enter a station still physically bound to a helper, even if its own
calendar has become available. The return bound uses the existing uncapacitated pedestrian
graph semantics; it does not claim future aisle traffic or collision admission. The existing
primary behavior is retained: an already admitted primary task can overrun a declared break
and must report `PRIMARY_BREAK_NOT_CLEAN`, without interruption. A valid N4 pair must not
disguise that violation as a free station. The stricter restoration proof below governs a
helper's new bounded local work; it does not retroactively cancel primary work admitted
under the existing policy.

Before assigning even the paid approach, prepare a side-effect-free local plan:

1. Resolve the actual worker node and directed approach route. Check the complete empty
   carrier tare and predicted sealed-parcel gross against this actual actor's capacity.
   Parcel prediction uses the real carrier's exact unit tokens and declared package tare,
   shape, ID and provenance; no inventory credit or packing transaction happens yet.
2. Validate the complete remaining directed parcel route at the actual stationary pose
   using the existing FlowBelt replacement compiler. Reserve the union of current pack/clear
   step requirements and the target-pose footprint. Do not reserve the entire downstream
   conveyor, an entire MAIN segment or unrelated future swept movement cells.
3. Check and reserve one actual worker, the exclusive package bench, a finite empty-carrier
   rack place and the declared package material. Capacity includes physical contents and
   outstanding reservations. The same object is not counted twice after arrival at its
   reserved destination.
4. For a helper, prove `now + approach + pack + clear <= declared_return_tick`; its paid
   directed return from the station at that return tick must finish by the restoration
   deadline. Terms are explicit services or exact route durations, with no guessed queue
   bound. Failure leaves the order waiting without partial worker/material/footprint claims.

All belt leases/external reservations and local owner capacity are checked before mutation.
One `FlowBelt.reserve(order, union)` commits the local belt reservation, followed by owned
engine resource keys in the same non-interleaved callback. No other dispatch runs between
checks and commits. Nested role ownership remains on the same real actor. Actual pack/clear
operations use the existing belt-driven clock and HumanState. Callbacks resolve the admitted
packing assignment instead of always consulting the profile's primary packer.

Packing credits parcel contents only at completed pack. The existing carrier stays the
physical belt body, with its tare and geometry, until completed clear. The reserved parcel
footprint stays in `FlowBelt.external`; ordinary belt release does not remove it. Clear
moves the empty carrier to its reserved rack and the parcel from bench to belt, then
`replace_payload` transfers external reservations into actual belt leases. Actual pose and
elapsed immutable step prefix are preserved; only future movement uses the new shape. The
following belt finish retains the footprint of the new body. Earlier events are not rewritten.

After clear the parcel can wait for ordinary downstream capacity without holding its human
packer. The local proof therefore needs no fictitious downstream queue bound. A helper
releases the unit packing assignment and stays at its actual station under its role lease
until the declared return. A primary keeps its worker lease through normal paid return home.
Bench, material and rack reservations release after actual clear; role leases retain B1
semantics. Closed packing assignments cannot authorize later activity or bypass role guards.

Settled checks cross-check context admission, actual worker/operation, shared role binding,
completion times, material custody/mass, capacity and the complete local reservation. The
reserved future parcel must match the real material's identity, shape and predicted mass
even before packing completes. A missing reservation or inconsistent operation raises at
the captured tick rather than only at a later clear. Snapshots contain no whole stock
history or invented future completion. These native facts have no public replay contract.

## B2 hand arithmetic and limits

Both variants use one order arriving100, H300/end400, the same24 people, common K05/K06
break100..160, source belt, stock, cart, materials and services. Deposit113 plus belt
prefix30.915448 gives station arrival143.915448. In A the primary's availability160 and
paid approach2 give pack162..165, clear to166, output282.254552, shipment308.254552 and
final return313.254552. In B, P12 is physically at the station from106: pack to146.915448,
clear to147.915448, output264.17, shipment290.17 and resource drain295.17. Observation in
B continues to300. P12 returns154..160; paid time is12 transition +4 local service=16.

Latest helper pack start150 is exact: pack3+clear1 ends154, return6 ends160. 150.000001
cannot satisfy the proof and leaves the job for actual primary availability. One order
preserves24=21onsite+3shipped and1.19kg total. An extra declared empty C2 in a capacity-one
rack forbids pack:21source +3carrier units, empty P1/C2, and .835+.305+.05+.20=1.39kg. The
helper still restores160; goods remain backlog. No material disappears to meet a deadline.

At the actual PK06 stop, both a narrow .32x.24x.24 carrier and enlarged .60x.34x.40 parcel
overlap source cell V3-C-SPUR-06-1 and exclusive V3_SPUR06. Do not invent an extra-cell
oracle. Expansion is nevertheless real: the new body appears only at clear, its remaining
route is revalidated, and a competitor cannot acquire held local resources. These are
explicit synthetic materials, not canonical M07 selection or validated hand contact.

A two-order same-HU control uses one cart/station: deposits113/133. P12 packs the first;
restored primary K06 packs the second. Outputs264.17/286.17 share S01: first shipment290.17
and return295.17; second shipment321.17 and return326.17. Six distinct units ship, total
material mass stays1.44kg. This protects existing multi-order behavior, not concurrent
multi-station dispatch or a source workload measurement.

Registry identity still proves only common staffing inputs. Genuine N4 needs complete
compiled common physical inputs, relevant station/resource flows and role-aware business
and labor metrics. The hand improvement is a bounded integration oracle, not a throughput
forecast or N4 PASS.
