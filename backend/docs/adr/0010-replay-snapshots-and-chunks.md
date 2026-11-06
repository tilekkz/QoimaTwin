# 0010. Replay snapshots and event chunks

Status: accepted for the backend, 2026-11-07. The exported field layout still goes through ADR 0007 with Tilek.

## Context

05 §10 items 3-5 need snapshots every 30 s with the complete mutable state, and 60 s chunks with no lost or
repeated event at a chunk or snapshot boundary. ADR 0001 hoped a snapshot could also restart the engine.
In the current engine every pending scheduler item holds a Python closure (`lambda`/`partial` over subsystem
objects). These closures cannot be serialized, and some state lives only inside them.

## Decision

### Snapshot boundary

- Boundaries are `T = k * snapshot_interval_s` (30 s), `k >= 0`, for every `T <= end_tick` of the run.
  For a drained run `end_tick` is the last settled tick. For a max-drain stop it is the deadline.
- The snapshot at `T` is the state after all phases of all ticks `<= T`. It covers exactly the events with
  `at_tick <= T`. `last_seq` is the seq of the last such event, or `-1` when there is none.
- Snapshots are taken on the scheduler's settled-tick hook (`Engine._on_tick_settled`), not by scheduling
  `Phase.CHECKPOINT` items. A hook call `(settled, next)` emits every boundary in `[settled, next)`: nothing changes
  between two settled ticks. Boundaries before the first scheduled tick are taken in `Engine.__init__` from the
  initial state.
- The checkpointer never schedules anything. It cannot keep a drained run alive or move its end tick
  (the analytical fixture still ends at 474 s; its last snapshot is at 450 s).
- No extra snapshot is taken at `end_tick` unless it is a boundary. Replay reaches the final state by applying the
  events after the last snapshot.
- Hook composition: `Engine._on_tick_settled` is the only hook. Invariants run first, then queue observation
  (ADR0011), then the checkpointer, so a snapshot is never taken of a state that failed its invariants.

### Snapshot content

`Snapshot(at_tick, last_seq, state_hash, state_bytes)` is a frozen dataclass. The state exists only as canonical
JSON bytes (`qoima-json-v1`). `state_hash` is SHA-256 over those bytes. `Snapshot.state` decodes a fresh copy on
each access, so neither the caller nor the running engine can change a stored snapshot.
`Engine.checkpoints.snapshots` returns them as a tuple for the exporter.

| Section | Content |
|---|---|
| `actors` | State, fixed position or `null` during TRAVEL, and the full active action (with waypoints) |
| `conveyor` | Cell occupancy, cargo descriptors, pending admissions with ready tick and owner, merge cursors |
| `ledger` | Balances and reservations per holding, per-order claims (unpicked lines), accepted receipt units |
| `orders` | FIFO, picking ownership, current status per order and cumulative counts; no milestone history |
| `totes` | Independently tracked free and allocated pools, sorted |
| `stations` | Waiting FIFO, tote in service, cargo-to-order descriptors, blocked parcel/start, reserved WIP |
| `shipping` | Buffer, open pallet (parcels, reserved slots, first placement, generation, expiry tick), sealed queue, scans in progress, outbound forklift tasks and carried pallet |
| `receiving` | External FIFO, receiving area with states, inbound forklift busy flag, staging used, counts |
| `timers` | Pending scheduler descriptors `(tick, phase, key, seq, unique)`, cancelled items excluded |

Not included: the event and action history, immutable inputs (layout, catalog, orders, receipts, initial lots) and
metric accumulators. Metrics belong to the metrics module (B7); the exporter projects its summaries.

Two parts of the state live only inside closures and are rebuilt from records:

- The pallet on the outbound forklift between pickup and dispatch: from the `pallet_sealed` event (parcel IDs) minus
  pallets still in the sealed queue, until `order_dispatched` for that pallet.
- An actor's current activity: from its action intervals. An actor without a covering action that still holds
  work in domain state (picker waiting for the feed, packer with a blocked parcel) is `BLOCKED`. Otherwise it is
  `IDLE` at the end position of its last action, or at its initial position.

The capture reads `Ledger` private maps and `PhaseScheduler._buckets` read-only. Public read-only accessors would
be cleaner; they are left to the owner of those modules.

### Not an engine restart point

A snapshot is a replay snapshot. There is no `Engine.restore`. The `timers` section lists when and where pending
work runs, not what it does, so the engine cannot continue from a snapshot. Restart means a deterministic re-run
from the same inputs (same `run_id`, same event stream, ADR 0008). A future resumable checkpoint needs typed
handler descriptors (handler kind plus plain arguments) for every scheduled item; that is a separate decision.

### Chunks

- Chunk `k` covers `[k * chunk_duration_s, (k + 1) * chunk_duration_s)` (60 s). An event exactly on a boundary
  belongs to the next chunk.
- Chunks cover `0 .. end_tick // chunk` contiguously. Empty chunks are kept (`first_seq = last_seq = null`), so a
  terminal event on a boundary has an owning chunk.
- `split_events` rejects gaps in `seq`, time going backwards, and events after `end_tick`.
- Seek to `target`: take the last snapshot `S` with `S.at_tick <= target`, then apply the events with
  `seq > S.last_seq` and `at_tick <= target`. The snapshot at `k * 60` lies in chunk `k`; its `last_seq` already
  includes chunk `k`'s events at tick `k * 60`, so they are not applied twice.

## Consequences

- Tests: `tests/unit/test_checkpoint.py` (boundaries, limit, isolation), `tests/unit/test_chunks.py`,
  `tests/unit/test_snapshot_state.py`, `tests/acceptance/test_snapshots.py` (fixture boundaries 0-450 s, 05 §10
  items 3 and 5, determinism, max-drain cap).
- Acceptance C5 (snapshot between merge grants) is met for replay: the cursor is in the snapshot. It is not met
  for engine resume, which does not exist.
- The capture cost per snapshot is the size of the mutable state plus the new events and actions since the last one.
