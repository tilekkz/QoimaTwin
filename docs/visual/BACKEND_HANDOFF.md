# Backend handoff for Arman and Tilek

Reviewed on 2026-11-07 from fetched Git objects, without merging the backend branch.
Arman owns the simulation, inventory ledger, business state, metrics, exporter and API.
Tilek owns the scene, visual bindings, replay presentation and client adapter.

| Reference | Exact revision reviewed |
|---|---|
| `origin/arman/backend-core` | `5a0be9d09a8c7ae8b882f011aa342e5250327bb1` — `feat: capture settled replay snapshots and half-open chunks` |
| `origin/main` | `0895f086174599d61ddce148f1508eb57cb03a14` |
| Visual checkout `HEAD` | `4d20f36db84759f839abff0b5649f81a1b2047fe` |

The backend revision is not an ancestor of the visual checkout (`git merge-base
--is-ancestor 5a0be9d HEAD` returned 1). This document records an integration boundary;
it does not represent a merge or approval of a contract revision.

The backend README reports implemented typed contracts, navigation and 179-cell
topology, deterministic scenario materialization,
the end-to-end analytical fixture, and receiving/inbound staging. The reviewed source
directly confirms the event/action recorder, exact time grid, immutable replay
snapshots and contiguous event chunks. The README's “Next” row still groups snapshots
with future work; snapshot/chunk status is more current in commit `5a0be9d` and ADR 0010.
Backend gates were not rerun during this read-only review.

`app/cli.py` currently exposes `validate-contracts` and `materialize`. The reviewed
handoff contains no engine-produced inline Run imported by the frontend. Run export
remains the next integration deliverable. The visual demo remains explicitly synthetic;
its browser QA does not certify backend Run export or business-state replay.

**Current wire format and field mapping**

The shared `contracts/run.schema.json` is still **2.0**. ADR 0007 is a **proposed 2.1**
change requiring agreement before shared contract files change. ADR 0010 is accepted
for backend snapshot/chunk semantics, while its exported field layout still follows
that agreement. The current client accepts inline `schema_version="2.0"` with
`layout_version="qoima-72x48-v2"`; it does not accept 2.1 automatically.

| Backend record | Current inline 2.0 projection / client use | Export agreement needed |
|---|---|---|
| `Event.at_tick` | `at_s = grid.to_seconds_float(at_tick)` | Keep integer ticks internally. An exported `at_tick` field belongs to agreed 2.1, since 2.0 forbids extra event fields. |
| `Event.seq`, `phase`, `kind`, `entity_id`, `payload` | Same logical fields; client orders by `(at_s, phase, seq)` | Preserve a unique deterministic exported sequence, phases 0–4, and typed payload meanings. Recorder payload is currently a dictionary; per-kind wire validation is part of ADR 0007. |
| `Action.start_tick`, `end_tick` | `start_s`, `end_s` through the same grid conversion | Preserve half-open `[start,end)` intervals and no overlap per actor. |
| `Action.action_id`, `actor_id`, `state`, `operation`, `entity_id` | Same fields; nullable `entity_id` remains explicit | Keep stable actor/cargo/vehicle IDs; do not turn a vehicle into an additional employee. |
| `Action.pos` or `waypoints` | Stationary states use `pos`; TRAVEL uses waypoint `{node_id,pos,at_s}` records | Convert every waypoint's `at_tick`; omit the unused geometry field. Waypoint endpoints must span the action. |
| Run metadata, 24 actor definitions, cargo descriptors and initial state | Required around the recorder output by the shared schema | Export versions, input hashes, roles/initial positions, contents/order links, horizon, status and termination from backend inputs/state. The action journal alone is not a complete Run. |
| `CellTransfer(at_tick,cargo_id,source,target)` | Logical `cell_exited` / `cell_entered` events with a shared transfer identity | Define deterministic expansion, inlet/service exits, and payload `cell_id`, container links and `transition_id`. One physical transfer must remain one transfer. |
| `Snapshot(at_tick,last_seq,state_hash,state_bytes)` | 2.0 allows only `{at_s,state}` at the snapshot envelope; current client treats `state` as opaque | Agree typed state and cursor/hash representation in 2.1. Do not add forbidden fields to a file labelled 2.0. |
| Backend metrics and termination | Supplied result data, not recalculated by the render adapter | Agree horizon/end separation and subsystem reasons from ADR 0007 before displaying operational results or A/B claims. |

README documents 3,000,000 ticks/s for the current inputs. `TimeGrid` actually derives
`ticks_per_second` from the least common multiple of primitive-duration denominators.
Use that run's grid conversion rather than hardcoding the divisor or accumulating
floating durations in the engine. Runtime positions remain metres `[x,y,z]`, Y up.

`ConveyorDriver.transfers` and `Recorder.events` are separate internal collections.
If export expands transfers into extra logical events, the exporter must establish a
single ordering/sequence space and export snapshot `last_seq` in that same space.
Reusing the recorder's old cursor after inserting events would not describe the
exported prefix. The precise merge/renumbering rule is still an agreement to make.

The client already renders actor intervals and directed metre-cell transfers. It can
bind `order_assigned`, induction, packing, shipping and receipt events when the needed
IDs and placements are supplied. Unknown cargo locations remain hidden with warnings.
Physical service/carry placements need explicit `pos`/`position` or an agreed cargo
attachment (`world`, `actor`, `vehicle`, `cargo`, owner ID and offset/anchor). Existing
optional attachment enrichment in the generic 2.0 payload is a client capability, not
an agreed typed 2.1 contract. Confirm its schema and physical anchor meaning together.

**Snapshot, chunk and seek boundary**

ADR 0010 and the reviewed implementation define the following backend behavior:

- Snapshot boundaries are 30-second multiples through the run's end. Each snapshot
  contains state after every phase of every tick `<= T`, with the last included event
  cursor (`-1` if empty). Capture runs on the settled-tick hook and does not schedule
  work or extend drain. A final non-boundary snapshot is not forced.
- Stored state is canonical JSON bytes with a SHA-256 hash; decoding returns a fresh
  copy. State covers actors/actions, conveyor occupancy/admissions/cursors, ledger,
  orders, tote pools, station links/WIP, shipping/pallets, receiving and pending timers.
- Chunks cover `[k*60,(k+1)*60)`. An event at exactly 60 seconds belongs to chunk 1.
  Empty windows and the chunk containing an exact terminal boundary are retained.
- Seek selects the latest snapshot `S.at_tick <= target`, then applies only events
  with `seq > S.last_seq` and `at_tick <= target`. A snapshot at 60 already includes
  events at 60, even though those events belong to chunk 1; loading that chunk must
  not apply them twice. The same rule must survive transfer expansion.
- These are replay snapshots. There is no `Engine.restore`; pending timer descriptors
  do not serialize Python closures into resumable engine work. Deterministic rerun
  from inputs is a different capability.

The current frontend compiles inline events/actions into indexed visual timelines.
It warns that business snapshots are opaque, and does not yet restore ledger,
reservations, queues, merge cursors or resource timers from them. A typed snapshot
adapter and bounded chunk loader are remaining frontend integration work after the
wire format is agreed; they must use backend state rather than simulate it again.

**Remaining handoff**

1. Arman and Tilek agree ADR 0007's field/version changes, transport event expansion,
   the exported sequence/cursor rule, snapshot state sections and physical cargo
   placements. Keep 2.0 as a valid logical projection if it is delivered first.
2. Arman supplies one actual engine-produced inline Run with immutable inputs/hashes,
   all actors/cargo, actions, ordered events, initial state, snapshots, supplied
   metrics and termination. The analytical fixture provides the first comparison;
   an inline import is allowed before network delivery.
3. Validate the file against the agreed schema plus causal/reference checks, then
   compare backend and client at action ends, simultaneous phases, 30/60-second
   boundaries, blocked transfers, pallet seal/dispatch and forward/backward seeks.
   Check exported cursors/hashes without duplicate stock or cargo transitions.
4. Agree manifest/chunk delivery: versions/input identity, time windows, first/last
   sequence, byte counts and SHA-256, plus equivalent inline assembly. The technical
   specification targets `GET /api/runs/{id}/manifest` and `/chunks?from_s=…`; those
   are specified integration surfaces, not endpoints verified by this review.
   P0 permits local files. Materialize/compare API ownership remains with Arman.
5. Connect supplied snapshots/results and streaming to the client, measure actual
   payload/cache sizes, and only then enable operational results or compatible A/B.
   The spec's 30 MB/hour payload and 64 MB event-cache figures remain targets until
   measured on exported runs.

**Evidence for review**

All backend paths below were read with `git show
5a0be9d09a8c7ae8b882f011aa342e5250327bb1:<path>`; they need not exist in this checkout.

| Evidence path | Material fact |
|---|---|
| `backend/README.md` | Owner, reported implementation gates, current 3,000,000 ticks/s, exporter next |
| `backend/app/cli.py` | Registered CLI commands |
| `backend/app/simulation/clock.py` | Derived grid and seconds conversion |
| `backend/app/simulation/recorder.py` | Event/action/waypoint fields and interval/order checks |
| `backend/app/simulation/scheduler.py` | Phase values and settled hook |
| `backend/app/simulation/conveyor_driver.py` | Separate atomic transfer records, admission/movement boundary |
| `backend/app/simulation/checkpoint.py` | Immutable snapshot bytes/hash/cursor and listener-only capture |
| `backend/app/simulation/chunks.py` | Half-open contiguous chunk split and stream checks |
| `backend/docs/adr/0007-contract-v2-1.md` | Proposed exported 2.1 changes and agreement requirement |
| `backend/docs/adr/0010-replay-snapshots-and-chunks.md` | Accepted internal snapshot/chunk semantics and no engine restore |

Current checkout evidence: `contracts/run.schema.json`, `contracts/README.md`,
`frontend/src/replay/adapter.ts` (`adaptRunV2`), `frontend/src/replay/core.ts`,
`01_Technical_Specification.md` §11, `03_3D_Scene_and_Replay.md` §8 and
`05_Acceptance_and_Demo.md` §10. Graph Tier 2 lookup found the adapter and its
`largeWarehouse.loadRun` caller. Coverage at generation `2026-11-06T22:22:36Z`
reported remote backend paths missing and local evidence metadata changed; exact
source/Git-object reads were used. No backend tests, API requests, installation,
worktree operation or merge was performed for this handoff.
