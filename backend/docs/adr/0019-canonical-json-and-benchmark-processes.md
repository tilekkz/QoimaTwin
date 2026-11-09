# ADR 0019: Canonical JSON checks and isolated benchmark measurements

Status: accepted for backend implementation; the optional 2.1 transport remains a proposal.

## Context

The November 7 backend specification requests cheaper canonicalization without changing bytes,
and reproducible 1-hour/8-hour measurements of time, resident memory and raw export size. The old
canonical validator revisits every scalar in Python. The old benchmark fixes H=3600 and measures
two engines in one process, whose peak memory cannot distinguish the individual runs.

## Decision

Canonicalization remains `qoima-json-v1`. Native JSON encoding uses the same ordering, separators,
Unicode policy, float representation and `allow_nan=False`. It first rejects circular containers,
unsupported values and non-finite numbers. An iterative container-only walk then rejects the
non-string object keys that Python's JSON encoder otherwise converts to strings. No bytes are
returned until both steps succeed. The walk does not allocate a visited set or call a validator
for each primitive. Parsing keeps the duplicate-key hook and rejects constants; a finite-float
hook also rejects exponent overflow such as `1e400`, so no post-parse traversal is required.

`tools/benchmark_runs.py` accepts a positive integer-second horizon up to 168 hours, selected
normal/peak profiles and an iteration count (default two). Every iteration starts a fresh Python
process with a distinct hash seed. The worker persists and reparses `inputs/scenario.json` before
constructing an invariant-checked engine. The v2 publication pipeline calls `export_run` with
`validate=False`, then `write_run` once with configured chunk/snapshot intervals and explicit
ownership of the existing `inputs/` directory. Optional proposal export is imported only on request.

Each worker records wall and process CPU time by stage, process-lifetime peak resident memory,
source fingerprints, event/journal/scenario hashes, run status, termination reasons, subsystem
status and complete horizon/end metrics. Windows uses `GetProcessMemoryInfo.PeakWorkingSetSize`;
Linux uses `getrusage(RUSAGE_SELF).ru_maxrss` converted from KiB to bytes. macOS already reports
bytes. The peak includes imports, materialization, the engine and export; it is not engine-only RSS.

Raw sizes distinguish the optional inline copy, event and snapshot chunks, the referenced bundle
(manifest + catalog + chunks), and all files including inputs. No compressed size substitutes for
the raw payload requirement. Source changes during a run or between iterations fail comparisons.
With one iteration the determinism fields are null and `determinism_checked` is false. A partial
simulation may produce a valid, deterministic benchmark: its partial status and subsystem causes
remain visible. An engine failure, count mismatch, conservation failure or unequal hashes fails
the benchmark. Offered-count oracles come from the specified 240/600 rates and half-open horizon,
not from previous engine output.

## Verification and limits

Hypothesis parity cases compare native protocol bytes, round trips and SHA-256; existing golden
tests remain authoritative. Cyclic lists/dicts, duplicate keys, overflow and unsupported values
have explicit regression cases. An initial visited-set implementation was discarded because its
encoding microbenchmark regressed. The final alternating same-process benchmark preserves all
4,493,302 bytes and their SHA-256 while reducing observed median CPU time for encoding and parsing.
Its fixture and raw samples are worker artifacts, not a performance assertion in tests.

Unit tests exercise fresh-child orchestration, Windows RSS, size accounting and a tiny real export
with exactly one validation. Full 1-hour/8-hour load measurements must run only after integration,
without concurrent full test gates. Unit and microbenchmark observations do not establish shift
runtime, export size, full replay correctness or approval of contract 2.1.
