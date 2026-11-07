# 2026-11-07 PDF requirements and evidence map

Source: **ТЗ для Армана: backend QoimaTwin**, 11 pages, dated2026-11-07; the local text
extraction is `D:/QoimaTwin-wt/tz-20261107.txt`. Normative details remain in
`01_Technical_Specification.md`, `05_Acceptance_and_Demo.md` and the cited ADRs.
This is a work-in-progress traceability map, not a declaration that the PDF is complete.
Baseline reviewed: `dd6e7ba`. Other workers' changes require integration and final evidence.

`Mandatory` means an explicit deliverable or acceptance condition in the PDF. `Optional` means
the PDF explicitly says "if time remains", "can improve", or "after everything mandatory".
Infrastructure items in the improvement section are still implemented where directly requested.
The table records scope and evidence honestly; a prepared test is not a passing integrated gate.

## Existing-code corrections and contract

| ID / page | Priority | Required behavior | Evidence / remaining work |
|---|---|---|---|
| P0.1 /2 | Mandatory | Separate exported horizon/end metrics; late dispatch excluded atH | Status/export owners; final projection tests pending integration |
| P0.2 /2 | Mandatory | Atomic cell_moved and replay between snapshots | Export owner; existing hourly replay covers physical cells only, not full mutable state |
| P0.3 /3 | Mandatory | Subsystem status and error>deadlock>max_drain>unfulfilled reasons | Status owner, horizon/reasons tests; verify integrated summary |
| P0.4 /3 | Mandatory | Heap scheduler preserving event hashes | Runtime owner; runtime scaling measurements by main |
| P0.5 /3 | Mandatory | Nonzero partial/error CLI, safe output directory, JSON errors | Runtime/main owners; CLI tests and smoke required |
| P0.6 /3 | Mandatory | Configured chunk duration, shared splitter and metadata | Runtime/export owners; non60s regression required |
| P0.assert /3 | Mandatory | Replace3 runtime asserts, preserve checks under python-O | Runtime owner; quality subprocess smoke executes analytical run under-O |
| P0.totes /3 | Mandatory | Invariants use config.totes_total | Status owner; default96 alone is not evidence |
| P0.scan /3 | Mandatory | Explicit scan/age rank, not lexicographic actor IDs | Status owner; same-timestamp regression required |
| P0.complete /3 | Mandatory | Complete only with dispatched+rejected=arrived | Status owner; counts and reason tests required |
| P0.adrs /3 | Mandatory | Clarify receiving area vs waiting, SEAL_PENDING phase, C5 limit | Status owner ADR0013; receiving area includes service, waiting KPI excludes it |
| P0.short /3 | Mandatory | Fractional-hour demo inputs and explicit truncated label | Runtime owner; quality60s normal4/peak10 tests prepared, initially RED on baseline |
| C2.1.1 /4 | Mandatory, coordination | Pallet/dock/queue locations, slots and attach/detach | Main export proposal; scene coordinates and shared contract agreement pending |
| C2.1.2 /4 | Mandatory | One physical transition record; logical adapter; peak raw<=30MB | Main export proposal and measured benchmark; do not equate streaming with lower total bytes |
| C2.1.3 /4 | Mandatory | Metric windows and subsystem statuses | SeeP0.1/P0.3 |
| C2.1.4 /4 | Mandatory, coordination | Shared operation enums and carrying_cargo_id | Main proposal; Tilek agreement cannot be inferred from a backend test |
| C2.1.5 /4 | Mandatory | ended_at_s,ticks_per_second,9 identity hashes,event at_tick | Main export owner; recompute run_id from one run artifact |
| C2.1.6 /4 | Mandatory | Document logical inlet/PK/SHIPPING containers | Main export owner; endpoint validation and adapter required |
| C2.1.7 /5 | Mandatory | Per-kind typed payloads and required events | Main proposal schema; shared contracts unchanged without agreement |
| C2.1.8 /5 | Mandatory | BLOCKED/WAIT reasons and snapshot action reference | Main/status owners; blocked snapshot regression required |
| C2.1.9 /5 | Mandatory | Typed snapshots, watermark and client-compatible state hash | Main export owner; full replay/hash proof remains required |

## Experiment and scale

| ID / page | Priority | Required behavior | Evidence / remaining work |
|---|---|---|---|
| B6.mean28 /5 | Mandatory | Training42/validation14, final56, no test-day access, WAPE+identity | Forecast owner; final gates must demonstrate no leakage |
| B6.abc /5 | Mandatory | Frozen training-visitsABC, mean3-home roundtrip,ties;200occupied/88empty | Planning owner; reserve stock must stay unchanged |
| B6.greedy /6 | Mandatory | 0/2/8 swaps,J cost,32SKU/496pairs,6*8s handling,both orientations | Planning owner; P1-P6 and hand route/labor expectations required |
| B7.compare /6 | Mandatory | Same exogenous hashes; net savings subtract relocation labor once | Main/planning owners; mismatch rejection and baseline/candidate pair |
| B7.api /6 | Mandatory | catalog/materialize/forecast/plans/compare/run manifests/chunks | API task follows quality; validation422,idempotency,process worker,loopback |
| B6.hgb /6 | Mandatory before final defense | Poisson,lags1/7/14/28,shifted means7/28,SKUonehot;frozen parameters | Forecast owner; WAPE and CPUtime alongside mean28 |
| B7.kpi /6 | Mandatory | Per-station load,belt occupancy/blocking,totes,distance,admitted/picked,zones | Status owner; hand-oracle tests and exported fields required |
| PERF.validation /7 | Mandatory | One schema validation, reusable validator | Main export owner; execution-count test needed |
| PERF.snapshot /7 | Mandatory | Smaller replay snapshots/deltas, no browser timers | Main export owner; recovery and hash tests needed before size claims |
| PERF.stream /7 | Mandatory | Streaming chunks; inline opt-in; bounded memory | Main export owner; measure8h peak memory, not just final file bytes |
| PERF.canonical /7 | Mandatory | Faster validation with identical canonical bytes | Runtime owner; invalid-input and bytes regressions needed |
| PERF.history /8 | Mandatory | Immutable history cache by hash | Forecast/runtime owners; quality cache only covers test publication input |
| PERF.invariants /8 | Mandatory | Check changedSKU cheaply without weakening invariants | Status owner; dirtySKU and global safety regressions needed |
| B8 /8,10 | Mandatory | Eight-hour normal/peak runtime,memory,export measurements; version bump | Main final benchmark; hourly evidence does not close this requirement |
| Optional experiments /7 | Optional | PromotionDEMO173*5 and14+4vs12+6 staffing | Not claimed implemented by quality work |
| Results table /7,10 | Mandatory final delivery | Actual per-gate input/expected/observed/status table05section12 | Main final report; optional one-command generator is separate |

## Quality and infrastructure

| ID / page | Priority | Required behavior | Evidence / remaining work |
|---|---|---|---|
| Q.ledger /8 | Mandatory | Random reserve/pick/release; atomic failures and conservation | `tests/property/test_ledger_sequences.py`:100examples, independent stock/claim model |
| Q.conveyor /8 | Mandatory | Random graphs, conservation, no collisions/extra hops, merge fairness | `tests/property/test_conveyor_graphs.py`:150graphs,50fairness cases and fixed3-way wrap |
| Q.replay /8 | Mandatory | Snapshotk+events after watermark equals live state+finalhash | Main replay owner; hourly cell-only differential test is narrower |
| Q.process /8 | Mandatory | Two hash seeds, fixed reviewed runID, Linux+Windows | `tests/integration/test_process_determinism.py`+`tests/probes.py`; seed/-O proof passes; fixed golden pending final version |
| Q.boundary /8 | Mandatory | OrdersH-tick,H,H+tick with drain0,tick,60 | Status owner; all9 combinations required |
| Q.reasons /8 | Mandatory | Inventory rejection plus blocked receiving | Status owner; verify primary+fullreason set |
| Q.pallet8 /8 | Mandatory | Ninth seal waits for one of8places; correct forklift times | `test_capacity_reservations.py`: frees at18, ninth dispatch373, return378, hand-derived |
| Q.parcel11 /8 | Mandatory | Eleventh parcel belongs to second pallet | Same file: first seal40, second48+300=348;10+1parcels |
| Q.merge3 /8 | Mandatory | Three sources,one blocked,cursorwrap | Property module fixed source order S0,S1,S2; blockedS1; grantsS2,S0 repeated |
| Q.rollback /8 | Mandatory | Rejected multiline order leaves no claims,next order ships | Capacity module: two1unit SKUs; request(1,2)rejects; next(1,1)ships |
| Q.receiving /8 | Mandatory | Receiving2/reserve2 with5receipts | Capacity module: accepted4,stored2,area2,external1; putaways224,404 |
| Q.oracles /8 | Mandatory | Document derivations68/179/112/184/205/288/576 | Comments in exporter/topology/geometry tests cite fixture or01/05; no learned engine constants |
| Q.cli /8 | Mandatory | simulate/materialize exit codes and failures | Runtime/main owners; cachedhistory only changes input reuse in existing materialize tests |
| Q.mass /9 | Mandatory | Onehourrun/profile; shortdeterminism; partitionarrivals | Hourly tests now singlepass+slow; independent60s runs4/10orders await fractionalruntime |
| Q.slow /9 | Mandatory | Defaultnot slow; full CI and prepush | pyprojectdefault; fullcommand below; collection verified on PowerShell |
| Q.fixtures /9 | Mandatory | Session analytical/materialized input; cache history safely | conftest: readonly completed engine; private history copies only for publisher tests; real history repeat remains slowtest |
| Q.xdist /9 | Mandatory | Parallel CI | pytest-xdist3.8.0 pinned+locked;2workers/loadscope; focused worker run passes |
| I.ci /9 | Requested improvement | data/tools paths,timeout,SHAactions,pinneduv,-Osmoke | CI updated; official tags resolved2026-11-07; remoteCI awaits push |
| I.gitignore /9 | Requested improvement | Ignore.hypothesis | Added.gitignore rule |
| I.version /9 | Requested improvement | Remove conflicting deadcanonicalization constant | Main owns app/version.py; quality did not modify app code |
| I.paths /9 | Requested improvement | Remove personalpath in benchmarkdocstring | Main benchmark owner; quality did not modify benchmark |
| I.cleanup /9 | Requested improvement | Archive logs,inspect and remove stale worktrees/branches | Main owner; no worktrees deleted |
| I.pr /9 | Requested improvement | PR arman/backend-core->main | Main owner; only after green final gates |

## Explicitly optional extensions and unresolved coordination

| Page | Classification | Item | Status / constraint |
|---|---|---|---|
|9 | Optional | FullEngine.restore using serializable scheduler commands | Not implemented; replay snapshots are not restart checkpoints |
|9 | Optional | Bottleneck explanation from queue/blocking integrals | Status/main may add; no quality claim |
|9 | Optional | One-command gate-report | Main may add; actual final result table remains required |
|9 | Optional | gzip transport with hashes of uncompressed bytes | Main/API may add; must not replace rawpayload measurement |
|10 | Requested improvement | AppError hierarchy,JSONerrors,assignment/configschema validation | Runtime/API owners |
|10 | Requested improvement | CLIassignment,horizonupperbound,contractspath/layoutversion | Runtime/main owners |
|10 | Mandatory portability check | FixedrunID onLinux/Windows exposes libm weight differences | Finalgolden pending; subprocesssameOS test alone does not prove crossOS |
|10 | Optional, aftermandatory | BackendLLMexplanation withoutfrontendsecrets | Not implemented/claimed |
|11 | Decision needed | Allordersshipped butreceivingblocked: overallstatus | StatusADR0013/main decision; preserve subsystem distinction |
|11 | Decision needed | LocalfilesvsAPI demo transport | Main/user coordination; backend cannot assume frontendagreement |

## Gate commands and evidence rules

From `backend/`, default development check is `uv run pytest -q` (excludes `slow`).
Full pre-push and CI test command, portable to PowerShell without empty-argument ambiguity:

```text
uv run pytest -q -m "slow or not slow" -n 2 --dist loadscope --cov --cov-report=term-missing
uv run mypy app tests
uv run ruff check .
uv run ruff format --check .
uv run python -m app.cli validate-contracts
uv run python -O -m tests.probes --fixture
```

Do not claim the fastsuite1-2minute target or8hruntime until measured after integration.
New properties and finitecapacity tests passed on the baseline; this is additional coverage,
not fabricatedRED evidence. Fractional-hour tests intentionally expose the known baseline gap.
The fixed processgolden must be reviewed with final schema/engine/inputidentity versions;
never refresh it silently from the output of an unknown or failing engine.

For accepted-arrival accounting use disjoint sets: dispatched + pending + rejected = arrived.
The old backlog includes rejected orders; adding rejected again to it would doublecount.
Horizon milestones use `<H`; snapshots contain all settled events`<=T`.

CI pins were resolved from official repositories, not third-party snippets:
[checkoutv4.3.1](https://github.com/actions/checkout/releases/tag/v4.3.1),
[setup-uvv6.8.0](https://github.com/astral-sh/setup-uv/releases/tag/v6.8.0).
`git ls-remote` returned respectively `34e114876b0b11c390a56381ad16ebd13914f8d5`
and `d0cc045d04ccac9d8b7881df0226f9e82c39688e`. uv0.13.4 matches the observed local tool.
