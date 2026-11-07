# V3 manual component measurements, 2026-11-08

Observed on Windows AMD64 / Python3.12.15 at backend commit
`9ef524ba6a551c8aec5cbea3e1a2e58c15d6d09a`, manual engine
`qoima-manual-engine-v3-proposal-2`. This is the explicit four-job SMALL/STANDARD
profile, two inbound/two outbound offers at 0/60s, H600/end900, two ports with one
declared buffer each. All530 initial HUs,200 SKU and24 actor identities remain.
These are measured results, never acceptance-test numerical oracles.

Two fresh subprocesses ran sequentially with invariants enabled. Other owned
heavy tests were deferred during the measurement; this is a local observation,
not a controlled-machine performance guarantee or a full V3 normal/peak result.

| Observation | Repeat1 | Repeat2 |
|---|---:|---:|
| Engine execution wall seconds |1.7304282|1.6458799|
| Engine execution CPU seconds |1.6875|1.4375|
| Whole subprocess wall seconds, including compile/export/startup/shutdown |40.0267864|37.8966176|
| Whole process peak RSS bytes |85368832|86773760|
| Raw transport export bytes |6176486|6176486|
| Event count |186|186|
| Operational status |complete|complete|

All16 recorded determinism fields passed, including separate process identity,
input/source/graph/proposal hashes, native run ID, events and every exported file.
The raw export count includes the graph, metadata, events, snapshots and manifest;
the whole subprocess timing also includes extra validation passes and metrics.
It must not be described as engine-only latency.

```text
run_id=c11df508e80a9bb5ae158be3299d499b7aee810cd109d9925a3fa8e1f9146c86
events_sha256=e167d9665ec168f8e8d0c70133063362b6badf84342c07adf0795c9d2aa1e851
artifacts_sha256=e2c711e30abdae2c6c8b4c531c6f188ed36654e3ef9e3ceb3b7d1eaaa0e69a57
input_hash=757e11b03a49790e08ecb05e9ebf5df4f5a9d0987a39d6aa888187c9afba18aa
```

Reproduction from backend, with a new external output directory:

```powershell
uv run python tools/benchmark_v3_manual.py `
  --bundle data/v3-proposal `
  --proposal data/v3-execution-proposals/manual-whole-hu-demo-v1.json `
  --out D:/QoimaTwin-runs/manual-benchmark-new --iterations 2
```

Raw evidence is outside Git at
`D:/QoimaTwin-runs/v3-manual-benchmark-20261108-version2-retry1/benchmark.json`.
The first invocation used an incorrect proposal path under docs and stopped
with FileNotFoundError before simulation. Its failed directory is retained;
the corrected invocation used a fresh output directory. No output was deleted
or treated as a successful measurement. Full-shift all-class/all-port V3
normal/peak benchmarks and N0-N4 comparisons remain pending.
