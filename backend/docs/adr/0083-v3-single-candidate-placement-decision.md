# ADR 0083: One-candidate N1 placement decision

Status: accepted for planning-only source decisions, not operational N1 acceptance.

## Scope and inputs

Evaluate zero or one caller-declared original SMALL/STANDARD whole-HU transfer to a
different initially free, compatible L1 manual slot. This is not an optimizer or a
search over fabricated assignments. Fresh `verify_outbound_stock` preserves the
complete authenticated N1 offered stream, C10 assignment, all B2B offers, pending
receipt dependencies and visible shortages. No arrival, quota, source weight, unit,
lot, workload clock or initial stock identity changes. C11 contributes only the
already frozen outbound mix projection; its unclocked move multiplicities and
positive proxy totals are not physical customer visits or this decision's oracle.

`PlacementChoices` supplies an explicit finite candidate, S01/S02 permission,
existing actor identity, home, speed and mass limit, transfer take/place ticks,
path policy/clearances, exact affected customer offer/port/buffer and handling,
and receipt target declarations. No missing quantity becomes a default. One actor,
home and speed serve the transfer and both customer cycles in this bounded mode;
there is no hidden alternative actor or faster relocation worker. Buffer geometry
is explicit canonical `BufferChoice` JSON using the existing source-cell and local
connector checks. The original graph remains unchanged. Proposed connectors are
checked in a fresh copy and remain identified synthetic local geometry.

## Feasibility before cost

The source boundary reopens the pinned V3 bundle. Original HU/lot/unit/mass and slot
come from the freshly verified stock binding. Source/destination must preserve
manual L1 access, handler/cargo compatibility, orientation, exact dimensions with
clearance, payload, slot capacity and a mass at most min(15 kg, actor limit).
Source shippers and explicit permissions must include the selected S01/S02.

Every declared incoming HU needs an exact offered receipt job/HU to target-slot
binding before a transfer is priced. Missing declarations remain `not_evaluable`;
they do not imply no incoming stock. Targets must be distinct, known and initially
vacant, cannot reserve the transfer destination, and must satisfy source static
storage family, orientation, dimensions and slot payload. Aggregate HU count and
mass include all original stock and all declared receipts in every affected
module, including modules unrelated to the transfer. The transfer reserves extra
target-module capacity without speculating about future outbound releases.

Receipt reservation compatibility is a physical space calculation, not receipt
handling admission. The existing `storage_admission` is called without a handler:
only its sole `HANDLER_UNAVAILABLE` result means physical checks passed; every
physical failure remains blocking. Handling capability, readiness, completion and
stock credit remain unproved. No handler is invented for bulky incoming cargo.

Only the unique `original_bound` outbound offer for the candidate HU is affected.
Allocation already consumes each whole HU once. An unoffered HU, future receipt HU
or shortage cannot fund repeated savings. Unknown or mismatched customer process,
missing route or incomplete binding remains explicit and unpriced. Every offered
row survives even when it cannot participate in this manual candidate.

## Complete cost and deterministic no-op

The exact source port service duration must match the caller binding. Cargo/port
permission, finite buffer fit and its declared connector are checked before cost.
Reuse source directed graph filtering, the explicit absent-only SMALL/STANDARD
manual policy and `operation_ticks`. Explicit cargo denial or missing clearance
does not become permission. Graph edge cost must equal physical length; the pure
hand helper rejects a different optimization metric that could create fake saving.

Pay transfer approach, take, loaded carry, place and complete return. Price both
customer cycles as home-to-slot, pick slot, carry to buffer, place buffer, pick
buffer, carry to port, source service, and return home. Common handling and service
remain included, not assumed zero. Each complete operation is rounded separately
to integer microseconds; internal route arcs are summed exactly before rounding.
Each operation retains Fraction seconds and exact route nodes/arc IDs.

Store gross customer saving, full transfer cost and net=gross-transfer once. Select
the candidate only if net>0; no-op wins zero and negative values. Retain the negative
evaluation and reasons. Under this mode's identical actor/home/speed and static
directed routing, triangle inequality normally prevents a profitable one-consumption
transfer: no positive result is required or manufactured. Hand example: customer
25 s before /9 s after (including identical 5 s handling/service); transfer22 s;
gross16 s, net-6 s, therefore no-op.

## Public authority and limits

`prepare_placement_decision(stock, choices)` authenticates input first.
`load_placement_decision(raw)` accepts only closed canonical bytes, reloads source,
and reconstructs the decision. `verify_placement_decision(value)` returns that fresh
object after exact recursive type/value comparison. Rehashing changed offers,
routes, costs, receipts or metadata does not confer authority; numeric aliases and
unknown fields reject. Caller graphs are allowed only by the explicitly analytical
`price_candidate` helper, never the source public boundary.

Results keep both `operational_admission` and `full_n1_acceptance` false. These are
uncontended work-cost estimates, not event times, runtime paid integrals or forecasts.
Actor availability, simultaneous arrivals, queues, port windows, competing buffer
leases, receipt processing, traffic, downstream all-cargo execution and B2B handoff
remain outside this decision. No fake CoordinatorProfile, worker, stock, engine,
HTTP/API or live world mutation is constructed. Baseline remains the original
source assignment; any selected placement is a separately retained projection.

## Validation

Tests precede implementation. Independent hand checks cover gross16/full-cost22,
directed return, complete-operation ceiling, denied loaded shortcuts and metric
substitution. Source tests preserve every offered row and exercise feasible/unpriced,
infeasible and evaluated-negative cases. Independent review reproduced weighted
cost/length mismatch and unrelated receipt-module overload before their guards were
added. Source reauthentication, canonical metadata and exact nested type controls
remain required. Root owns composed integration and full N1 completion.
