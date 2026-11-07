# ADR 0025: Explicit Tilek visual compatibility projection

Status: backend adapter implemented; no frontend contract approval implied.
Date: 2026-11-07.

The accepted `contracts/run.schema.json` 2.0 loads in Tilek's replay adapter at
`origin/codex/twin-environment@10496fd4ccd748676c036c371dd1a29881f046d1`, but its
pallet locations are absent and its forklift operation vocabulary differs from
the domain journal. Proposal 2.1 placement events are not consumed by that adapter.

We add `app.exporter.tilek.export_tilek_run(engine, outcome, *, validate=True)` as an
explicit separate visual projection. `export_run` remains authoritative and unchanged.
The result is accepted shared 2.0 JSON. Its identity is
`sha256_hex({**fingerprint(inputs), "wire_version": "tilek-visual-v1"})`.
No extra root properties are added. A real initial actor-state boundary carries a
defined `payload.visual_projection` provenance object with `wire_version`,
`source_run_id`, and `visual_projection_limitations`. Every original event retains
its kind, time, phase, entity ID and payload fields, plus `source_seq`. The projection
resequences the combined stream; source sequence IDs remain explicitly bound.

Frozen `locations`, `placements`, `wire_positions.apply_position`, and
`wire_events._attachments` supply geometry, finite queue slots and physical handoffs.
The private attachment seam is intentionally reused; there is no second stock,
queue, order, or forklift engine. `wire_events` requires its frozen `wire_derived`
import dependency even though the adapter never invokes derived stock logic.

Real pallet milestone payloads receive `pos`, `stage`, `cargo_id`, and `attachment`
for Tilek's existing generic hook. A scan-start placement and completed forklift
handoffs that lack raw-journal events become meaningful `actor_state_changed`
events with actor state/action ID, physical-event type and visual binding. Pickup
attaches at completion. Loading and putaway detach at completion, before same-tick
dispatch/hide. Parcel-to-pallet ownership stays in the original scan handler through
dispatch. Source conveyor cell pairs and real container IDs remain intact.

Forklift pickup becomes visual `loading`; loading/putaway become `unloading`;
travel becomes `drive`. Empty approach/return actions have null entity IDs; loaded
travel and services keep real pallet IDs. IDs, action times and geometry survive.
Source metrics, cargo contents, inventory and initial state are preserved. Snapshot
business state and operations retain source semantics; `source_checkpoint` preserves
the original checkpoint while the projected checkpoint references the new sequence
and hashes the retained state plus explicit provenance.

`validate_tilek_run` checks the accepted JSON Schema and reuses the source semantic
validator after excluding and resequencing derived actor transitions. The extracted pure validate_run_semantics helper preserves every source check;
default validate_run still runs schema plus semantics. The visual schema runs once,
then retained source events receive the same semantic checks. Export validates only
the final projection; publication callers export with validate=False and validate
once in the writer. `write_tilek_run`
reuses the existing bundle publisher and metadata/output/interval guards. It cannot
be a direct `write_run` alias because `write_run` invokes that source-only validator.
Manifest provenance repeats the inline binding. Root owns CLI `--format tilek-v2`;
APIs and scenes are unaffected by this change.

Consequences: proposed queue coordinates are marked `proposed_queue_grid`, not
presented as scene-approved facts. Unknown PKxx/SHIPPING cell warnings remain. The
frontend still needs heading support, dynamic carry height/fitting, configurable belt
timing, terminal/cutoff handling, manifest/API loading and semantic snapshot replay.
No epsilon, extended interval or fabricated completion compensates for those gaps.
WAIT_RESOURCE intervals are not added by this adapter. Existing source intervals remain.
No claim is made that visual replay proves conservation; source engine invariants and
semantic data remain the basis for that check.

Validation: RED tests first reproduced absent pallet positions and incorrect forklift
operation/carry fields in the default exporter. Focused Python checks and actual Tilek
TypeScript probes cover generated analytical, receiving, multi-order and cutoff runs.
See `backend/docs/tilek-compatibility.md` and the external adapter report for commands/artifacts.
