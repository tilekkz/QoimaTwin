# Registered coordinator API proposal

The local API exposes one pinned source profile through `GET /api/v3/coordinator-profiles`.
Submit its `profile`, `layout_version` and `source_revision` to
`POST /api/v3/coordinator-runs`. Requests use the existing shared calculation worker and an
immutable source/request key. Arbitrary paths, raw profiles and overrides are not accepted.

For the returned public run ID:

- `GET /api/v3/coordinator-runs/{run_id}` returns actual native status, completion boundaries,
  staffing results and metrics.
- `GET .../manifest` returns native transport and authorized native/outer file inventories.
- `GET .../files/{artifact_id}` returns the exact validated JSON bytes named by a listed hash.
- `GET .../checkpoint?tick=158000000` requires an exactly captured tick.
- `GET .../replay?tick=158000001` reconstructs mutable settled state at any observed
  integer tick, including all events through that tick. See the separate
  [replay contract](v3-coordinator-replay-api.md) for response fields and scope.
- `GET .../events?start_tick=154000000&end_tick=156000000` selects observed events from a
  half-open interval of at most60,000,000 microsecond ticks.
- `GET .../storage-fullness` returns the separately identified storage report with
  distinct horizon/end observations, bound native/public IDs and the exact input hash.
  Analytical fixtures expose unavailable source capacities. See ADR0085.

Partial runs remain partial when business or physical return work is unfinished. Business
completion, resource drainage, observation end and staffing validity are separate fields.
Role-assignment exposure is not busy utilization. Native namespace3 state preserves all carts,
workers, role bindings, unit contexts and packing state.

Every access rehashes known raw evidence before semantic cache reuse. Unknown public resources
are404; corrupt/missing server evidence is500; invalid request or window bounds are422.
The whole bundle is validated before selecting a view, so these endpoints make no bounded-memory
or streaming promise. The replay reader does not restore a running engine or interpolate
worker geometry. Frontend adoption and complete V3 workflows remain separate work.

The implementation and its prewritten tests await the user's final verification phase.
