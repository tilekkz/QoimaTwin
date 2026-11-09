# Backend A-E acceptance and one-hour measurements

Observed on 2026-11-07 local time; engine qoima-engine-0.2.2, Python 3.12.15, Windows 11.
The reproducible machine-readable measurements are in [mass-flow.json](2026-11-07-mass-flow.json).

## Method

Two fresh runs per profile, horizon 3600 s, identical persisted scenario inputs and the supplied
illustrative assignment. This is not a trained ABC placement or an optimization experiment.
Every Engine enables initial and settled-tick invariant checks. Runtime excludes materialization
and construction; export time includes metrics, JSON Schema validation and disk writes.
No other heavy test or benchmark was run concurrently by this session. These are local observations,
not portable performance guarantees. Offered 240/600 orders are spec oracles, not throughput targets.

App source SHA256: `2c16efd72927e27d88728099d6a11f465017a4dcf36fa3a5d73de294cd46d374` (56 files).
Measured before the E commit on parent `a2d98799bc9035ee96e77e83734630393db6412d` with E changes present.
The source fingerprint identifies the measured code independently of that parent commit.

## Measurements

| Profile/run | Engine seconds | Export seconds | Inline bytes | Chunk bundle bytes | All files bytes |
|---|---:|---:|---:|---:|---:|
| large-normal/1 | 10.420 | 31.126 | 20074636 | 20332308 | 40446771 |
| large-normal/2 | 9.942 | 30.680 | 20074636 | 20332308 | 40446771 |
| large-peak/1 | 20.966 | 78.965 | 45500932 | 46123335 | 91720729 |
| large-peak/2 | 24.380 | 78.532 | 45500932 | 46123335 | 91720729 |

Raw UTF-8 bytes, not compressed. Chunk bundle = manifest + catalog + chunks, excluding the optional
inline copy and scenario. All files includes both transport forms and scenario.json, but not the
separate CLI history files. The <=30 MB raw-payload target is not met for peak: both the inline
copy (45,500,932 bytes) and total chunk bundle (46,123,335 bytes) exceed it. Streaming bounds
the loaded time window, not the total raw volume. The largest individual chunk is 359,801 bytes
for normal and 724,951 bytes for peak.

| Profile | Arrivals | Dispatched < H | Backlog at H | Dispatched at end | End seconds | End mean/p95 cycle seconds |
|---|---:|---:|---:|---:|---:|---:|
| large-normal | 240 | 220 | 20 | 240 | 3836.0 | 300.250 / 382.800 |
| large-peak | 600 | 470 | 130 | 600 | 4522.0 | 580.917 / 897.050 |

All four runs drained, with zero final inventory-conservation violations. Role utilization and
time-weighted queues for both windows are in the JSON report; drain never inflates [0,H) labor.

## Determinism and replay

- large-normal: events SHA256 `ee871380f260f8240fdb1c5910199f7013ae414f543d3ccf87fc00d9f8ecd81d`; run ID `ab7210718568bfd9852fcd59331b9f77bbedaece564298ed241a225544ce0c73`.
  40120 events, 3054 actions, 128 snapshots, 64 chunks.
- large-peak: events SHA256 `c5d6546c2559c41b2b6f07873c7ef2caa0da97d259e5a718863d7979fab4cef0`; run ID `b027df5d74b21d435bdafba2b0773b915ff147607b5707d9dfa85be7bc6ccc0a`.
  113244 events, 7485 actions, 151 snapshots, 76 chunks.

Both runs of each profile match event hash, run ID, scenario hash and both metric windows.
Independent post-write verification matched the manifest SHA256 and length for all 288 referenced
files across four runs.
The separate hourly acceptance test also applies physical cell exits then entries atomically per
phase-2 batch and matches every snapshot and final occupancy. Offered counts come from 05 T6;
no expected performance count was learned from engine output.

## Acceptance and regressions

- C5-C8: cursor persistence at kernel level, full-post divert blocking, one-hop release and one tote return.
- K1-K6: six parallel packers, finite waiting, blocked output/tote release, clipped role utilization.
- D1-D8: reservation race, capacity/age seals, drain timer, shipping backpressure and dispatch milestones.
- T1-T6: empty/partial runs, horizon backlog, max-drain clipping, linear p95 and fixed offered load.
- Analytical fixture remains handoff32.8, induction33, first move34, pack52..76.1, outfeed77,
  shipping124, placement132, seal432, dispatch469, forklift return474 seconds.
- RED before E fixes: 5 failed/15 passed. Full post allowed branch entry; cancelled age timer moved
  end96 to300. Cancelling only the business callback was insufficient: the scheduler must ignore
  cancelled buckets when deciding the next live tick. last_dispatch_s also failed before addition.
- E focused integration: `47 passed in 19.45s`; hourly replay/determinism: `2 passed in 190.09s (0:03:10)`.
- AST audit: `oversized_functions []`, `test_engines_without_invariants []`.

## Full commit gates

Each gate ran pytest, strict mypy, ruff check, ruff format --check and validate-contracts in that order.

| Task/commit | Exact pytest output | Exact mypy output | Ruff format output |
|---|---|---|---|
| A / 6144a0e | 231 passed in 525.81s (0:08:45) | Success: no issues found in 66 source files | 79 files already formatted |
| B / 5a0be9d | 273 passed in 304.85s (0:05:04) | Success: no issues found in 73 source files | 87 files already formatted |
| C / aa9edff | 293 passed in 284.87s (0:04:44) | Success: no issues found in 82 source files | 97 files already formatted |
| D / a2d9879 | 306 passed in 303.82s (0:05:03) | Success: no issues found in 84 source files | 100 files already formatted |
| E / this report's commit | 328 passed in 499.80s (0:08:19) | Success: no issues found in 90 source files | 108 files already formatted |

All five gates: `All checks passed!`; validate-contracts: `"status": "passed", "issues": []`.
The final gate reports engine qoima-engine-0.2.2, 184 picker nodes, 205 picker edges, 864 slots,
179 conveyor cells and 24 actors. Strict mypy including the benchmark tool also passed (91 files).

CLI smoke command (inputs include the separately materialized synthetic history):

```text
uv run python -m app.cli simulate --profile large-normal --horizon-s 3600 --out D:/QoimaTwin-runs/ae-cli-20261107
{"status": "complete", "run_id": "ab7210718568bfd9852fcd59331b9f77bbedaece564298ed241a225544ce0c73", "termination_reason": "drained"}
```

Post-write check: `CLI artifact hashes: 66 files verified; inline matches validated benchmark byte-for-byte`.
The inputs directory contains history_daily.csv, manifest.json and scenario.json.

## Scope and integration limits

The run schema remains shared v2.0. contracts/fixtures/proposed and the manifest/catalog/chunk
envelope are proposals for Tilek, pending agreement. No frontend files changed. Snapshots contain
mutable replay state, not event history; Engine.restore is not implemented (ADR0010). C5 verifies
the next grant using restored conveyor kernel occupancy/cursors, not a full engine restart.
This work measured one-hour normal/peak only; no eight-hour or browser FPS claim is made.
Forecast, slotting planner and API work remain outside these A-E tasks.
