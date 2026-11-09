# Explicit V3 manual profile benchmark protocol

This driver measures only the pinned bundle and explicit proposal supplied on its CLI.
It never generates arrivals, changes H/end, scales rates, or invents normal/peak cases.
Run it after background work and repository gates have stopped. Timing observations from
concurrent tests are not meaningful performance evidence. This delivery ran tiny protocol
tests only; the parent owns the final actual-source benchmark in a quiet environment.

From `backend/`, using the repository Python 3.12 environment:

```powershell
python tools/benchmark_v3_manual.py --bundle D:/public/v3-pinned-bundle --proposal D:/public/manual-whole-hu-demo-v1.json --out D:/public/v3-manual-benchmark-001 --iterations 2
```

The bundle path is the explicit root accepted by `load_v3_bundle`; use the pinned source
bundle, not an export directory. Both input paths are required. Iterations must be >=2.
Output must be outside this repository and new or empty. Existing artifacts are never
overwritten. Each repeat launches a fresh Python subprocess with a distinct hash seed,
performs compilation, creates one invariant-checking `ManualEngine`, and calls `run` once.
The resulting outcome is exported without executing the engine again:

```python
build_manual_run(
    inputs.profile,
    inputs.graph,
    outcome,
    graph_document=inputs.graph_document.decode(),
    end_tick_limit=inputs.end_tick,
)
write_manual_run(run, out_dir)
```

The writer is `app.v3.run_transport.write_manual_run(run, out_dir, *,
chunk_ticks=60_000_000, max_chunk_bytes=8*1024*1024)`. Its own exclusive publication
preserves immutable export artifacts and writes the export manifest last.

Every repeat prints its actual profile counts, arrival ticks, horizon and end cap. The
supplied source example has **four whole-HU jobs**: two inbound arrivals at 0/60 seconds
and two outbound jobs, 530 initial HUs plus two synthetic incoming HUs, 200 SKU, 24 actors,
two selected ports with one explicit buffer each, H=600 seconds and end=900 seconds.
Only SMALL_CARTON/STANDARD_CARTON jobs execute. Other initial archetypes remain inert
authoritative stock. This is a smoke profile; it supplies no one-hour/eight-hour,
normal/peak, full operational V3, or all-eight-archetype performance evidence.

## Measurements and boundaries

Each timing contains current-child CPU seconds and wall seconds. CPU is `process_time`,
never aggregate parent/other-process CPU. Phases are sequential:

| Field | Included work |
| --- | --- |
| compile | Pinned bundle load/checks and explicit profile compilation |
| engine_construction | Profile validation, state creation and initial invariant check |
| engine_run | One DES execution with per-tick conservation checks |
| export_build_including_validation | Build graph/profile/event/snapshot representation and builder's mandatory schema/semantic validation |
| schema_semantic_validation_extra_pass | Separate full schema/semantic replay validation of the completed representation |
| write_including_validation | Writer's mandatory validation, serialization, chunking, raw writes and export manifest publication |
| optional_metrics | `app.v3.manual_metrics.summary(profile, outcome)` if installed |

Export build/write include their own mandatory validations: the public seam has no
validation-disable flag. The additional validation pass is explicit and included in
whole-child cost. Do not subtract this pass to estimate the other validations or call
these fields pure serialization/I/O. Validation also checks semantic replay, not only
JSON shape. No exporter function is patched to bypass its contract.

`whole_child.cpu_s_since_process_launch` includes imports, all measured phases, metrics,
artifact hashing and source checks through measurement creation. It excludes final
measurement-JSON serialization and interpreter teardown. The child's
`wall_s_since_measure_entry` starts at measurement entry, while the parent's
`whole_child_wall_s_including_startup_shutdown` brackets the entire subprocess.
These labels deliberately distinguish whole-child CPU from engine-only CPU.

`peak_rss_bytes_whole_process_including_compile_export` is the process maximum through
measurement completion, including imports, compilation, engine, validation and export.
It is not incremental or engine-only RSS. Windows uses typed `GetProcessMemoryInfo` and
`PeakWorkingSetSize`; Linux uses `RUSAGE_SELF.ru_maxrss * 1024`; macOS uses bytes directly.
No child-of-child aggregate or parent RSS is substituted.

`raw_export_bytes` sums verified manifest, metadata, graph and all event/snapshot chunks.
It is raw filesystem bytes, with no compression and no benchmark-report/input bytes.
Each referenced file is checked against its manifest byte length and SHA256. The parent
checks the inventory again after child exit. Missing, corrupt or escaping artifacts fail.

## Determinism and publication

Events SHA256 hashes canonical JSON bytes of every actual `ManualOutcome.events` record,
including exact rational route lengths, ticks, owners, leases and worker/job payloads.
The exported event array must equal those records exactly. No rounded screen positions,
display summaries, sampled events or metrics substitute for actual events.

Repeat checks bind run ID, actual events SHA, compiled input hash, canonical full profile,
raw proposal SHA, graph SHA, H, end cap, manual engine version, pinned source revision,
git revision, source tree fingerprint, operational status and raw export inventory SHA.
Missing identity fields and fewer than two repeats cannot pass. Each worker must match
the parent's source/revision, remain unchanged across the run, and have a distinct PID.
Only `complete`/`partial` are accepted operational states; deterministic partial runs
are reported as partial, and passing the protocol does not imply all jobs completed.
Optional business metrics are report data and do not define determinism. Absence of
the optional metrics module is accepted; broken imports or metric exceptions fail.

Fingerprinting reads only `backend/app/**/*.py` and `backend/tools/benchmark_v3*.py`,
using public relative paths. It does not traverse home/auth directories, collect git
status, environment values, `.env`, credentials or arbitrary files. Linked source files
escaping the allowlist fail. Git revision is read without editing any repository.

Output contains `repeat-NNN/measurement.json` and `repeat-NNN/export/`. A nonzero child,
missing report/artifact, failed validation or determinism mismatch returns nonzero and
prints the failure to stderr; successful prior repeats remain available for inspection.
Only after every check passes does the parent exclusively create `benchmark.json`,
then `manifest.json` bound to its canonical SHA, then `latest.json` pointing at that
manifest. `latest.json` is local to this fresh output directory; there is no shared
mutable global latest pointer. Partial failed outputs must be preserved and a new
directory used for retry. Manifest existence inside a repeat alone does not mean the
overall benchmark passed.

## Remaining full-scale V3 work

The parent must first integrate compiler/runtime/exporter and run the actual-source
profile in a quiet environment. That run would still be smoke evidence only. Full
performance work needs explicitly supplied and reviewed one-hour/eight-hour normal/peak
profiles, source-bound arrival/materialization policies, representative initial stock,
all intended ports/buffers/actors and operational process coverage. No such profiles
are generated here. All-eight-archetype execution additionally needs supported loaded
vehicles, conveyors, transfer/packing and unit-picking behavior, traffic/edge contention,
physical admission and role calendars. Horizon/rate changes require new explicit input
profiles and new identities. Actual Linux runtime checks remain a CI/parent task;
Linux-target mypy on Windows is static compatibility evidence only.
