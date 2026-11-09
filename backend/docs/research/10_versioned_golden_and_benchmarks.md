# Versioned fixture oracle and final benchmark procedure

The fixed artifact `tests/golden/qoima-engine-0.4.0.json` distinguishes two kinds of evidence.
Its input fingerprint is independently constructed from the four published source JSON files by
`tests/golden_identity_oracle.py`, using only the Python standard library. No engine output,
Pydantic model, production identity helper, or production canonicalization helper supplies that
expected fingerprint. The resulting run ID is SHA-256 of its canonical preimage.

The oracle implements ADR 0008 semantic ordering and ADR 0009 A27 fixture adaptation. It supplies
the three nullable actor fields that the actor contract defaults to null. Edge lengths and
connection coordinates have the contract's floating-point representation before the documented
content-hash ordering of those collections. Integer-valued floats then normalize to integers.
The fixture time base is independently 3,000,000 ticks/s: the 1,000,000 base resolution and thirds
from walking at 1.2 m/s require that least common multiple. Horizon 3,600 s is the fixture adapter
convention. A separate test hashes a hand-written provenance byte string; absent semantic plan
and forecast inputs hash the literal JSON `null`.

The artifact's event hash is a **recorded regression signature**, explicitly labeled as such. It
detects drift across processes, hash seeds, Python optimization, and operating systems. It does
not establish the correctness of any numerical simulation result. Those expectations remain the
manual analytical fixture and the numbered acceptance tests, including the 32.8 s handoff,
469 s dispatch, and 474 s return. The existing fixture probe checks the manual 474 s endpoint,
complete status, inventory conservation, and contract validation with invariants enabled.

`tests.golden_probe` checks the fixed input preimage, engine version, contract source digests,
run ID, and event signature using explicit exceptions so all checks remain active under `-O`.
The fresh-process test runs with hash seeds 1 and 271828; the second process is optimized. Existing
CI executes these pytest tests on both Windows and Ubuntu. Local Linux type checking is useful
but is not evidence of a Linux runtime pass; that evidence must come from the CI matrix.

Contract text digests normalize CRLF to LF to survive Git checkout line-ending differences.
The recorded application tree digest identifies the original reviewed event-signature source;
it is provenance, not an assertion that future unrelated source files cannot change. Updating a
golden requires reviewing the changed semantics and independent acceptance evidence. Never
regenerate an expected numerical result from the engine merely to make a failure green.

## Final benchmark execution

Run only after the integrated source and dependency lock are frozen and correctness checks pass.
Use new directories outside the repository; the benchmark deliberately rejects existing output.
Do not overlap these measurements with a full test suite or another load benchmark. Each worker
has its own process and hash seed, and each profile runs twice:

```text
uv run python tools/benchmark_runs.py --format proposal --horizon-s 3600 --profiles large-normal large-peak --iterations 2 --out D:/QoimaTwin-runs/final04-hourly
uv run python tools/benchmark_runs.py --format proposal --horizon-s 28800 --profiles large-normal large-peak --iterations 2 --out D:/QoimaTwin-runs/final04-eight-hour
```

Replace both illustrative output paths with actual paths outside the repository. The existing
tool already supports these arguments and the final proposal writer seam. Normal and peak offered
order counts follow the specification: 240 and 600 in one hour, or 1,920 and 4,800 in eight hours.
Those counts concern offered/arrived orders; they do not assert completion or conceal a partial
receiving subsystem. Inspect run status, termination reasons, subsystem counts, and both metric
windows in addition to the top-level benchmark verdict. Check every repeated event/journal hash,
run ID, scenario, metrics, and source fingerprint for equality.

Report measured wall and CPU time separately for construction, engine, and the entire export
(projection, metrics, schema validation, and file IO). Report fresh-process peak resident memory,
including imports and serialization. Windows uses GetProcessMemoryInfo; Linux uses ru_maxrss
with its platform unit conversion. Keep the integrated Windows/Linux guarded implementation.

The raw transport measure is `sizes.chunk_bundle_bytes`: manifest + catalog + referenced event
and snapshot chunks. Optional inline and persisted inputs are reported separately. With the
default proposal writer, `inline_bytes` must be zero. Compare the actual one-hour peak transport
against the conservative decimal limit of 30,000,000 bytes. The current benchmark records the
exact size but does not put this target into its Boolean `checks`; a final acceptance report must
state the observed size and verdict explicitly. The eight-hour total has no 30 MB total limit,
and dividing that total by eight does not prove a bound on every hourly interval. The client's
64 MB cache bound also requires its own reader/cache checks; backend peak RSS is a different
measurement.

No new load result is claimed by this document. The earlier 0.3.0 one-hour trial and the isolated
structural-validator timing are historical measurements, not end-to-end results for the final
integrated 0.4.0 source.
