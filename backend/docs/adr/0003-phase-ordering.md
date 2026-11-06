# 0003. Phase ordering inside one timestamp

Status: accepted, 2026-11-07.

| Phase | Work |
|---|---|
| 0 | Timed completions and resource releases; pallet age expiry intents |
| 1 | External order arrivals and receipt arrivals at the boundary |
| 2 | One atomic conveyor tick, then feed/outfeed admissions (integer seconds only) |
| 3 | One coalesced dispatch cycle, repeated to a fixed point: mark SEAL_PENDING, seal, create forklift tasks, start services, assign FIFO orders |
| 4 | Snapshot and invariant checks; no business work |

Rules enforced by `PhaseScheduler`:

- No scheduling into the past.
- No scheduling into a phase that already ran at the current tick.
- Exactly one conveyor tick per integer second while the conveyor has work.
- Inside a phase, items run in stable key order (actor ID, station ID, `(ready_tick, cargo_id)`,
  `(arrival_tick, order_id)`), then by scheduling sequence.
- The exported `seq` is a separate counter assigned when an event is emitted.
