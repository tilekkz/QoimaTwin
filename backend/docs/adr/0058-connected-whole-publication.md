# ADR 0058: Native publication for connected manual whole-HU work

Status: backend proposal, not an accepted shared frontend contract.

## Context

ADR0056 adds intact SMALL/STANDARD outbound and STANDARD receipt to the existing
unit/receipt calendar, 24 actors and StockLedger. The SMALL receipt publication
cannot describe the new claims, original-wrapper ownership or conservative port
reservations. Its namespace and strict reader remain unchanged.

The typed source binder freezes physical inputs without a requested H/end pair.
Attaching an arbitrary profile, conveyor or cap to its hash would not establish
the identity of a published run. Saved native JSON is evidence of one prior DES;
decoding it is neither another DES nor an engine checkpoint restore.

## Decision

Use `qoima.connected-manual-whole-run.v3-proposal` and a separate whole manifest.
The public Python seam is `freeze_whole_source`, `freeze_hand_inputs`,
`load_whole_inputs`, `build_whole_run`, `validate_whole_run`, `write_whole_run`
and `read_whole_run`. No CLI, HTTP or shared contract admission is added here.

The versioned input envelope contains H, end cap, the exact original canonical
physical artifact and its SHA-256. The envelope has a new SHA-256; it never claims
to equal the original physical hash. Run identity binds that envelope hash and
the independent whole engine/publication versions. For source inputs, decoding
reconstructs exact dataclass/Fraction values and the public directed graph,
then repeats the typed binder against repository-pinned source inputs. The
result must equal the original physical bytes. Source graph, local connector,
port service/window and materialization facts are therefore verified together.
Only successful immutable-byte verification is cached; returned profile objects
are decoded afresh. Explicit hand fixtures have a separate named policy and
cannot claim a source revision.

The immutable catalog contains baseline units/containers, declared future
receipts, exact recipes and owners, actual graph/actors, and separate unit,
receipt and whole processes. Future tokens become current inventory only at an
actual receipt service completion. Mutable checkpoints contain current stock,
actual registered receipts and claims, actor/cart/belt state and whole views.
Native recipes and ancestry are checked before compact projection.

A reader reconstructs one inventory journal from contiguous atomic revisions.
Transaction identities cannot be reused. Whole acquisition reserves the complete
existing HU and conflicts with all other claims. Authorized handoffs preserve
its unit ancestry, positions and original wrapper identity/seal:

| Completed stage | Actual owner | Resource consequence |
| --- | --- | --- |
| Source pickup | Assigned worker | Original source slot becomes free |
| Buffer placement | Declared finite buffer | Worker remains assigned |
| Buffer pickup | Assigned worker | Buffer lease is released |
| Port service | Declared shipped owner | Whole claim, port and shipped capacity release |
| Paid return | Worker is at home | Worker lease is released |

The bay is conservatively reserved before buffer pickup and paid approach, as
decided in ADR0056. Reservation exposure and actual per-class service exposure
are distinct. Whole and unit jobs share the exact port identity, while one
actor cannot execute overlapping operations. Whole operation order, actor,
route, clearance, distance/speed duration, handling duration and source window
must match the declared typed plan. A balanced arbitrary baseline wrapper move
is still rejected; permission is attached to the actual admitted whole job.
The selected buffer must belong to that job's port and remain identical in every
whole event from admission/claim through handling, service and paid return. A
different known place, or another permitted buffer, does not inherit the lease.

One global sequence orders unit, receipt, whole and belt events. Counts observe
all events at tick <= T; exposure integrates [0,T). H and actual end remain
distinct captures. Inbound service must finish at or before min(H, port close),
while admitted outbound service may drain after H within its source window and
end cap. A shipped HU with an unfinished paid return is business-complete but
the run remains partial. Planned future operation ends are never completions.

Metrics separate unit orders, whole orders and receipts. Cycles end at business
handover, with exact rational mean and linear p95 in ticks. Common actor paid
operation time is summed once; assigned waiting and total assigned exposure are
reported separately. Whole reservation/service exposure is grouped by port and
archetype. This proposal does not reinterpret legacy metrics.

Publication writes immutable raw-hashed files and publishes the manifest last.
Event/checkpoint chunks use half-open 60-second buckets and an 8 MiB raw limit
per chunk. Inputs, catalog and metadata have their own descriptors. The reader
checks paths, raw lengths/hashes, schema, input binding and semantic history.
Only captured checkpoint retrieval is supported; no arbitrary seek, interpolation,
frontend adapter, client-memory bound or full-V3 capability is claimed.

## Validation and limits

The prewritten hand oracles are original STANDARD shipment47/return52; future
STANDARD credit20/putaway31/receiver-return41 then shipment78/return83; and mixed
OUT_W reservation201.17/service206.17..241.17/return246.17. These numbers derive
from the declared hand graph, handling times and port services, not an engine
result. Partial-at-cap, repaired-watermark forgeries, claim/resource removal,
wrapper-seal changes, actor reassignment and immutable input corruption are
tested separately.

The saved actual-source outcome is decoded as data and published without DES.
Its original manifest supplies the already requested H/end and retains the
earlier external harness retry and pre-review runtime provenance. The unchanged
simple source resource IDs are validated by the new reader; this is not a
two-run determinism claim. Actual source route timestamps remain observations.

Scope remains manual SMALL/STANDARD whole movement plus the existing connected
SMALL unit flow. It does not authorize forklift/heavy operations, N4 role changes,
all six ports, all eight operational classes or production workload rates.
