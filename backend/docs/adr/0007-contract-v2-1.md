# 0007. Contract v2.1 proposal for the run export

Status: proposed, 2026-11-07. Needs Tilek's agreement before files in `contracts/` change.

The current `contracts/run.schema.json` (2.0) stays a valid logical projection. The proposal adds:

- A discriminated payload schema for each event `kind`, with `additionalProperties: false`.
- `phase` limited to 0..4, and `at_tick` (exact integer time) next to `at_s`.
- Actions: TRAVEL requires at least two waypoints and no `pos`; other states require `pos` and no waypoints.
- Typed snapshots with `last_seq`, `state_hash` and the full mutable state (actors, cargo, inventory, queues,
  totes, stations, pallets, merge cursors, timers).
- A run manifest plus chunks covering `[k*60, (k+1)*60)`, each with first/last seq, byte size and sha256.
- Metrics split into `at_horizon` (window `[0, H)`) and `at_end` (after drain).
- Termination per subsystem, with a reason list and one primary reason.
- A compact atomic transfer record for conveyor moves, with a documented adapter to `cell_exited`/`cell_entered`.

The full list of gaps is section B of `../research/2026-11-07-codex-edu-spec-audit.md`.
