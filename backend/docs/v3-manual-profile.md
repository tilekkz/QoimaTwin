# V3 manual profile compiler

`app.v3.profile.load_manual_profile(bundle_path: Path, proposal_path: Path)` loads
the pinned source package and strict explicit synthetic proposal. The pure seam is
`compile_manual_profile(bundle: V3Bundle, proposal: ManualProposal)`.
Both return frozen `CompiledManualInputs` containing:

- `profile`: sibling ADR0031 `ExecutionProfile`.
- `graph`: sibling `BoundGraph` with augmented directed walk graph.
- `graph_document`: `ImmutableDocument`; `.decode()` returns a fresh JSON tree
  for replay/export. Its repository canonical SHA256 equals `graph.sha256`.
- `horizon_tick`, `end_tick`, `input_hash`.

Call `ManualEngine(inputs.profile, inputs.graph, check_invariants=True)` and then
`.run(inputs.horizon_tick, inputs.end_tick)`. All jobs are already materialized;
the engine receives no RNG, planning weights, rates or clockless demand inputs.
Do not pass a regenerated or differently normalized graph to the exporter.

The versioned proposal and full reviewable compiled profile live under
`backend/data/v3-execution-proposals/`. The `.materialized.json` file is an
artifact, not a trusted shortcut around source loading/validation. Regenerate it
with `materialize_manifest.materialized_bytes(load_manual_profile(...))` and compare
bytes. It contains all 532 HUs (530 baseline plus two outside receipts), 776 slot
projections, 24 actors, finite ports, bindings and four exact timed jobs. Rebuild
the graph from pinned source plus explicit proposal connectors; its bound digest
prevents graph substitution. Source files and source flags are unchanged.

See [ADR0032](adr/0032-v3-manual-execution-profile.md) for all synthetic choices,
source anchors, clearance checks and unsupported processes. Public loaders reject
changed source hashes, duplicate JSON keys, extra fields, invalid clocks/signs,
nonfinite values, boolean counts, duplicate identities, unknown references,
unsupported jobs, occupied receipt targets, insufficient fit/payload, unsafe
connectors and unavailable directed clearance-compatible routes.

The runnable demo's unit oracle is 12,256 initial + 48 receipts = 12,304 total.
After all four jobs, stock12,256 + shipped48 + outside0 + WIP0 = 12,304, separately
for every SKU. All actors return home and all leases release. This is a small
synthetic execution demonstration, not an operational shift or full V3 workflow.
Linux-target mypy on Windows is static portability evidence, not Linux execution.

## Local CLI

Run from `backend` with a new or empty output directory:

```powershell
uv run python -m app.cli v3 materialize-manual --profile data/v3-execution-proposals/manual-whole-hu-demo-v1.json --out D:/QoimaTwin-runs/v3-inputs
uv run python -m app.cli v3 simulate-manual --profile data/v3-execution-proposals/manual-whole-hu-demo-v1.json --out D:/QoimaTwin-runs/v3-manual
```

`materialize-manual` writes frozen `materialized.json`, the exact augmented
`graph.json` and a raw-byte hash manifest. It does not execute jobs.
`simulate-manual` first persists those files in `inputs/`, executes the invariant-
checked engine, writes the validated transport in `run/` and writes `metrics.json`.
The result identifies `source_label=actual_engine_run` and
`full_v3_warehouse=false`. Partial or failed runs return a nonzero exit code;
existing output is never overwritten. The horizon and end cap come from the
explicit proposal and have no CLI override.

Metrics report independent settled `at_horizon` and `at_end` business counts,
mean/linear-p95 handoff cycles, worker and eligible-role utilization, and
time-weighted queues. Worker home return remains paid after business handoff.
See [ADR0034](adr/0034-v3-manual-observation-metrics.md) for boundary arithmetic.

The separate [fresh-process benchmark protocol](research/11_v3_manual_benchmark_protocol.md)
compares repeated event, input and export hashes. This four-job example can only
measure the bounded manual smoke profile; it supplies no full-shift normal/peak
performance claim.

Receipt-then-ship chains (ADR 0038): a later outbound job may ship a received HU from its
receipt slot, using the same new HU ID. Arrival must not precede the receipt. The compiler
also runs the engine admission check and requires plain decimal numeric text.
