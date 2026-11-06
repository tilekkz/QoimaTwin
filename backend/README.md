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
| Next: invariant checker + 30 s snapshots, run exporter for Tilek, mass-flow runs | open |

The fixture times now come from the engine and match `contracts/analytical_fixture.json`.
Mass-flow results (240/600 orders per hour) are not measured yet.

## Setup

Needs [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself.

```bash
cd backend
uv sync --locked
```

## Commands

```bash
uv run python -m app.cli validate-contracts   # JSON Schema + semantic checks of ../contracts
uv run pytest                                 # all tests
uv run pytest -m acceptance                   # numbered gates from 05_Acceptance_and_Demo.md
uv run pytest --cov                           # coverage gate: 85 % statement and branch
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests                         # strict mode
```

Optional git hooks (run from the repository root):

```bash
uv run --directory backend pre-commit install -c backend/.pre-commit-config.yaml
```

`QOIMA_CONTRACTS_DIR` overrides the contracts directory (default: `../contracts`).

## Layout

| Path | Content |
|---|---|
| `app/contracts/` | Strict immutable Pydantic models of the shared JSON files, loader, semantic validation |
| `app/navigation/` | Exact all-pairs shortest paths on the picker graph |
| `app/conveyor/` | 179-cell topology and the atomic one-hop tick (`transfer.py`) |
| `app/simulation/` | Time grid, phase scheduler on SimPy, engine and subsystems (picking, conveyor, packing, shipping, outbound, receiving) |
| `app/inventory/` | Transactional ledger with conservation checks |
| `app/data/`, `app/storage/` | Synthetic scenario materializer, canonical JSON and hashes |
| `app/cli.py` | Command-line tools |
| `tests/acceptance/` | One test per numbered gate (G1, S1, C1, ...) |
| `docs/adr/` | Architecture decisions |
| `docs/research/` | Independent reviews of the spec by Codex main and Codex edu |

## Rules

- Exact time: integer ticks, 3,000,000 per second (ADR 0002). No float accumulation in the engine.
- One mutation path for stock (ADR 0005). Conservation per SKU is checked after every settled timestamp.
- Files in `frontend/` belong to Tilek. Changes to `contracts/` are agreed with him first (ADR 0007).
