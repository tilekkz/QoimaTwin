# Manual V3 run proposal

The manual execution exporter consumes the frozen profile, augmented source
graph and actual `ManualOutcome`. Static V3 catalogs and Run 2.0 are separate.
This proposal has no existing Tilek frontend adapter.

```python
from pathlib import Path

from app.v3.execution import ManualEngine
from app.v3.profile import load_manual_profile
from app.v3.run_export import build_manual_run
from app.v3.run_transport import write_manual_run, read_manual_run, seek_manual_run

inputs = load_manual_profile(
    Path("data/v3-proposal"),
    Path("data/v3-execution-proposals/manual-whole-hu-demo-v1.json"),
)
outcome = ManualEngine(inputs.profile, inputs.graph, check_invariants=True).run(
    inputs.horizon_tick,
    inputs.end_tick,
)
run = build_manual_run(
    inputs.profile,
    inputs.graph,
    outcome,
    graph_document=inputs.graph_document.decode(),
    end_tick_limit=inputs.end_tick,
)
manifest = write_manual_run(run, Path("out/manual-v3"))
same_run = read_manual_run(Path("out/manual-v3"))
state_at_80s = seek_manual_run(Path("out/manual-v3"), 80_000_000)
```

`validate_manual_run` performs strict schema, content binding, typed reference,
canonical execution capability, directed motion, finite lease, observed stage,
window, replay and metric checks. `replay_manual(run, cutoff_tick)` reconstructs
a state from an already validated in-memory run. Every boundary is integer tick;
the fixed clock is 1,000,000 ticks/second. Unknown or future cutoff requests fail.

`actor_pose_at(run, actor_id, cutoff_tick)` returns an observed route anchor,
carried HU IDs and a separate planned end tick when moving. It never moves an
actor beyond observed time. `hu_location_at` returns a typed storage slot,
buffer place, port, outside/shipped state or worker attachment. A storage slot
requires the corresponding source geometry to render its cargo; service nodes
are not cargo centres. Model orientation/attachment offsets remain an asset
integration responsibility and are not fabricated by the exporter.

The run preserves the full frozen profile and graph document. Exact physical
quantities use `{numerator,denominator}`; graph source JSON stays unchanged.
Input identity includes the profile's graph SHA, source bindings, assumptions,
timed jobs, horizon, end cap, clock and versioned manual engine. Observed end can
precede H when work completed early; `observed_until_tick=max(H,actual_end)`.
An open movement's planned end can exceed the observation cap without implying
completion. The operations array and checkpoint active IDs retain this distinction.

Publication produces `metadata.json`, `graph.json`, separate event and snapshot
parts, then `manifest.json`. There is no default inline duplicate. Each file has
raw byte length and SHA-256. Chunks use 60-second half-open windows; checkpoints
default to 30 seconds and contain settled mutable state only. Raw chunks are at
most 8 MiB, with smaller explicit limits supported. Same-window parts preserve
sequence. A seek reads one full checkpoint part and intersecting event parts,
not all history or the graph document. Full reads reconstruct and validate the
complete inline representation. Files are immutable; existing destinations and
concurrent replacements are rejected, and a failed output has no success manifest.

The published schemas are `proposals/adaptive-v3/manual-run.schema.json` and
`manual-manifest.schema.json`. `manual-source-demo.example.json` is actual engine
output from the explicitly synthetic four-job profile over pinned V3 source.
It is review material, not an agreed shared contract, full-warehouse benchmark
or operational safety admission. See ADR 0031-0034 for the exact boundaries.
