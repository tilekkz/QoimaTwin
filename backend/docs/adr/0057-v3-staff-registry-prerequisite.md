# ADR 0057: Source-bound staffing registry and analytical exposure prerequisite

Status: accepted for the bounded registry prerequisite; dynamic N4 execution is deferred.

## Context

The adaptive V3 brief sections 1, 7 and 10 require a staffing comparison to keep the same
24 workers and common workload, stock, geometry, service, equipment and downtime. Only
declared role allocation changes. `DOWNSTREAM_DESIGN_NOTES.md` proposes a common K05/K06
break, temporarily covering the existing PK05/PK06 with cross-trained P11/P12 and paying
their transitions and restoration. That is a candidate design, not an implemented norm.
These documents are pinned at `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`. C12 examples are
not source authority for staffing abilities, break periods, service or travel duration.

The current connected runtime selects one picker, packer, cart and station, with an
initial actor availability threshold. It has no dynamic six-station staffing coordinator.
This decision does not modify that runtime or claim an N4 result.

## Decision

Add a pure immutable registry and analytical exposure calculator. Neither contains a
calendar, worker ownership map, task scheduler or live resource grant. Future integration
must use the existing common light/receipt/whole calendar and actual 24 identities.

`compile_staff_registry(document)` strictly parses decoded JSON version
`qoima-staff-registry-0.1.0`. All fields are required; extra fields and nested coercions
are rejected. Lists represent sets and are sorted only after duplicate validation.
Integer microsecond ticks exclude `bool`, floats, negative values and empty periods.
Unavailable intervals are half-open and cannot overlap for an actor; adjacent periods
remain distinct and retain their reasons. JSON callers should use the existing strict
`app.storage.canonical_json.parse_json` before compilation to reject duplicate object keys.

The registry binds exact source IDs P01..P12, K01..K06, R01/R02, S01/S02 and F01/F02;
their primary roles are respectively pick, pack, receive, ship and forklift. These are
roster identities, not a rule for inferring an effective role after future reassignment.
Primary skills must be present. Additional skills and permitted equipment are explicit
common assumptions, identical in A/B. Source FL01/F01 and FL02/F02 pairs are retained;
`manual_cart` is an equipment eligibility tag, not a materialized cart or a live grant.
No forklift eligibility exists without the corresponding source vehicle permission.
These checks are not proof of physical handling, equipment availability or certification.

All six primary station bindings are explicit, unique and refer to source packing actors.
The station registry distinguishes pedestrian service anchors from cargo WORK nodes:
PK05/PK06 workers are at `(106,0,6.1)` / `(117,0,6.1)`, while WORK anchors have Y=0.92,
Z=5.3. Existing shared receiver/shipper IDs and source spur references remain visible.
Bindings and equipment declarations cannot create extra desks, vehicles or people.

The implementation reads only the exact pinned staffing subset:

- `port-resource-policy-v3.json`, checked using the pinned fourteen-file provenance.
- `layout-links-v3.json`, checked using that same pinned provenance.
- The existing immutable conveyor supplement `conveyor-v3.json`, checked against its
  pinned raw size and SHA256 in `conveyor_source.py`.

This is a three-file staffing projection, not a fresh validation of the full fourteen-file
bundle or all 27 original proposal documents. Source bytes are reread and rehashed on
compilation, equality checks and analytical use; caller-reported hashes are never trusted.
Retained typed values are rechecked, including `bool`/integer aliases and nested containers.
No input source, shared schema or frontend file changes.

## Identity boundary

`registry_common_hash` hashes the registry version, verified source facts/fingerprints,
capabilities, unavailability and primary station bindings. `require_same_registry`
revalidates both exact typed registries and compares their canonical bytes. Input set
permutations preserve identity; a change in common capabilities, windows, equipment or
bindings does not. `analytical_allocation_hash` separately hashes explicit cover choices
under `qoima-analytical-staff-allocation-0.1.0`. Its caller must compare common registries
separately; the allocation hash alone says nothing about their equality.

Neither hash proves equality of orders, inventory, route planners, ports, geometry beyond
the staffing subset, service recipes, material pools or complete physical A/B runs. A
future compiled common-run identity must independently bind and validate those facts.

## Analytical covers and hand oracle

`AnalyticalCover` supplies helper, station, start/end and positive outward/return ticks.
These are declared synthetic durations, not computed directed routes or observed work.
A cover requires an explicitly eligible non-primary packing actor, an uninterrupted
available helper and a primary station actor whose common break covers the whole period.
Overlapping covers cannot share a helper or station, including transition periods.
This metadata consistency does **not** establish that a station or actor actually released
its current operation, cargo, cart, claim or lease. That remains a runtime prerequisite.

`analyze_staffing` partitions an arbitrary half-open observation window into effective
scheduled role, transition and unavailable person-ticks. `schedule_eligible_actor_ids`
reports scheduled eligibility at the exact tick; it is not actual task availability.
Zero-width observation windows return zero exposure. During a declared transition the
helper is eligible for neither picking nor packing. Every one of the 24 actors is counted
exactly once; identity never changes. Results expose `operational_admission=False` and
`full_n4_pass=False`.

The independently written synthetic oracle uses a common K05/K06 break `[100,160)` s,
P11/P12 clean at 100 and truly released PK05/PK06. Explicit bidirectional 6 m / 9 m routes
at 1.5 m/s imply 4 s / 6 s each way. P11 packing eligibility is `[104,156)` (52 s), P12
`[106,154)` (48 s). Thus baseline four packers give 240 person-s; the candidate gives
340, not 360. Paid transitions take 20 person-s. Helpers lose 120 picker-eligible person-s,
split into 100 packing and 20 transition. Total roster exposure is 1440 person-s: common
unavailability 120 and candidate task eligibility 1300 plus transitions 20. At 105, extra
packing is 1 person-s and transition is 9. If P11 is only clean at 110, declare that later
start: its packing window is 42 s, and combined extra exposure becomes 90.

These calculations are availability identities, not orders completed, actual utilization,
route feasibility or predicted improvement. Primary packers at break end are scheduled
eligible; any real paid approach remains unimplemented. No forced job cancellation or
implicit physical handoff is performed by this pure calculation.

## Deferred coordinator requirements

Stages B/C must preserve actual ownership release before role activation, pay movement
from real nodes, use one shared calendar, and perform real six-station dispatch. A common
break cannot free an occupied station by assertion. Restoration deadlines require a
provable complete work/clear/return bound: unbounded downstream waiting invalidates that
proof. Reject unproven admission; never invent a worst-case duration, interrupt an owned
task, teleport or hide a missed deadline. Returning exactly at a deadline requires actual
completion/release before same-tick primary reavailability.

Role-aware metrics must stop attributing work solely by ID prefix. Future observation
coverage through H must be distinguished from business/resource completion because the
current early-complete runtime can stop before future calendar changes. Those are new
versioned runtime/outcome/publication decisions, not changes to old artifacts or IDs.
N4 remains open until a genuine common-input paired runtime test verifies these behaviors.
