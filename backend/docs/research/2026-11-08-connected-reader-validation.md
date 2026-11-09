# Connected reader: one structural pass per captured state

The reader previously validated metadata and every event/checkpoint part, then
validated the assembled run with the same nested schema again. A direct schema
visitor test reproduced two structural visits to each decoded captured-state
object. Metadata H/end captures are separate wire objects and each still needs
its own validation.

The reader now validates strict metadata, catalog and chunk schemas once, then
executes the unchanged common semantic checks over their assembled result.
The public full-run validator and writer still perform complete schema validation
before those semantics. There is no public switch to skip schema validation.
Unknown part names reject explicitly instead of silently selecting the run schema.

All raw SHA256, length, contained-path, descriptor-range, source/input binding,
stock, sequence, watermark, H/end, metric-count and terminal-state checks remain.
The wire schema, export bytes, identities, versions, captured-only clock and
unsupported capability flags are unchanged. This does not add streaming memory
bounds, arbitrary seek or a frontend adapter.

Observed checks on 2026-11-08:

- Three new tests first failed: standalone strict catalog selection, unknown part
  rejection and the one-visit structural budget (`3 failed in 21.59s`).
- Twelve required-field/extra-field/wrong-type controls over metadata, catalog,
  events and checkpoints passed before the change (`12 passed in 34.15s`).
- New cases and existing publication/API corruption regressions passed afterward:
  `41 passed in 104.33s (0:01:44)`.
- Strict Windows and Linux-target mypy each reported no issues in five source
  files; Ruff passed and all five Python files were already formatted.
- Four independent nested scalar/source-binding probes passed in 21.71s.
- One full read of the existing source CLI artifact passed 14 explicit checks.
  All 17 files, totaling 46,127,485 bytes, remained unchanged. The preserved
  invalid-complete artifact was rejected by the shared terminal-state guard.

No DES or new source publication was needed for these reader checks. Concurrent
development and a repository gate were active; this evidence establishes a
reduced structural traversal count and compatibility, not a wall-time benchmark
or a full-warehouse performance claim.
