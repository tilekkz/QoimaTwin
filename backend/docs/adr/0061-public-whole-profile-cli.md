# ADR 0061: explicit public whole-HU profile and bounded CLI

Status: accepted backend proposal; no shared frontend contract approval implied.

## Context

ADR0056 binds a typed SMALL/STANDARD whole-HU scenario to pinned source facts.
ADR0058 publishes that scenario with one ledger, calendar and worker registry.
Its full immutable physical input is deliberately not a convenient authoring
format. A CLI needs reviewable choices without allowing source-derived geometry,
service times, access permissions or inventory to become caller overrides.

## Decision

`v3 simulate-whole --profile FILE --out DIR` accepts the separately versioned
`qoima.whole-flow-profile.v3-proposal` 0.1.0 document. The new schema derives a
fresh schema object from the receipt vocabulary; old schemas remain unchanged.
All 24 actors, homes, speeds, capacities and availability, material recipes,
containers and owners, cart, station, local buffers, handling times, arrivals,
H/end, unit placements and whole-HU jobs are explicit. There are no implicit
workers, replenishment pools, workload rates, material quantities or service
defaults.

The existing verified source binder derives the full 530-HU baseline, slot and
worker/cart anchors, L08/belt route, port windows and per-class services. It
checks explicit local connectors against source zones/walls/clearance, and uses
the established absent-only C09 manual permission projection. Explicit source
denials remain denials. Public input cannot override those derived facts.
Receipt credit still requires source inbound service completion at or before
min(H, port close). Job admission is [0,H), and an admitted outbound operation
may drain within its source window and end cap. Paid return remains observable.

The current source binder supports original/future SMALL or STANDARD intact
whole HUs, one offered class per inbound port, and original baseline SMALL unit
orders. Future unit orders are rejected explicitly. Accounting support for other
classes does not grant their physical execution. Mesh hand contact, full N0-N4,
forklift operations and HTTP admission are not supplied by this command.

JSON uses exact integer ticks and numerator/positive-denominator rationals.
Booleans, floating values, unknown keys and duplicate table identities reject.
Rationals reduce and unordered actor/owner/material/recipe/job/port/buffer tables
sort by identity; path and unit placement order remain significant. Normalized
choices bind `qoima-whole-flow-public-profile-0.1.0` in a public request receipt.

The unchanged ADR0058 outer input hash binds physical input bytes and H/end.
The public choices hash and request receipt hash are separate identities. Two
equivalent notations can share normalized choices and native run identity;
a change in public request compiler version is represented by the request
receipt rather than silently changing the old native envelope or run namespace.
The physical artifact retains its source compiler version and source hashes.

Before the first request file is published, exact typed compiled values are
checked against their immutable envelope and a canonical recompilation of the
public choices. Independent choices and input hashes are not sufficient proof
of that relation. A bounded two-entry cache stores only immutable source-bound
input bytes; each caller receives a fresh typed profile, and `verify_inputs`
still checks the supplied typed state and source authority on every publication.

## Publication and failure behavior

The output directory must be absent or empty, and must not be a symlink.
Exclusive raw-byte publication prevents overwriting existing files. Before engine
construction, the command writes canonical `profile.json`, `request.json` and
`run/inputs.json`. The request binds public compiler version, choices SHA-256,
outer input SHA-256, physical input SHA-256 and exact H/end. Nested `run/` keeps
the existing writer's policy permitting only its exact prewritten inputs.

One shared `WholeFlowEngine` execution produces the unchanged whole publication.
`run/manifest.json` is published last after mandatory validation. `result.json`
and stdout identify the actual manifest path/hash, run ID, input identities and
request receipt hash. They retain real status and bounded capability flags.
`partial` and `failed` return nonzero. Execution/publication failures retain the
already frozen request and inputs, plus a structured failure result when it can
be safely written. No failed result is promoted to complete, and a failed attempt
must use a fresh directory for retry. No automatic retries occur.

## Example and validation

The example explicitly declares a STANDARD DEMO_111 receipt of 24 units into
free FLEX_W:001:L1:B1 through IN_N_STANDARD, then whole outbound through
OUT_W_RETAIL. H=2000 seconds and end cap=4000 seconds; source services are 18 and
35 seconds. Worker speeds and handling durations, buffer connectors and the
unused carrier/parcel are synthetic declared choices. The .32/.24/.24 carrier
with .20 kg tare is not an M07 asset or contact proof. The selected worker
connector is .7 m wide; this document does not claim carrier shrinking was needed.

Before execution the source arithmetic is fixed: 12,256 baseline units +24
received =12,280 total, then 12,256 onsite +24 shipped. 9,403.85 kg baseline
+0.20 kg carrier +0.05 kg parcel +6.35 kg received STANDARD =9,410.45 kg total;
final onsite 9,404.10 kg +shipped 6.35 kg. All 530 original wrappers and 24 actor
identities remain. Route timestamps and elapsed time are observations, not
analytical oracles or benchmark claims. Source CLI validation executes once
under Python `-O` after focused schema/compiler/command checks.
