# ADR 0067: Paired coordinator comparison for bounded N0 and N4

Status: proposed backend implementation; checks deferred by the user's current instruction.
This decision does not amend a shared frontend contract or establish full V3 acceptance.

## Problem

A registry hash binds the 24 worker identities, declared skills, availability and station
primaries. It does not bind stock, orders, carts, ports, graph, geometry, materials or clocks.
Comparing two runs by that hash alone can attribute changed physical inputs to a role plan.
An analytical C11 allocation score also does not execute a paid relocation or an N1/N2/N3 flow.

## Decision

The public Python entry point `compare_coordinator_profiles` accepts two strict ADR 0064
documents and an explicit `N0` or `N4` scenario. Both documents compile and undergo retained
typed-input validation before either engine is created. Invalid input propagates as validation
failure; unsupported scenarios raise `UnsupportedPairScenario` without creating an engine.

For each validated input, decode the immutable `choices`, replace only `role_intents` with an
empty list, and recompile through the same source, graph, physical capacity and resource gates.
The complete neutral frozen bytes must match. Their SHA-256 is `common_input_hash`.
The comparison retains all provenance/profile metadata, source pins, H/end, registered goods,
future receipt definitions, flows, placements, exact timers, worker calendars, materials,
stations, carts, role capabilities and per-order physical assignments. Invalid neutral input
is an incomparable validation failure, never a partial projection with a hash.

An additional exact materialized-profile comparison removes only native `intents`; it prevents
a derived physical-world change from disappearing during neutral recompilation. This comparison
follows successful exact typed validation and is not a substitute for that validation.

N0 requires identical complete frozen inputs as well as the neutral identity. It executes two
independent `CoordinatorEngine` instances and compares canonical native event bytes and all
captured observations/completion fields. Reusing one cached simulation is not two executions.
Unequal observations produce `not_demonstrated`, with both actual results retained for diagnosis.
The verdict concerns determinism for this declared bounded input, not every N0 warehouse flow.

N4 requires an empty baseline role plan and exactly two distinct existing primary pickers,
each declared eligible to pack, assigned to distinct stations. The restore target must be the
existing actor's actual home. The same roster, skills, breaks, equipment, assignments and all
physical inputs remain common; additional headcount or hidden material/resources are rejected.
Actual admission still belongs to the one coordinator clock/worker map/ledger/belt: a primary's
break does not establish an empty bench, free helper, released cart, or released claim.

Both actual outcomes pass strict ADR 0065 native publication validation before the paired
report is built. A demonstrated helper has an actual activation, completed pack and clear with
released packing ownership, positive observed packing labor, and actual restoration no later
than its declared deadline. Both helpers must demonstrate this and the candidate must have no
constraint violation. Planned ends are not actual completions; a capped paid return leaves
restoration null and the verdict `not_demonstrated`. A positive-duration transition requires
its actual completed operation. A zero-distance transition has no paid operation in the
native journal; equal actual start/end ticks and the matching `role_activated` or
`role_restored` event establish completion after strict native validation. Its labor is zero;
no artificial travel is introduced. Native route/custody/resource validation
establishes the physical station admission, not an inferred availability flag.

## Metrics and evidence

The report carries both complete native metric summaries. Counts are settled through the
observation tick; time integrals cover the half-open interval. At-horizon summaries use the
same H. At-end summaries use each run's actual observation end under the same cap and can
have different denominators. Role assignment time is never reported as worker busy time.

ADR 0065 defines roster labor over `24*T`, available roster labor over actual available
worker time, and effective-role labor over available assignment time for that role. Zero
denominators are null. Role outward/return labor occurs once in those sums. The paired helper
evidence separately measures actual pack/clear and role-transition operations, clipped to the
actual observation end; it does not add those diagnostic values to the native totals.

Report/result bytes are immutable. Decoded accessors return new objects. `comparison_id` binds
pair version, scenario, scope, full common input hash and both full input hashes; native run
IDs retain their own namespace. Canonical event hashes contain no wall-clock benchmark data.

The non-public `coordinator_pair_hand` seam uses ADR 0065 validated analytical hand inputs.
It exists for manual arithmetic acceptance, has `analytical_fixture` scope, and is not accepted
by the source CLI/API. The public source function never falls back to this seam.

## Prewritten acceptance

The two-station, one-cart hand world starts both orders at 80 s. Baseline shipments are
288.254551 and 319.254551 s; resource drainage is 324.254551 s. With the two explicit helper
plans, shipments are 270.17 and 301.17 s, and resource drainage is 306.17 s. These values come
from the prior declared hand routes, service times and source conveyor arithmetic.
Each helper performs 3 s pack plus 1 s clear. P11 transitions 100–104 and 156–160 s;
P12 transitions 100–106 and 154–160 s. At cap 158 s, paid transition exposure is 6 and 10 s,
respectively, and neither actual restoration has occurred. These tests are written before
the harness implementation and have not been executed under the current deferred-check rule.

## Limits

N1/N2/N3 are explicit unsupported execution capabilities. No C11 score, static source model,
asset action or synthetic workload silently stands in for their paid physical execution.
The report always retains `full_v3_acceptance=false` and `frontend_adapter_supported=false`.
It is an in-memory bounded comparison, not a streaming or bounded-memory publication promise.
No HTTP endpoint, shared schema change, frontend reader adoption or source-scale timing claim
is introduced by this ADR. Root integration owns the final gates and public orchestration.

## Mixed-source demonstration terminal capacity

The original and Tilek-helper N4 example pairs declare three retained terminal places
for their common shipped owner: two distinct unit parcels P1/P2 plus the one intact
RECEIVED-STANDARD-1 HU. This is an explicit scenario capacity assumption, identical
on both sides, not a new warehouse/source norm. The earlier capacity2 cannot finish
all three shipments without a separately modeled terminal-clearing process; none is
declared. Keep the runtime finite-capacity guards and partial outcomes unchanged.
No upstream source pin, material population, actor count or operational timing changes.
The four corrected JSON examples and the independent pre-run arithmetic test are
authored pending final checks; they do not establish an observed complete result.
