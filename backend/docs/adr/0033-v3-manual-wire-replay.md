# ADR 0033: Source-bound manual V3 run, finite leases and observed replay

Status: backend proposal implemented; no shared frontend contract agreement.

## Context

ADR 0031 supplies a real, limited whole-HU manual engine. ADR 0032 supplies
explicit synthetic operator/calendar/connector choices over the pinned adaptive
V3 source. Static V3 catalog consistency (ADR 0027) alone cannot assert execution.
The legacy Run 2.0 reader has no operational V3 contract or augmented graph.

## Decision

Publish `qoima.manual-run.v3-proposal` and `qoima.manual-manifest.v3-proposal`,
wire version `0.1.0`. `source_label=actual_engine_run` describes actual execution
of the named manual engine; `data_kind=manual_execution_proposal` and capability
flags deny a complete V3 warehouse and an existing frontend adapter. The frozen
profile retains its explicit synthetic assumptions and source fingerprints.

The run ID hashes the complete exact profile, horizon, requested drain cap,
clock, manual-engine version and wire version. The profile binds the canonical
SHA-256 of the complete augmented graph document. Preserve that document,
including node world positions, directed arcs, permissions and connector
provenance; validate it against the actual runtime graph. No V2 coordinates,
implicit reverse arcs or positions reconstructed from identifiers are allowed.
Exact fractions serialize as reduced numerator/denominator pairs. Timestamps
are integer microseconds; operation durations use the ADR 0026 ceiling policy.
Representation choices such as chunk/snapshot interval do not change run identity.

Events retain contiguous runtime sequence and actual integer tick. Typed
`job_changed`, `worker_changed`, `hu_owner_changed` and lease events carry every
state change required for replay. Validate the profile with the same canonical
gate as the engine. Validate observed assignments against actual worker skill,
mass and eligible port membership. Validate each finite resource against its
job, exclusive acquisition/release and required ownership; a matching ghost
acquire/release pair cannot create capacity. Service operations must finish in
the source window intersected with the horizon. Operation duration and stage
order must match the declared profile and directed route, including paid return.

The derived operation index separates actual start, planned end, observed end
and completion. An unfinished movement can have a planned end after the cap;
there is no corresponding future completion event. Checkpoint wrappers retain
active operation IDs. Snapshot state itself contains only mutable jobs, workers,
HU owners, leases and balances, with no timers or event history. The profile
bootstrap is before tick-zero events; checkpoint zero is after all tick-zero
events. Every checkpoint at T includes all observed events with tick <= T.

Default checkpoints are every 30 seconds, plus zero, horizon and actual end.
Default event/snapshot chunk windows are half-open 60-second windows. Events
exactly on a boundary belong to the following window. Split crowded windows
into ordered parts before raw JSON exceeds 8 MiB; a single oversized item fails
explicitly. Full checkpoints support one-checkpoint seeks without a delta chain.
The manifest binds raw byte counts and SHA-256, separate graph and metadata
artifacts, and is published last with exclusive atomic file publication.
Readers validate schema, descriptor time bounds, byte sizes, hashes and local
paths. A seek loads one checkpoint part and only intersecting event parts.

Replay reconstructs observations without restoring or advancing an engine.
Actor interpolation uses actual source node poses and elapsed fraction of the
declared route. Carrying uses actual HU ownership. A storage service node is an
approach anchor, not a cargo floor pose: stock returns a typed storage-slot
reference; a carried HU returns its actual worker attachment reference.

Metrics follow ADR 0034: settled counts include boundary T; utilization and
queue integrals use [0,T). Inbound putaway/outbound handover complete business
work before a worker's paid home return. Validate exported metrics by recomputing
them from the same frozen profile and observed trace, separately at H and end.

## Evidence and limits

Independent hand arithmetic covers inbound stock 23s/return 33s, outbound
handover 31s/return 33s, repeated backward seeks and cap 18s inside movement ending
at 22s. Independent reviewers reproduced and then closed rehashed invalid loads,
removed skills, wrong windows, ghost/wrong resources, missing worker/buffer/port
leases and wrong HU carriers. The actual four-job source example preserves 530
baseline HU, adds two explicitly declared 24-unit receipts and ships two 24-unit
HU: 12,256 stock units plus 48 shipped units, no unexplained stock creation.

This is not the full N0-N4 workflow, a heavy-load/forklift model, packing,
conveyor execution, role scheduling or a claim that Tilek's reader accepts it.
The shared `contracts/` and frontend remain untouched. Published backend-owned
schemas and the actual source demonstration are under `proposals/adaptive-v3/`.
