# Tilek visual compatibility export

Use this explicit backend projection when supplying inline Run 2.0 JSON to Tilek's
existing replay adapter. The default shared v2 export remains the authoritative
simulation artifact. This format is identified as `tilek-visual-v1`; it does not
declare proposal 2.1 accepted.

```python
from app.exporter.tilek import export_tilek_run, write_tilek_run

visual = export_tilek_run(engine, outcome, validate=False)  # writer validates once
manifest = write_tilek_run(visual, output_directory)
# Load output_directory / "run.json" in the existing Tilek viewer.
```

Public signatures:

```python
export_tilek_run(engine, outcome, *, validate=True) -> dict
write_tilek_run(run, out_dir, *, metadata=None, chunk_duration_s=60,
               snapshot_interval_s=30, allow_existing_inputs=False) -> dict
```

CLI `simulate --format tilek-v2` selects both functions and writes an inline `run.json`.
Calling the source `write_run` on a visual run is unsupported: its extra semantic
checks do not yet recognize schema-permitted `actor_state_changed`. The visual writer
uses the existing bundle publisher and preserves its output guards, canonical bytes,
chunk hashes and action overlap selection. No npm install or server is required.

The projection was also verified against `polished@cb5777f` and `adaptive@22296bc`:
92 assertions passed on their actual TypeScript. See the
[pinned compatibility review](research/2026-11-07-tilek-compatibility.md) for the exact scope.

The run ID hashes the current full fingerprint plus `wire_version="tilek-visual-v1"`.
Inline provenance lives at `events[0].payload.visual_projection`, repeated in
`manifest.provenance`, with `source_run_id` and `visual_projection_limitations`.
Every original event has `payload.source_seq`; its original kind/time/phase/entity
and business fields survive. Extra actor transitions record real initial/scan-start
or completed physical handoff boundaries; they do not invent stock/order milestones.
All original action IDs and times survive. Forklift operation and empty-trip entity
fields are explicitly visual. Source metrics and cargo contents remain unchanged.
Snapshots retain source business state/operations and a `source_checkpoint`; the
projected checkpoint binds the new event sequence. They are not visual scene snapshots.

The adapter imports the frozen proposal helpers from `app.exporter`: `wire_locations`,
`wire_placements`, `wire_positions`, `wire_events` and the latter's `wire_derived`
dependency. All dependencies are now present in this worktree and ordinary imports work. This
adapter never calls proposal stock/milestone derivation. No proposal schema is required.

Pallet placement uses the frozen helpers' real containers and finite slots. OPEN_PALLET
and docks have scene-anchor provenance; queue grids are marked `proposed_queue_grid`.
Pickup attaches at service completion. Loading/putaway detach at completion. Scanned
parcels remain children of their real pallet until dispatch; multi-order pallets keep
all original parcel/order IDs. Real PKxx/SHIPPING endpoints remain in conveyor pairs.

Remaining frontend gaps:

- PKxx/SHIPPING warnings require container support; the exporter creates no fake cells.
- Action schema 2.0 forbids `yaw`/`endYaw`. Shelf-facing headings need frontend/contract work.
- Vehicle attachment follows the forklift, but carry height stays at a fixed offset;
  the adapter drops fitting information required for dynamic lift height.
- The viewer uses horizon for duration and half-open intervals show IDLE exactly at
  an incomplete cutoff. Backend intervals stay honestly clipped with no epsilon or
  fake terminal action; source status/termination and provenance remain authoritative.
- The current viewer hardcodes one-second conveyor motion, ignores opaque business
  snapshots and metrics, and does not resolve manifest/chunks/API automatically.
- BLOCKED actor intervals do not necessarily light the conveyor; the scene has a fixed
  tote pool and domain event IDs may not match visual pulse targets.
- The generic placement hook cannot independently hide arbitrary removed cargo or
  rotate placements. Existing dispatch/parent handlers provide the supported hide path.

Focused checks, from `backend/`, with Python 3.12 and installed project dev dependencies:

```powershell
python -m pytest tests/unit/test_tilek.py tests/unit/test_exporter.py tests/unit/test_exporter_totes.py tests/acceptance/test_receiving.py -q
python -m mypy app/exporter/tilek.py app/exporter/tilek_actions.py app/exporter/tilek_events.py app/exporter/tilek_validation.py app/exporter/validation.py tests/unit/test_tilek.py
python -m ruff check app/exporter/tilek.py app/exporter/tilek_actions.py app/exporter/tilek_events.py app/exporter/tilek_validation.py app/exporter/validation.py tests/unit/test_tilek.py
```

External probe artifacts for this implementation are in
`C:/Users/Denry/AppData/Local/Temp/tilek-compat-6t15kh5i/`.
`projection-probe.mjs` executes actual frozen Tilek adapter/core/motion TypeScript using
Node strip-types. Generated inputs are under `generated-tilek-visual-v1-final/`; the candidate
for root to copy to `contracts/fixtures/proposed/` is `analytical-bundle/run.json`.
The implementation report is `D:/QoimaTwin-wt/tz-tilek-adapter-report.md`.

Validation runs accepted JSON Schema once, then shared source semantics on retained
source events. Default validate_run still performs schema plus all existing semantic
checks. CLI must export with validate=False and let the writer validate publication.
Strict mypy is checked with --platform win32 and --platform linux, without follow-imports
suppression or command-line ignore-missing-imports. These are target-platform checks
from Windows, not a native Linux runtime test.
