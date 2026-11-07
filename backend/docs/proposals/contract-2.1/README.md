# Backend contract 2.1 proposal

This directory is a review artifact, not an agreed shared contract. Tilek's current adapter at
10496fd4ccd748676c036c371dd1a29881f046d1 accepts inline 2.0 and correctly rejects this proposal.
No file under shared contracts/ or frontend/ is changed here. Pending decisions are in ADR0017.

`run.schema.json` is the full executable JSON Schema. `analytical-h10.proposal.json` is a generated,
schema-validated analytical fixture with horizon10 and drain through474 seconds. Its handoff is
at32.8, dispatch at469 and final actor return at474. It deliberately demonstrates zero dispatched
orders at the horizon and one at the end. Engine version is qoima-engine-0.4.0; the run identity
includes all nine semantic input hashes, scenario provenance and the explicit proposed wire version.

The Python entry points are `app.exporter.proposal.export_proposal` and `write_proposal_run`.
For publication call export_proposal(..., validate=False), followed by write_proposal_run(...),
which validates once. Inline run.json is disabled by default; include_inline=True opts into a
duplicate full document. Catalog/event_chunks/snapshot_chunks form the default transport.

A reader reconstructs the nearest full checkpoint and its checked balance-delta chain, then
replays later events. `app.exporter.wire_replay.replay_snapshot` is a reference reducer validated
against independent live checkpoints. Same-tick cell_moved events are atomic, and a snapshot atT
includes all events throughT. Boundary action descriptors preserve newly started work exactly at
the cutoff without claiming future execution. Relocation metadata has a separate pre_shift
calendar and actor; it never changes the shift roster or shift utilization denominators.

The actual one-hour peak transport measured25,232,469 raw bytes before the final schema-optimizer
and metadata refinements. Optional inline measured30,564,459 bytes and is not part of the default
transport. This is a measured reference, not a promise about later versions or eight-hour runs.
The global integration gate and final performance measurements remain required before release.
