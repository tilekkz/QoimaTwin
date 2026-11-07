# QoimaTwin backend

Owner: Arman. Deterministic warehouse simulation, planning, forecast, run export and API for the 72×48 m warehouse
(`qoima-72x48-v2`). The spec is in `../01_Technical_Specification.md`, the gates are in `../05_Acceptance_and_Demo.md`,
and the decisions are in [`docs/adr/`](docs/adr/README.md).

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
| One-hour normal/peak determinism, invariants, runtime and export-size measurements | see research report |

The fixture times now come from the engine and match `contracts/analytical_fixture.json`.
The materializer offers 240/600 orders per hour; measured dispatch and backlog are reported
separately from those input counts.
See [the one-hour acceptance and performance report](docs/research/2026-11-07-backend-ae-results.md).

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
uv run python -m app.cli simulate --profile large-normal --horizon-s 3600 --out runs/normal
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
the supplied illustrative assignment, not a trained ABC plan. Output contains schema-valid
`run.json`, a proposed `manifest.json`, an initial-state/catalog file and 60-second chunks.
Load catalog plus chunks for streaming; the full inline copy is optional for readers. Repeated
actions in neighboring chunks have stable IDs. Verify exact byte hashes from the manifest.
The manifest reports at_horizon and at_end metrics separately, with status and reasons for each
subsystem. All legacy run.json scalar metrics use the horizon window: counts strictly before H,
and duration integrals over [0,H). A fully dispatched orders flow can coexist with blocked receiving.
The shared schemas remain v2.0; the transport envelope and files under
`contracts/fixtures/proposed/` are proposals for Tilek, not an agreed v2.1 contract.

Forecast validation uses the first 42 historical days for fitting and the following 14 for evaluation;
the final forecast uses all 56 observed days. CPU measurements remain outside forecast identity.
The planner receives historical visit estimates, never test orders. Baseline and candidate share
exogenous inputs; the candidate pays relocation labor separately before the shift. Zero-benefit
plans remain explicit no-ops and worse observed results remain visible. See
[ADR 0015](docs/adr/0015-forecast-temporal-protocol.md) and
[ADR 0016](docs/adr/0016-planning-and-comparison-protocol.md).

## Layout

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
| `app/cli.py` | Command-line tools |
| `tests/acceptance/` | One test per numbered gate (G1, S1, C1, ...) |
| `docs/adr/` | Architecture decisions |
| `docs/research/` | Independent reviews of the spec by Codex main and Codex edu |

## Rules

- Exact time: integer ticks, 3,000,000 per second (ADR 0002). No float accumulation in the engine.
- One mutation path for stock (ADR 0005). Conservation per SKU is checked after every settled timestamp.
- Files in `frontend/` belong to Tilek. Changes to `contracts/` are agreed with him first (ADR 0007).
