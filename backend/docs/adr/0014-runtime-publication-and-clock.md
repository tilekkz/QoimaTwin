# 0014. Runtime ordering, short horizons and safe publication

Status: accepted for backend hardening, 2026-11-07. Shared v2 schemas are unchanged.

## Clock

The live scheduler slots use a min-heap and lazy deletion. A bucket keeps its live-item count;
cancellation is idempotent. Peeking no longer scans all future buckets. The SimPy queue still
owns time and phases, and cancelled-only events neither settle a tick nor extend drain.
A cancelled unique item can be replaced in the same bucket. Order within a bucket is
`(rank, key, seq)`: regular completions and completed scans have rank 0, pallet age expiry
has rank 1. Scan-versus-expiry ordering therefore does not depend on actor spelling.
Snapshot timer descriptors include that rank. This remains replay, not Engine.restore.

## Horizon

An input horizon is positive integer seconds, bounded by 168 hours. For any horizon H the
arrival sequence is the unchanged rational schedule `(i+0.5)*3600/rate`, restricted to
arrival < H. The RNG consumes draws only for retained arrivals. Whole-hour inputs preserve
their exact order stream, including rates that have non-dyadic arrival fractions.
H < 3600 is explicitly marked `shortened_run=true` in provenance, CLI and materialized manifest.
No offered-load rescaling occurs. Receipts retain their existing 90+180*i schedule.

## CLI errors and output

AppError codes are stable for CLI and future HTTP use. Invalid input has HTTP 422 semantics;
an existing nonempty output directory is a conflict. Unexpected execution exceptions become
JSON `execution_error`, rather than a traceback. KeyboardInterrupt and help are not swallowed.
Only passed/complete commands return exit code 0; partial and failed return 1.
Every response names contracts_dir, layout_version (null if loading failed) and engine_version.

Commands refuse a nonempty output directory before doing work. The simulate command owns the
new `inputs/` directory and explicitly allows that single child when publishing its run; any
other existing child is rejected. Files are flushed and replaced atomically, manifest last.
A failed publication may leave an incomplete directory for diagnosis; retry must use a fresh
directory. No existing artifacts are silently overwritten or recursively removed.
`--assignment` loads JSON Schema, the strict model, layout and slot references before inputs
are published. Assignment/config backend JSON Schemas derive from their typed models while
the future shared schemas are under agreement; no files in contracts/ are modified here.

## Export validation and intervals

`export_run` validates by default. A controlled projection-to-publication pipeline can pass
`validate=False`, then `write_run` performs the single mandatory validation before writing.
Arbitrary external dictionaries always pass through write_run validation; no mutable object
is assumed safe because it was validated earlier. Compiled validators are cached by schema
text, so replacing a schema invalidates the cache without relying on timestamps.

The writer uses the shared split_events function on exact integer ticks. chunk_duration_s and
snapshot_interval_s are explicit writer options and manifest fields; the CLI passes config
values. Positive fractional seconds are accepted when exactly representable on the time grid.
Chunk ownership stays half-open; a terminal boundary event belongs to the next chunk.
