# ADR0065: Native coordinator publication, metrics and local execution interfaces

Status: code-only implementation draft; tests written first, execution deferred
to the user's final validation phase. No frontend contract adoption.

## Context

ADR0063 adds simultaneous unit jobs with actual independent carts to the shared
receipt/whole/unit calendar, inventory and24-worker map. The old whole publication
has one default cart and one unit context; using it for this coordinator would
discard physical state and validate the wrong port/station authority. ADR0064
provides source-bound frozen coordinator choices. Registry sameness alone does
not establish equality of the physical scenario for a paired comparison.

## Decision

Use a distinct native publication namespace for
`qoima-staff-coordinator-v3-proposal-3`. Public execution accepts only the strict
ADR0064 compiler profile. Publication verifies exact frozen bytes, source binding,
requested horizon/end, native types and materialized physical state before use.
The run identity binds those exact input bytes to coordinator and publication
versions. A separate analytical-fixture helper is permitted for hand tests; its
explicit scope cannot impersonate the public source compiler or grant permissions.

The immutable input contains every source reference, directed graph, initial
stock/material definition, worker/cart/station/port, allocation, registry calendar,
role intent and timing choice. Public graph records contain nodes and directed
arcs, not private lookup caches. The transport stores this immutable input once;
event chunks and actual captures contain mutable state, not copies of input history.

Native captures retain all carts,24workers, current stock/claims, shared leases,
unit contexts/progress, cart release facts, packing ownership, role views/bindings,
effective roles and exposure. The legacy default-cart alias must match its entry
in the actual cart map. It never replaces that map. Global native event seq/tick
ordering remains authoritative across receipt, whole, unit and staffing work.
Readers expose only captured settled states and observed half-open event windows;
planned operation ends are distinct from observed completion. Decoding restores
data values only, never an engine or executable callback.

Semantic validation must bind custody, operation routes, active actors, claims,
cart/bench/port/material reservations and role chronology to the exact input.
Rehashed but physically inconsistent histories must fail. Structural JSON or raw
hash validity alone is insufficient. Whole/parcel terminal capacity is the union
of actual placed containers and active promises by exact owner and container ID.
The new path must preserve the existing receipt-creation and paid-return guards.

## Metrics and identities

Report H and actual end separately. Business completion, physical resource drain,
observation end, staffing status and constraint violations remain distinct fields.
Unit and whole cycles end at actual business handover, not paid worker return.
Mean and linear p95 use reduced exact rational ticks. Queues integrate over[0,T),
while observed counts include settled transitions atT.

Actual paid worker operations are counted once across the common24actors. Role
assignment exposure is not busy time. Whole-roster paid fraction uses24*T;
available-roster fraction removes actual unavailable ticks. Per-role paid fraction
uses actual available assignment time for that effective role. Transition work is
an explicit category and already belongs to worker paid time. Zero denominators
yield null; no ratio is clamped or represented as extra headcount.

`registry_common_hash` proves only registry equality. Paired N0/N4 may derive a
separate common physical identity by recompiling the exact same source choices
with only role_intents emptied. Every other field, provenance, resource, stock,
assignment, clock and source remains unchanged. Both variants and the neutral
baseline must validate normally; an invalid baseline is explicitly incomparable,
not silently normalized into a hash. N1/N2/N3 and C11 planning-proxy relocation
are outside this interface's demonstrated operational scope.

## Interface and validation plan

`build_coordinator_run` accepts verified compiled source inputs or the distinct
analytical-fixture input type and an actual CoordinatorOutcome. The new writer and
reader use their own namespace and strict semantic journal. The CLI will accept
`v3 simulate-coordinator --profile FILE --out DIR`; the API will select a registered
source profile through the existing owned JobService slot. Neither introduces a
second calendar, actor registry or inventory. Shared route/worker/CLI hooks remain
small separately reviewed integration changes.

Unit orders require explicit namespace3 `UnitResources`, including in the hand
input path. Role-only, receipt-only and whole-only analytical cases may omit those
unused resources. This publication does not introduce a singleton fallback and
does not modify the legacy runtime's compatibility path. A worker may first pick
an order and later pack that same order under a real role intent: the journal
keeps distinct task plans and preserves the original completed picker progress.
Co-located role changes emit actual activation/restoration facts with zero paid
movement; they do not fabricate positive operations or borrow the visual timeline.

The data-only semantic journal starts from one baseline StockLedger and applies
its public CAS/claim commands. Declared receipt definitions become registered
only at the actual service-credit fact. Pick consumption is acknowledged before
its stock delta, while whole shipment consumption is acknowledged afterward;
both transitions must finish in the same observed tick and cannot disappear
between captures. Worker/cart plans are reconstructed from immutable input
choices. Conveyor steps are compiled from the pinned physical source and actual
payload, then recorded intervals and finite reservations are checked without
running another scheduler. All actual typed captures are compared with this
journal, including claim generation and all carts/roles/packing contexts.

The bundle has one `inputs.json`, one metadata `catalog.json`, nonempty event
chunks on exact half-open 60,000,000-tick boundaries, and one file for each unique
captured tick. Capture references declare checkpoint/H/end roles, which may share
one byte-identical snapshot. The writer accepts an empty output or its sole exact
preexisting `inputs.json` and publishes the manifest last. The reader rejects
unknown files, path aliases, noncanonical bytes and rehashed semantic changes.
Explicit reader bounds are128MiB per file,1GiB per bundle and2MiB for the manifest;
exceeding them is an error, never truncation. No measured scale or size claim is
made by this unexecuted draft. CLI/request evidence is a separate parent-owned
integration; registered HTTP admission is ADR0069.

Port metrics separate actual service from conservative whole-HU bay reservation
through pickup/approach. They group observations by port, work kind and cargo
class, with source-open exposure on[0,T). The hand STANDARD case reserves40s,
serves35s and ships24units; atH46 its clipped exposures are39s and34s. These are
declared hand arithmetic, not values learned from executing this draft.

Prewritten hand oracles include role exposure621s atH105 with9paid transition
seconds; empty-goods business0/resource160/observation200; all24*200worker-seconds
partitioned into role/transition/unavailable exposure; two carts atcap84; and
candidate unit handovers270.17/301.17 with paid drain306.17 versus baseline
288.254551/319.254551 with drain324.254551. These expected values precede execution
of this package. New tests and implementation are not yet verified. No complete
V3, human-contact, traffic/collision, heavy-handler or frontend acceptance is claimed.

## Pre-release appendix: observed metrics and immutable identity

Before the first coordinator release, ADR0071 extends both observed summary windows
and changes `METRICS_VERSION` to `qoima-staff-coordinator-metrics-v2`. The native
run ID now hashes the canonical object containing `engine_version`,
`publication_version`, `metrics_version` and the exact frozen `input_hash`.
It is still a hash of inputs and declared policies, never of measured output.
Different metric policies cannot silently publish changed summaries under one ID.

Set `PUBLICATION_VERSION` to `qoima-coordinator-run-0.2.0` for this pre-release
semantic change. The native envelope layout and transport descriptor shapes do
not change; `TRANSPORT_VERSION` remains `qoima-coordinator-run-bundle-0.1.0`.
The separate publication bump is required because the current CLI request and
registered API bundle/job key bind the publication version, not the metric policy
directly. Their existing imports therefore change the request evidence, registered
bundle and cache namespace without adding wrapper fields or modifying physical
inputs. The compiler input and bounded registry-common hashes remain unchanged.

Both policy versions are release obligations: future changes to published summary
semantics must advance the metrics and publication versions together while the
request/cache protocol binds only publication. The native metrics binding is an
additional explicit domain boundary, not permission to retain an old API cache key.
Current readers reject the prior unpublished0.1 native schema rather than silently
rewriting its artifacts. Historical draft/source snapshots remain preserved.

Two tests were authored before this isolated correction: an independent standard
JSON/SHA256 derivation using the declared literal protocol, and a changed summary
policy with unchanged physical input. Execution, import-order, wrapper-boundary
and static checks remain deferred to the user's final verification phase. No
passed result or backward compatibility with a released coordinator0.1 is claimed.
