# Independent manual V3 execution oracles

These arithmetic oracles were written before `app/v3/execution.py` existed in
the runtime worker tree (observed `Test-Path` false, 2026-11-07). They are small
synthetic acceptance inputs, not production process choices or source-profile
compilation. All 24 actor identities are declared explicitly; only R01/R02
have the receive skill in the shared-resource scenarios.

The public seam is `ManualEngine(profile, bound_graph, check_invariants=True)`
and `.run(horizon_tick, end_tick)`. Each second is exactly 1,000,000 ticks.
Travel speed is 1 m/s; intake service 2 s; each pickup/place 1 s. Each HU has
24 units of one SKU, 1 kg gross mass and .2 m dimensions. No expected value is
obtained from an engine run.

## Shared actors across three ports

For j=1,2,3, independent declared directed arcs exist in both directions:
`H --j m-- Pj --1 m-- Bj --2 m-- Sj`. Every port has one finite buffer place.
All three jobs arrive at time0; J1/J2/J3 address their corresponding ports and
distinct slots. Port eligibility includes the same R01/R02, not duplicated
per-port workers. All remaining 22 actors have empty skills.

For a job starting at d, the event boundaries are:

| Operation | Finish |
|---|---:|
| Empty approach H→Pj | d+j |
| Intake service | d+j+2 |
| Loaded Pj→Bj | d+j+3 |
| Place in buffer | d+j+4 |
| Pick from buffer | d+j+5 |
| Loaded Bj→Sj | d+j+7 |
| Place in storage | d+j+8 |
| Empty return Sj→H | d+2j+11 |

Stable job/actor dispatch gives J1/R01 at0 and J2/R02 at0. Their storage/home
times are9/13 and10/15. J3 can start on R01 at13; its storage/home times are
24/30. Elapsed completion is30 s, total occupied actor time13+15+17=45 person-s.
The same two actors remain shared across all three ports.

At horizon25, all72 units are in storage but R01 still returns; state is
partial until30. At horizon9, events at9 are included:24 stock,24 WIP,24
outside. New dispatch at or after H is forbidden, so J3 cannot start at13 in
that shorter run. Its final counters are48 stock,0 WIP,24 outside,0 shipped;
remaining outside stock is never credited to the warehouse.

## One finite buffer and two workers

Two jobs at0 use P1/B1 and distinct storage places at S1. Both actors are
eligible. The first job holds the buffer[0,6), releases its bay at3, places
stock at9, and returns at13. The second must wait for the buffer, despite the
other worker being free. It starts at6, releases its bay at9, releases buffer
at12, places stock at15 and returns at19. Buffer reservations touch at6 but
never overlap; final elapsed19, actor labor13+13=26 person-s. At5: first HU
is in the buffer, second outside, warehouse stock0 and WIP24.

## Exact port and horizon boundaries

Single P1 job has service[1,3], storage9 and return13. A declared window[0,3]
allows service to finish exactly3. Closing one microsecond earlier rejects
dispatch with no cargo credit or leaked leases. A horizon3 similarly permits
the service ending exactly H and drains internal putaway/return; horizon one
microsecond earlier cannot admit this service. State snapshots include tick H;
new arrivals and dispatch require tick<H. These policies are explicit ADR0031
semantics, confirmed with the runtime owner before test execution.

With the same job arriving at4 rather than0, every boundary shifts by4:
service7, storage13, home17. No job event or resource lease may precede4.

A future window[5,7] requires an independent wakeup at4: paid approach[4,5],
service[5,7], stock13, home17. An arrival-only wake at0 and window-opening
wake at5 miss this feasible job. The runtime owner confirmed earliest feasible
approach semantics before the added regression was run.

## One HU through inbound and outbound

The same HU has inbound J1 at P1 and outbound J2 at P2, both arriving at0.
R01/R02 each explicitly have receive and ship skills. Inbound places at S1
at9 and returns at13. R02 can then approach H→S1 in4 s, reaching13; pickup
finishes14. Loaded S1→B2 uses S1→B1→P1→H→P2→B2, distance2+1+1+2+1=7 m,
reaching21. Buffer place22, pickup23, loaded B2→P2 reaches24, port service
finishes26, home return ends28. The same24 SKU units move once through stock,
WIP and shipped; neither a second job nor a return journey creates goods.
At H26: shipped24, warehouse0, returning actor; end28: complete, all home.
At H15 outbound cannot finish port service inside H, so it must leave the HU
in storage: stock24, WIP/outside/shipped0. The runtime owner confirmed this
policy before this fixture was executed. Total occupied labor for H26 is
13+19=32 person-s, not the elapsed28 s.

## Business completion versus resource release

A separate fixture uses H→P=2 m, P→B=3 m and B→S=5 m, all bidirectional,
with service10 s and pickup/place1 s. Only R01 can perform the requested job.

Outbound: approach10 + pickup1 + carry5 + buffer place1 + pickup1 + carry3
+ service10 = handover31. Return P→H costs2 more seconds; actor release33.
At H32, shipped HU count1 and business backlog0, even though JobView is
returning. Business cycle is31 s; busy labor on[0,32) is32 person-s.

Inbound: approach2 + service10 + carry3 + place1 + pickup1 + carry5 + place1
= stock23. Empty return S→H costs10; actor release33. At H24 the receipt is
already complete for inventory/business counts, although the actor still
returns. Tests assert distinct source events/ownership dates. Future metrics
must use business events rather than JobView's final resource state.

## Structural assertions

The tests also check finite resource lease exclusion, whole-HU conservation
among owner states, distinct HU ownership, motion continuity along actual
directed graph arcs, speed-derived durations, actor home return, no completion
event beyond the cutoff, and identical events/snapshots for two independent
runs. Heavy/manual-overweight cargo and unknown actor/port/slot/HU references
must fail explicitly before scheduling. These are acceptance conditions, not
new handling modes.

## Actual outcome export and seek

The separate manual V3 proposal exporter is exercised with this exact synthetic
hub graph, explicit node coordinates and connector provenance. Its graph bytes
are hashed and bound to both profile and graph. A real engine outcome is
exported; seek10→28→5→28 must produce stock48 at10, stock72 at28, and
stock0/WIP48/outside24 at5. Every state retains exactly three HU identities
and72 units. Repeating28 returns an equal state and leaves the complete source
run unchanged. This verifies the current manual proposal replay seam, not a
shared frontend contract, transport loader or restorable engine.

## Observed verification

Initial missing-engine RED: `1 error in 2.50s`. The independently added future
window test then reproduced a product defect: no worker lease rather than the
hand-derived4 s start, `1 failed, 9 deselected in 3.47s`. The runtime owner
added the exact pre-service wakeup and retained the same arithmetic oracle.
No production implementation was edited by the acceptance worker.

Final combined independent acceptance run: `27 passed in 2.72s`. This includes
the business/resource boundary and actual exporter/replay cases. Metrics
backlog/cycle/labor assertions remain the metrics owner's follow-up; these tests
establish their source event dates and quantities.
