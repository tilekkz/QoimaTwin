# ADR 0055: Native connected receipt inventory publication

Status: proposed backend implementation; no shared frontend contract agreement.

## Context

ADR 0052 freezes the source-bound receipt process and ADR 0053 executes it on the
connected light-flow clock and stock authority. A receipt creates previously absent
unit tokens and its original wrapper at completed intake service. The existing
connected SMALL publication assumes a fixed initial unit/container universe and
therefore cannot represent this new accounting meaning without a separate version.

## Decision

The native schema is `qoima.connected-receipt-small-run.v3-proposal`, version `0.1.0`.
Its bundle schema is `qoima.connected-receipt-small-manifest.v3-proposal`. Publication
version `qoima-receipt-publication-0.1.0`, native receipt engine version and the exact
frozen input SHA256 jointly determine the run identity. Existing light publication
IDs and bytes remain unchanged.

The source compiler identity and explicit route policy are verified against the
trusted pinned source loaders by reconstruction. A protocol-shaped object is not
authority: exact nested runtime types, canonical materialized profile, initial
inventory, process, H/end and raw input bytes must agree. The separately identified
hand-fixture compiler permits only `explicit-hand-receipt-fixture-v1`, with no source
revision claim. Source compilation requires the ADR 0052 C09 permission projection
policy. A canonical source dictionary does not certify a physically different typed
profile, including a dictionary impersonating a Fraction.

The execution helper also checks its separately supplied conveyor before publishing
inputs or constructing the engine. Exact nested source types and immutable document
bytes must match the verified pinned loader, and its canonical physical values must
match the frozen source conveyor. The named hand-fixture compiler uses that same
fixed pinned conveyor context; it does not permit an alternate implicit belt speed.

Immutable inputs are published before engine construction. Output must initially be
empty; failure leaves input evidence and never publishes a success manifest. The
writer accepts only empty output or the exact prewritten `inputs.json`, writes raw
immutable files exclusively and publishes the manifest last. Neither writer nor
reader offers a validation bypass. Builder `validate=False` only defers the final
wire schema/journal pass to the mandatory writer; input and native immutable binding
remain enforced.

## Inventory and observation semantics

Catalog `initial_units`/`initial_containers` are actual baseline existence. Separate
`declared_receipts` contain future unit descriptors, original HU/lot ancestry and the
wrapper recipe reference. Their presence grants no stock credit. A `receipt_creation`
delta at completed intake service carries the definition and all created tokens;
ordinary stock deltas cannot create units or wrappers. Exact source recipes remain in
the catalog, not copied into mutable checkpoints. Native definitions/recipes/tokens
are checked before projection removes their duplicate fields.

The validator reconstructs actual inventory through contiguous atomic revisions,
checks before/after contents, unit selection, scalar masses, SKU counts, owner
capacities and actual creation. It separately checks inventory claims, same-tick
operational triggers, finite receipt resource ownership and current receipt custody.
Claim generation and registered-receipt IDs must match captured state. Credit needs
an eligible receiver and actual completed service fitting the source window and H.
Whole-HU protection persists through putaway; exact pick claims protect requested
units. Claims are checked after every journal event, so a balanced move away and back
between captured checkpoints cannot evade the reservation. Receipt credit and buffer/
slot handoffs require an actual completed operation by the same assigned actor, with
the exact operation previously started; explicit handling duration and physical place
must agree. Finite port acquisition is paired with every service start, even when the
entire service occurs between captures. Business putaway and paid receiver return are
separate observations.

Events have contiguous sequence and one exact microsecond clock. A checkpoint at T
contains the settled state after all events with tick <= T, anchored by `last_seq`.
Captured checkpoints include 0, every 30 s through actual end, H and actual end;
when complete before H the later H view is retained. Plans ending after an observation
are open operations, never fabricated completion events. Complete status requires
completed outbound business, completed admitted receipt returns, no open human/cart/
belt operation or waiting marker, and no resource/claim leak.

The reused light metrics describe outbound business and all-worker exposure. Separate
`receipt_metrics.at_horizon`/`at_end` report arrived, credited/created units, putaway,
return, outstanding work and receiver resource exposure. Counts are inclusive settled
observations; exposure remains a duration over [0,T). No inferred receipt throughput
or business cycle is substituted for these explicit facts.

## Transport and limits

Event and checkpoint files use half-open 60 s buckets with a configurable raw byte
limit capped at 8 MiB per file. A single item exceeding the limit fails publication.
Descriptors bind raw SHA256, size, relative path and actual tick bounds; the manifest
has a strict JSON Schema and unique contained paths. Readers verify every descriptor,
the full native schema/journal and exact input/catalog binding even when selecting
an early event window. Event selection is at most 60 s; checkpoint selection accepts
only an actually captured tick.

This implements captured-state retrieval, not arbitrary replay, interpolation or
engine restoration. Mutable stock checkpoint rows do not contain recipes, ancestry
or event history. Whole-reader memory and total transport size are not bounded by
the individual chunk limit. Repeated source reconstruction/schema/raw hash validation
is intentionally retained pending a separately reviewed optimization.

The artifact flags actual component execution and internal receipt inventory
integration; full V3, frontend adapter, arbitrary seek, interpolation and physical
hand-contact proof remain false. Synthetic materials/process timings remain explicit.
The native JSON decoder only reconstructs known data records to reuse a previously
executed, hashed outcome; it does not execute serialized Python objects. Its result
still passes the same writer checks. It is not a public resume or HTTP input format.

## Independent arithmetic and checks

Hand fixture: existing 24 units + receipt 24 = 48; shipment 3 leaves 45 onsite.
At 1 m/s approach 2 s + service 10 s credits at 12 s. Buffer carry 3 s + place 1 s
+ pickup 1 s + slot carry 5 s + place 1 s gives putaway 23 s; return 10 s gives
receiver release 33 s. H=11 cannot admit the service, H=12 credits but leaves the
carry operation open. An explicit arrival at 60 s belongs to the second event bucket
while the 60 s checkpoint includes its settled admission.

Pinned source accounting: 12,256 baseline units + 24 received - 3 shipped = 12,277
onsite. Source goods 9,403.85 kg + carrier .20 kg + parcel .05 kg + receipt .94 kg
= 9,405.04 kg; shipment .155 kg leaves 9,404.885 kg onsite. Source route clocks are
measured outcomes, not manufactured numerical acceptance oracles.
