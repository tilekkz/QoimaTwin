# QoimaTwin backend

Owner: Arman. Deterministic warehouse simulation, planning, forecast, run export and API.
The current development target is the 144x72 m adaptive V3 warehouse. Its isolated input,
static compatibility and catalog modules live in `app/v3/`; the existing 72x48 m V2 engine
retains its analytical regression. V2 requirements remain in `../01_Technical_Specification.md`
and `../05_Acceptance_and_Demo.md`. Versioned decisions are in [`docs/adr/`](docs/adr/README.md).

## Adaptive V3

The backend pins Tilek's V3 proposal inputs at `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`.
They describe 776 slots, 530 initial HUs, 200 SKUs, 12,256 units and 9,403.85 kg. Loading checks
exact source bytes, schemas and record relationships; geometry admission uses exact arithmetic.
Directed routes and a separate microsecond time policy preserve the V3 geometry.

```bash
uv run python -m app.cli v3 validate
uv run python -m app.cli v3 catalog --out runs/v3-catalog
uv run python -m app.api --store-root D:/QoimaTwin-runs/api-store
```

The API serves `/api/v3/catalog`, `/api/v3/initial-state` and content-addressed source documents.
Catalog export contains the static 530-HU state and its provenance. Actual timed whole-HU
execution is available separately through the manual CLI and `/api/v3/manual-runs`; its
registered four-job profile covers SMALL/STANDARD handling at two ports with paid return.
See the [manual profile](docs/v3-manual-profile.md) and [manual API](docs/v3-manual-api.md).
The separate [conveyor component](docs/v3-conveyor.md) executes source-bound physical cells,
pivots and station-spur reservations through a reproducible CLI. The bounded
[connected SMALL workflow](docs/adr/0045-connected-light-flow.md) links paid picking,
cart handoffs, finite belt work, packaging and outbound service on one clock with a shared
unit ledger. Its explicit synthetic material and service choices do not prove hand contact
or the complete V3 warehouse. The [local PALLET cycle](docs/adr/0046-v3-timed-local-pallet-cycle.md)
adds paid operation timing and exclusive leases to the verified local geometry; it is not
an inbound warehouse workflow. The PALLET cycle currently exposes a Python component;
the [connected SMALL CLI](docs/v3-light-flow.md) publishes frozen inputs, actual events,
captured checkpoints and metrics with an immutable manifest.
The [connected SMALL API](docs/v3-light-api.md) registers one explicit source profile,
shares the existing calculation worker and serves verified raw files and captured state.
The [explicit SMALL profile](docs/adr/0048-v3-explicit-connected-small-profile.md)
binds a strict JSON proposal to verified source geometry and freezes every material,
worker and timing choice before execution; an [example](docs/proposals/adaptive-v3/light-flow-profile.example.json)
is provided without claiming measured hand-contact behavior.
The [unit ledger](docs/adr/0041-v3-unit-and-packaging-ledger.md) conserves individual ancestry
and explicit packaging material. The [timed workload](docs/v3-workload.md) freezes offers
without allocating stock or inferring hourly rates. A separate
[local pallet mesh proof](docs/adr/0042-v3-local-pallet-mesh-proof.md) checks actual pinned
geometry and continuous translations; it does not grant warehouse operational admission.
F1/F2/F3 test port mix, geometry/mass and elapsed time versus person-seconds using independent
hand calculations. See [inputs](docs/v3-inputs.md), [analytical fixtures](docs/v3-analytical.md),
and [source compatibility](docs/v3-admission-source.md). Shared contracts remain proposals until
agreed with Tilek; `frontend/` is unchanged by this backend work.

## Status

| Gate | State |
|---|---|
| H0: tooling, ADR 0001-0009, contract loader and hardened validator | done |
| B1: typed layout, all-pairs paths, 179-cell conveyor topology, G1-G4 | done |
| B2: deterministic synthetic scenarios, history, canonical hashing (`cli materialize`) | done |
| B3/B4 slice: one order end to end, analytical fixture 32.8 s ... 469 s ... 474 s | done |
| B5 part: receiving, inbound forklift, reserve staging (R1-R3, I6) | done |
| Settled invariants, 30 s replay snapshots and 60 s chunks | done |
| Schema-valid v2 run exporter and proposed bundle/fixture for Tilek | done |
| Horizon/end metrics, linear p95, role utilization and time-weighted queues | done |
| PDF P0: coherent horizon scalar metrics and ordered subsystem termination reasons | done |
| Executed picker distance, station load, belt/tote/receiving integrals and active labor | done |
| Mean28/HGB temporal forecasts and immutable history cache | implemented; see forecast protocol |
| Frozen ABC, greedy 0/2/8 swaps and paired comparison with relocation labor | implemented; see ADR 0016 |
| C5-C8, K1-K6, D1-D8, T1-T6 acceptance gates | done |
| Local API with one spawn worker, immutable artifacts and bounded replay windows | implemented; see API guide |
| Optional Mercury explanations from stored comparison facts | implemented; backend-only configuration and immutable cache |
| Contract 2.1 proposal, atomic transfers, business replay and full/delta checkpoints | implemented as opt-in; shared contract agreement pending |
| One-hour normal/peak determinism, invariants, runtime and export-size measurements | historical A-E report; final V2 measurements paused after the V3 scope change |

The fixture times now come from the engine and match `contracts/analytical_fixture.json`.
The materializer offers 240/600 orders per hour; measured dispatch and backlog are reported
separately from those input counts.
The [A-E one-hour acceptance and performance report](docs/research/2026-11-07-backend-ae-results.md)
records engine 0.2.2 results. It is historical evidence, not a benchmark of the current integrated
backend. Final integrated one-hour repeats and eight-hour measurements remain pending.

The current engine version is `qoima-engine-0.4.0`. Run identity uses `qoima-run-v2`, the nine
semantic input hashes, the declared horizon and all scenario provenance; proposed wire output
has a separate run identity namespace. See [ADR 0024](docs/adr/0024-provenance-publication-identity.md).

## Setup

Needs [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself.

```bash
cd backend
uv sync --locked
```

## Commands

```bash
uv run python -m app.cli validate-contracts   # JSON Schema + semantic checks of ../contracts
uv run pytest -q                              # development tests, excludes slow
uv run pytest -q -m "slow or not slow" -n 2 --dist loadscope  # complete pre-push suite
uv run pytest -m acceptance                   # numbered gates from 05_Acceptance_and_Demo.md
uv run pytest -m "slow or not slow" -n 2 --dist loadscope --cov  # coverage gate: 85 %
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests                         # strict mode
uv run mypy --platform linux app tests         # check Linux typing branches on any host
uv run python -O -m tests.probes --fixture     # optimized-Python determinism smoke
uv run python -m app.cli simulate --profile large-normal --horizon-s 3600 --out runs/normal
uv run python -m app.cli simulate --profile large-normal --horizon-s 600 --format tilek-v2 --out runs/tilek-demo
uv run python -m app.cli simulate --profile large-normal --horizon-s 3600 --format proposal --out runs/proposal
uv run python -m app.cli simulate --profile large-normal --horizon-s 3600 --format proposal --include-inline --out runs/proposal-inline
uv run python -m app.api --store-root D:/QoimaTwin-runs/api-store  # loopback 127.0.0.1:8000
uv run python tools/benchmark_runs.py --out D:/QoimaTwin-runs/new-benchmark-directory
uv run python tools/benchmark_runs.py --horizon-s 28800 --out D:/QoimaTwin-runs/new-shift-directory
```

Optional git hooks (run from the repository root):

```bash
uv run --directory backend pre-commit install -c backend/.pre-commit-config.yaml
```

`QOIMA_CONTRACTS_DIR` overrides the contracts directory (default: `../contracts`).
Output directories must be new or empty. Partial and failed simulations return a nonzero exit code
with a JSON report. Positive integer-second horizons up to 168 hours are supported; horizons below
one hour are explicitly marked as shortened runs. `--assignment PATH` selects a validated assignment.

`simulate` materializes the synthetic inputs first, then runs with invariants enabled. It uses
the supplied illustrative assignment, not a trained ABC plan. The default `--format v2` writes
schema-valid shared 2.0 `run.json`, a proposed transport `manifest.json`, a catalog and 60-second
chunks. `--format proposal` instead writes the backend 2.1 proposal catalog, event chunks and
full/delta checkpoint files. Proposal inline `run.json` is omitted by default;
`--include-inline` adds that duplicate document. Repeated actions in neighboring chunks have
stable IDs. Verify exact uncompressed file-byte hashes from manifest descriptors.
See the [proposal schema, fixture and replay guide](docs/proposals/contract-2.1/README.md).
The manifest reports at_horizon and at_end metrics separately, with status and reasons for each
subsystem. All legacy run.json scalar metrics use the horizon window: counts strictly before H,
and duration integrals over [0,H). A fully dispatched orders flow can coexist with blocked receiving.
The shared schemas remain v2.0; the transport envelope and files under
`contracts/fixtures/proposed/` are proposals for Tilek, not an agreed v2.1 contract. The
backend-owned 2.1 schema and fixture live under `docs/proposals/contract-2.1/`. At inspected
frontend commit `10496fd4ccd748676c036c371dd1a29881f046d1`, Tilek loads inline 2.0 and supports
visual seek, but has no API/manifest/chunk loader or proposal business-state decoder. Changing
the schema version alone does not provide that integration. The explicit `tilek-v2` adapter
below supplies the existing reader; it is separate from the new V3 warehouse catalog.

Forecast validation uses the first 42 historical days for fitting and the following 14 for evaluation;
the final forecast uses all 56 observed days. CPU measurements remain outside forecast identity.
The planner receives historical visit estimates, never test orders. Baseline and candidate share
exogenous inputs; the candidate pays relocation labor separately before the shift. Zero-benefit
plans remain explicit no-ops and worse observed results remain visible. See
[ADR 0015](docs/adr/0015-forecast-temporal-protocol.md) and
[ADR 0016](docs/adr/0016-planning-and-comparison-protocol.md).

Frozen synthetic history bytes are reused across processes through a verified persistent cache
outside the checkout. Defaults are `~/AppData/Local/QoimaTwin/history-cache-v1` on Windows and
`~/.cache/qoimatwin/history-cache-v1` elsewhere. `QOIMA_HISTORY_CACHE_DIR` can select an absolute
external directory; paths inside the current checkout are rejected. Input/source fingerprints
and stored byte hashes are checked before reuse; callers receive defensive decoded data rather
than a shared mutable DataFrame. See [ADR 0022](docs/adr/0022-persistent-history-artifact-cache.md).

## Local API and optional explanations

The [API guide](docs/api.md) gives the catalog, materialization, mean28/HGB, plan 0/2/8,
comparison and manifest/chunks/file workflow, with IDs taken from responses. Heavy calculations
run in one owned spawn process; another uncached request receives 409 while it is busy. Completed
requests reuse immutable artifacts. HTTP cancellation does not cancel admitted work; graceful
shutdown waits for it. Default binding is loopback; browser integration needs a same-origin
setup or a development proxy. Replay file routes use descriptor SHA256 IDs, not bundle paths.

Mercury runs only for an explicit `POST /api/compares/{comparison_id}/explanation` request. It
explains stored comparison facts and supports complete or partial simulation outcomes; it does
not choose the plan or alter metrics. Configure the key in the backend process environment or
ignored `backend/.env`, never in HTTP bodies or frontend files. Results are cached by semantic
facts/model/prompt inputs; provider failures are sanitized. See the [Mercury guide](docs/mercury.md).
Neither the API examples nor this status table constitute a completed live-workflow or
eight-hour performance measurement.

## Layout

For Tilek's current inline reader, use `--format tilek-v2`. The separate
[visual compatibility projection](docs/tilek-compatibility.md) preserves source metrics and
timing while supplying pallet placements, attachments and forklift operation names.
It passed 92 checks on the actual TypeScript from `polished@cb5777f` and `adaptive@22296bc`.
See [the compatibility review](docs/research/2026-11-07-tilek-compatibility.md) for remaining
reader limitations and the distinct, unfinished adaptive v3 warehouse proposal.

A local HTTP workflow has exercised materialization, mean28/HGB, planning, paired simulation,
raw file hashes, repeat seek windows and an actual Mercury 3 explanation. Protocol v3 returned
eight validated Russian observations; repeating the request returned the same cached result.

| Path | Content |
|---|---|
| `app/contracts/` | Strict immutable Pydantic models of the shared JSON files, loader, semantic validation |
| `app/navigation/` | Exact all-pairs shortest paths on the picker graph |
| `app/conveyor/` | 179-cell topology and the atomic one-hop tick (`transfer.py`) |
| `app/simulation/` | Time grid, phase scheduler on SimPy, engine and subsystems (picking, conveyor, packing, shipping, outbound, receiving) |
| `app/inventory/` | Transactional ledger with conservation checks |
| `app/data/`, `app/storage/` | Synthetic scenario materializer, canonical JSON and hashes |
| `app/forecast/` | Temporal mean28/HGB forecasts, WAPE and immutable semantic snapshots |
| `app/planning/`, `app/comparison/` | Frozen ABC, exact relocation routes and paired labor comparisons |
| `app/api/` | Loopback-first HTTP routes, spawn-worker admission, immutable publication and replay windows |
| `app/explanations/` | Optional Mercury provider, server-derived facts and semantic cache keys |
| `app/v3/` | Pinned adaptive V3 inputs, exact static compatibility, directed routes, analytical fixtures and catalog API |
| `app/exporter/` | Shared2.0 export and opt-in 2.1 proposal transport, checkpoint codec and public-state replay |
| `app/cli.py` | Command-line tools |
| `tests/acceptance/` | One test per numbered gate (G1, S1, C1, ...) |
| `docs/adr/` | Architecture decisions |
| `docs/research/` | Independent reviews of the spec by Codex main and Codex edu |

## Rules

- Exact time: V2 uses 3,000,000 ticks/s (ADR 0002); V3 quantizes each positive operation upward to microseconds (ADR 0026). No float accumulation in execution clocks.
- One mutation path for stock (ADR 0005). Conservation per SKU is checked after every settled timestamp.
- Files in `frontend/` belong to Tilek. Changes to `contracts/` are agreed with him first (ADR 0007).

The separate [V3 manual profile guide](docs/v3-manual-profile.md) describes the explicit
four-job SMALL/STANDARD whole-HU receipt/shipping proposal, CLI materialization and execution,
actual-event replay and horizon/end metrics. It retains the full initial stock and actor
identities, pays all declared travel/handling/return and checks ownership after settled ticks.
It does not yet implement the complete V3 warehouse workflow or a Tilek frontend adapter.
The [manual V3 API](docs/v3-manual-api.md) accepts the registered frozen profile,
shares the existing single calculation worker with V2, publishes immutable artifacts,
and exposes SHA-addressed files and bounded seek. Shared schemas remain unchanged.
