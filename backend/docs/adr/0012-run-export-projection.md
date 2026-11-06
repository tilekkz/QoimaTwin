# 0012. Inline v2 projection and proposed transport envelope

Status: accepted for backend; transport and fixture additions remain proposals for Tilek.

The shared v2 schema forbids additional top-level fields. Keep run.json valid against that
unchanged schema. Publish complete identity, provenance, end time and horizon/end metrics
in a separate manifest with transport_version=qoima-run-bundle-1-proposal.

- Record each compact CellTransfer's offset into the domain journal when it happens. Merge
  transfers at this anchor in phase 2, expand each into adjacent exited/entered events sharing
  a transition_id, and assign contiguous public seq values after projection. Domain seq and
  public seq are different; snapshot watermarks use the last public event at or before T.
- Boundary transfers also have pairs. Their external endpoint identifiers (`inlet`, `PKxx`,
  `SHIPPING`) are containers, not extra physical conveyor cells. Only IDs in layout's cell
  registry affect cell occupancy. The from/to container fields define the complete transfer.
- Pallet cargo has empty contents and order references; pallet_sealed supplies its parcel
  children. Goods remain counted in the leaf parcels. Reusable tote catalog entries start
  empty; events and snapshots supply their changing contents/ownership.
- Snapshots contain mutable state and a nested checkpoint watermark/hash. state_hash hashes
  the state excluding the checkpoint metadata itself. They are replay snapshots, not restart
  checkpoints (ADR0010).
- Chunks own events on [k*60,(k+1)*60). An event on the final exact boundary gets a next chunk.
  Intersecting actions repeat with stable action_id; clients deduplicate these immutable
  intervals. Snapshot ownership uses the same half-open boundary rule. Empty chunks remain.
  catalog.json supplies initial state and immutable identities without downloading inline history.
  Events carry exact at_tick inside payload because v2 forbids it at the event envelope level.
- At a drain cutoff actions are clipped to executed time. A cut inside a graph edge ends at an
  interpolated position with virtual waypoint ID `@cutoff:from:to` (not a warehouse graph node).
  Still-open induction/output BLOCKED intervals end at the cutoff; no completion event is invented.
  Embedded snapshot actions use the same clipping; their projected state hash is recomputed.
  An action scheduled exactly at termination has no executed interval: keep the actor's state
  and start position, with no motion interval. Replay clamps its clock to ended_at_s.
- Hash exact UTF-8 file bytes, publish each file atomically and manifest last. Readers must
  verify sizes/hashes. run.json is an inline convenience copy; count its bytes separately from
  the chunk transport as well as in total on-disk bytes. No compressed-size substitution.
- Identity includes engine version, canonicalization and identity versions, exact timebase,
  horizon, scenario ID, experiment and hashes for layout/config/actors/orders/receipts/stock/placement.
  Plan and forecast hashes are explicit null-artifact hashes until those inputs exist.
  Stock excludes slot placement. Integer-valued floats normalize to integers in identity
  hashing only; generic canonical_bytes preserves number types. Ordered routes remain ordered.
- Before task D the v2 metrics projection exposes actual end counts/cycles/backlog and ledger;
  role/queue/conveyor fields are empty, never invented measurements. Task D supplies these
  summaries with explicit observation windows.

The CLI uses the supplied illustrative assignment, not a claimed trained ABC placement.
Shared schemas and frontend files stay unchanged. Proposed fixture files are clearly labelled.
