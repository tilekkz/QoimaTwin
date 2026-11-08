# Coordinator settled replay API proposal

This is the public read integration of ADR0072 for the native coordinator namespace.
Its implementation and prewritten tests remain **NOT_RUN_USER_DEFERRED** until the
user's final verification phase. It does not enable a frontend adapter or full V3.

```
GET /api/v3/coordinator-runs/{run_id}/replay?tick=102000000
```

The tick is an exact nonnegative decimal microsecond integer, with no sign,
fractional notation, Boolean notation, leading zero or whitespace. It must not
exceed the run's actual observed boundary. Zero and the observed boundary itself
are allowed. Existing API validation returns422 for malformed or future queries.
An unknown public run returns404 before lazy server registration is attempted.
Missing or corrupt evidence for a known run is500 artifact_corruption.

The endpoint first uses the existing registered-profile and complete native/outer
inventory verification. Every request rehashes raw input and artifact bytes even
when the existing semantic summary is cached. It reads the exact verified frozen
inputs and reconstructs the native run through the strict C65 reader. ADR0072 then
creates a fresh data-only journal and applies all actual events with tick<=T.
It does not instantiate, run or restore an engine, scheduler or callback.

The response has these fields:

| Field | Meaning |
| --- | --- |
| reader_version | `qoima-coordinator-settled-replay-api-0.1.0` |
| scope | `verified_native_settled_state` |
| run_id / native_run_id / input_hash | Existing verified public/native/frozen-input identity |
| tick | Requested observed cutoff |
| last_seq | Last applied event, or-1 for an empty prefix; also retained in snapshot |
| observed_until_tick | Actual run observation boundary, never a planned future end |
| state_boundary | `after_all_observed_events_with_tick_lte_T` |
| reader_capabilities | arbitrary_settled_state=true; engine_restore, geometric_interpolation and full_v3=false |
| snapshot | Compact mutable coordinator state using the existing native capture vocabulary |

Snapshot retains current stock locations and owners, credited receipt IDs, revision,
claim generation/claims, all workers/carts, operations, packing, role state/exposure,
queues, unit contexts/progress, belt state and resource leases. Container recipes and
unit ancestry stay in frozen input authority; no history, event list or checkpoint
list is embedded. A typed roundtrip verifies the compact definition references.
Newly received ownership is absent before actual receipt credit. This projection
does not manufacture current registry state from future declarations.

State changes atT are included. Paid exposure stops at[0,T); a worker in motion
keeps the actual route and planned end without inventing a completed node/pose.
The existing native belt observation remains exact; this endpoint introduces no
worker or mesh interpolation. Backward and repeated reads start with fresh journal
state and leave source artifacts unchanged.

`/checkpoint` still requires an exactly captured tick; `/events` keeps its bounded
half-open window. Status, registered-profile metadata, result cache and immutable
native manifests are unchanged. Their previous captured-state capability fields
are not rewritten to claim this new reader feature: the `/replay` response declares
its own reader capability explicitly.

There is no fast-seek, bounded-memory or latency claim. The current implementation
verifies the complete bundle and reduces from initial authority for each request.
Tests authored before execution cover exact captured equality, roles102/104 and
open paid return158..160, backward/repeated requests, compact definitions, receipt
credit12, source/input corruption after a warm read, unknown/known error ordering,
strict query forms and a guard against calling CoordinatorEngine.run.

The existing HTTP test fixture patches registration only to exercise the hand
world; it is not evidence of public analytical-fixture admission. Final source
HTTP/readback checks must use the registered source profile on the final candidate.
