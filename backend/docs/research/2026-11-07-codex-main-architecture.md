# QoimaTwin v2 — Arman’s backend implementation plan

Scope: `backend/app`, `backend/tests`, and backend build/CI configuration. Tilek owns frontend implementation; Arman supplies validated contracts, replay artifacts, reference reducers, and conformance fixtures.

The supplied documents describe expected behavior, not an implemented simulator. The geometry and stock counts are internally consistent: 184 pedestrian nodes, 205 edges, 179 conveyor cells, 864 slots, 600 lots, and 600,000 units. No files were modified.

## 1. Repository, dependencies, and quality gates

Use a modular monolith: one FastAPI application, a separate CPU worker process, a deterministic SimPy engine, and immutable artifacts on local disk. Avoid introducing distributed services before there is a deployment requirement for them.

```text
backend/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .pre-commit-config.yaml
├── Dockerfile
├── .dockerignore
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── cli.py
│   ├── settings.py
│   ├── version.py
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   ├── middleware.py
│   │   ├── auth.py
│   │   ├── catalog.py
│   │   ├── scenarios.py
│   │   ├── forecasts.py
│   │   ├── plans.py
│   │   ├── comparisons.py
│   │   ├── runs.py
│   │   └── jobs.py
│   ├── contracts/
│   │   ├── base.py
│   │   ├── ids.py
│   │   ├── layout.py
│   │   ├── config.py
│   │   ├── actors.py
│   │   ├── scenario.py
│   │   ├── assignment.py
│   │   ├── forecast.py
│   │   ├── plan.py
│   │   ├── events.py
│   │   ├── actions.py
│   │   ├── snapshots.py
│   │   ├── run.py
│   │   ├── transport.py
│   │   └── validation.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── state.py
│   │   ├── locations.py
│   │   ├── commands.py
│   │   ├── transactions.py
│   │   └── invariants.py
│   ├── data/
│   │   ├── scenario_materializer.py
│   │   ├── history.py
│   │   ├── seeds.py
│   │   └── provenance.py
│   ├── forecast/
│   │   ├── features.py
│   │   ├── mean28.py
│   │   ├── hgb.py
│   │   ├── evaluation.py
│   │   └── service.py
│   ├── planning/
│   │   ├── abc.py
│   │   ├── surrogate.py
│   │   ├── relocation.py
│   │   ├── greedy.py
│   │   └── comparison.py
│   ├── navigation/
│   │   ├── graph.py
│   │   ├── shortest_paths.py
│   │   └── picking_routes.py
│   ├── inventory/
│   │   ├── ledger.py
│   │   ├── reservations.py
│   │   └── relocation.py
│   ├── workforce/
│   │   ├── registry.py
│   │   ├── dispatch.py
│   │   ├── picker.py
│   │   └── actions.py
│   ├── conveyor/
│   │   ├── topology.py
│   │   ├── transfer.py
│   │   ├── arbitration.py
│   │   └── admissions.py
│   ├── packing/
│   │   ├── station.py
│   │   └── targeting.py
│   ├── receiving/
│   │   ├── intake.py
│   │   └── putaway.py
│   ├── shipping/
│   │   ├── scanning.py
│   │   ├── palletization.py
│   │   └── dispatch.py
│   ├── transport/
│   │   ├── forklift.py
│   │   └── tasks.py
│   ├── simulation/
│   │   ├── clock.py
│   │   ├── simpy_adapter.py
│   │   ├── scheduler.py
│   │   ├── phase_dispatch.py
│   │   ├── engine.py
│   │   ├── checkpoint.py
│   │   └── termination.py
│   ├── metrics/
│   │   ├── accumulators.py
│   │   ├── labor.py
│   │   ├── queues.py
│   │   ├── orders.py
│   │   └── summary.py
│   ├── exporter/
│   │   ├── event_writer.py
│   │   ├── action_writer.py
│   │   ├── snapshots.py
│   │   ├── chunks.py
│   │   ├── manifest.py
│   │   └── inline_adapter.py
│   ├── replay/
│   │   ├── reducer.py
│   │   ├── seek.py
│   │   └── interpolation.py
│   ├── storage/
│   │   ├── canonical_json.py
│   │   ├── hashes.py
│   │   ├── artifacts.py
│   │   └── job_repository.py
│   └── jobs/
│       ├── service.py
│       ├── worker.py
│       └── recovery.py
├── typings/                         # Narrow stubs for untyped library interfaces
└── tests/
    ├── conftest.py
    ├── builders.py
    ├── fixtures/
    ├── contracts/
    ├── acceptance/
    ├── unit/
    ├── integration/
    ├── properties/
    └── performance/

.github/workflows/backend-ci.yml
```

**Dependency baseline.** Pin direct dependencies exactly; commit all transitive versions and distribution hashes in `uv.lock`. These are proposed installation pins, not a claim that this combination has already passed integration testing.

| Group | Exact pins |
|---|---|
| Runtime | `fastapi==0.162.0`, `pydantic==2.14.3`, `uvicorn==0.54.0`, `simpy==4.1.2` |
| Numerical/data | `numpy==2.5.4`, `pandas==3.1.1`, `scikit-learn==1.9.1` |
| Contract validation | `jsonschema==4.26.0` |
| Quality | `ruff==0.17.4`, `mypy==2.4.1`, `pre-commit==4.7.0` |
| Testing | `pytest==9.2.0`, `hypothesis==6.170.15`, `pytest-cov==7.1.0`, `httpx==0.28.1` |
| Toolchain | `uv==0.13.7`; Python `>=3.12,<3.13`, with one exact 3.12 patch recorded at H0 |

Release references: [FastAPI](https://pypi.org/project/fastapi/), [Pydantic](https://pypi.org/project/pydantic/), [Uvicorn](https://pypi.org/project/uvicorn/), [SimPy](https://pypi.org/project/simpy/), [NumPy](https://pypi.org/project/numpy/), [pandas](https://pypi.org/project/pandas/), [scikit-learn](https://pypi.org/project/scikit-learn/), [jsonschema](https://pypi.org/project/jsonschema/), [Ruff](https://pypi.org/project/ruff/), [mypy](https://pypi.org/project/mypy/), [pre-commit](https://pypi.org/project/pre-commit/), [pytest](https://pypi.org/project/pytest/), [Hypothesis](https://pypi.org/project/hypothesis/), [pytest-cov](https://pypi.org/project/pytest-cov/), [HTTPX](https://pypi.org/project/httpx/), [uv](https://pypi.org/project/uv/).

Essential `pyproject.toml` settings:

```toml
[project]
name = "qoimatwin-backend"
version = "2.0.0"
requires-python = ">=3.12,<3.13"
# dependencies: exact runtime pins above

[tool.uv]
package = false

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
mypy_path = "typings"
warn_unreachable = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-config --strict-markers"
markers = [
  "acceptance: numbered specification gates",
  "integration: complete subsystem integration",
  "property: generated state-machine tests",
  "performance: controlled benchmark runs",
]

[tool.coverage.run]
branch = true
source = ["app"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

Additional rules:

- Run `mypy --strict app tests`; no project-wide `ignore_missing_imports` or blanket `Any`. Isolate SimPy/sklearn typing limitations behind typed adapters and narrow reviewed stubs.
- Enforce **both statement and branch coverage ≥85%**, checked separately from coverage JSON. Require stronger coverage for scheduler, ledger, conveyor, and palletization.
- Pre-commit invokes the locked environment: Ruff check/format, mypy, contract-schema checks, and a short fixture suite.
- CI runs Linux and Windows Python 3.12 jobs; lint/type/schema checks, acceptance tests, properties, API/storage tests, and coverage. Scheduled/release CI also runs normal/peak eight-hour scenarios and performance gates.
- Pin GitHub Actions by commit SHA when creating the workflow. Cache dependencies by `uv.lock`; upload JUnit, coverage, acceptance reports, and failed-example artifacts.
- Use `uv sync --locked` in CI so dependency drift fails rather than silently rewriting the lock. [uv locking behavior](https://docs.astral.sh/uv/concepts/projects/sync/)
- Build a non-root container with a read-only application filesystem and a mounted artifact directory. Ship an offline wheel/cache bundle and verified demo artifacts for the presentation.
- `app.cli` commands: `validate-contracts`, `materialize`, `forecast`, `plan`, `simulate`, `compare`, `verify-run`, `benchmark`, `serve`, `worker`.

## 2. Domain model and invariant-preserving state

**Immutable inputs**

`contracts/base.py::FrozenModel`:

```python
model_config = ConfigDict(
    frozen=True,
    extra="forbid",
    strict=True,
    allow_inf_nan=False,
)
```

Use frozen nested models and tuples. A frozen model containing an ordinary mutable `dict` is insufficient; represent mappings as immutable entries or a validated immutable mapping type.

Principal models:

| Model | Contents |
|---|---|
| `Layout` | Bounds, racks, slots, pedestrian/forklift graphs, segments, ports, stations |
| `SimulationConfig` | Staffing, service durations, capacities, policies, horizon/drain rules |
| `Scenario` | Immutable orders, receipts, provenance, horizon, content hashes |
| `HistoryManifest` | Calendar, generation recipe, named RNG streams, train/validation boundaries |
| `Assignment` | Active slot–SKU mapping, independent reserve mapping, lot placements |
| `ForecastSnapshot` | Cutoff, feature/model versions, predictions, validation metrics |
| `RelocationPlan` | Disjoint swaps, orientation, route edges, transfers, labor |
| `RunInputs` | References and hashes for every behavior-affecting input |

`ids.py` defines distinct `NewType`s:

```text
SkuId, SlotId, RackId, NodeId, ActorId, VehicleId, OrderId,
CargoId, ToteId, ParcelId, PalletId, LotId, ReceiptId,
PackId, CellId, TaskId, RunId, ScenarioId, ForecastId, PlanId
```

`NewType` gives static separation, not runtime validation. Pydantic validators enforce namespace syntax, uniqueness, and referential integrity.

**Mutable simulation state**

Use plain `@dataclass(slots=True)` objects owned by one engine:

- `WarehouseState`
- `OrderState`
- `ActorState`
- `ToteState`
- `StationState`
- `ConveyorState`
- `ReceivingState`
- `ShippingState`
- `PalletState`
- `ForkliftState`
- `ReservationState`
- `MetricsState`

No module-global mutable state; no state retained inside inaccessible generator frames.

**Ledger**

`inventory/ledger.py::InventoryLedger` stores integer quantities keyed by physical account:

```text
(sku_id, lot_id, location)
```

Locations are a discriminated union:

```text
Pickface(slot), ReserveSlot(slot), ReceivingPosition(position),
InboundVehicle(vehicle), ReserveStaging(position),
Tote(tote), PackWip(station), Parcel(parcel), Dispatched(dock)
```

`InboundVehicle` is included in the reported receiving/transit bucket; it must not disappear between receiving and reserve staging.

Outbound pallets contain parcel references. Parcel contents remain the counted inventory leaves; pallet contents are derived aggregates, never an additional copy.

For every SKU:

```text
initial + accepted_receipts
  = pickface + reserve_slots + receiving_and_inbound_transit
  + reserve_staging + carried_or_tote + pack_wip
  + parcel_units_including_palletized_parcels + dispatched
```

`transactions.py::StateTransaction` is the only mutation entry point:

1. Validate source balances, destination capacity, actor/cargo ownership, and reservation preconditions.
2. Construct the complete state delta.
3. Apply debit/credit and associated ownership changes atomically.
4. Assert affected-SKU conservation, nonnegative balances, and resource invariants.
5. Publish immutable events only after successful commit.

Methods:

- `reserve_whole_order(order_id, lines)`
- `pick_reserved_line(order_id, sku_id, quantity)`
- `accept_receipt(receipt_id)`
- `transfer_stock(source, destination, quantity)`
- `start_pack(order_id, station_id)`
- `complete_pack(order_id, tote_id, parcel_id)`
- `dispatch_pallet(pallet_id)`
- `apply_relocation_transfer(...)`

Reservations are claims on existing stock:

```text
0 ≤ reserved ≤ on_hand
available = on_hand - reserved
```

Whole-order reservation is all-or-nothing. Failed validation changes neither stock nor resources.

**Tote invariant**

`TotePool.allocate()` and `TotePool.release_at_pack_complete()` maintain:

```text
available_ids ∩ allocated_ids = ∅
available_ids ∪ allocated_ids = {T001, ..., T096}
len(available_ids) + len(allocated_ids) = 96
```

Allocated covers picker custody, conveyor, waiting buffer, and PACK. After pack completion the parcel owns the goods and the tote is empty and available, even while the packer remains blocked.

Duplicate release, duplicate receipt acceptance, and duplicate dispatch are invariant failures. Replay reloading is handled through event cursors, not by accepting duplicate business operations silently.

## 3. Deterministic SimPy DES

### Scheduler and phase ordering

Use SimPy’s actual event queue as the **only future-event scheduler**. Implement:

- `simulation/simpy_adapter.py::PhaseEvent`
- `simulation/scheduler.py::PhaseScheduler`
- `simulation/phase_dispatch.py::DispatchCycle`
- `simulation/engine.py::SimulationEngine`

SimPy already supports event priority through `Environment.schedule()`. Same-time FIFO alone is insufficient for the required five phases. [SimPy scheduling](https://simpy.readthedocs.io/en/stable/topical_guides/time_and_scheduling.html), [Environment API](https://simpy.readthedocs.io/en/stable/api_reference/simpy.core.html)

Each scheduled descriptor contains:

```text
due_tick, phase, schedule_seq, command_kind, entity_id, payload, generation
```

`PhaseEvent` is a small tested adapter that schedules an already-triggered custom event with:

```python
env.schedule(event, priority=phase, delay=due_tick - now_tick)
```

Its callback calls a synchronous domain handler. The adapter encapsulates the small amount of SimPy event-initialization internals required for a custom event; pin SimPy and test the adapter directly.

The effective execution key is:

```text
(due_tick, phase, SimPy insertion order)
```

Insertion order is deterministic because all scheduling occurs through `PhaseScheduler`, which assigns monotonic `schedule_seq`. Restore pending descriptors in `schedule_seq` order to preserve equal-time/equal-phase ordering.

Export `seq` is a **separate monotonic counter assigned when an event is emitted**, not when a future command is scheduled.

| Phase | Handler |
|---|---|
| 0 | Timed operation completions, resource releases, expiry intents |
| 1 | External orders/receipts and receiving-boundary admissions |
| 2 | One atomic conveyor tick, including feed/outfeed admissions |
| 3 | Pallet sealing, assignments, service starts |
| 4 | Snapshots, consistency checks, finalized timestamp measurements |

Rules enforced by `PhaseScheduler.schedule()`:

- Never schedule into the past.
- Never schedule a lower phase at the current timestamp.
- Same-phase bookkeeping is synchronous or appended deterministically.
- Service durations must be positive. Zero-duration bookkeeping does not create a new service process.
- Exactly one conveyor execution per integer second.
- Exactly one coalesced phase-3 `DispatchCycle` per timestamp. It runs deterministic substeps to a fixed point, without advancing time or granting another conveyor hop.
- Checkpoint events cannot trigger business work.

Phase-3 order:

1. Apply expiry/full intents and mark `SEAL_PENDING`.
2. Seal eligible pallets.
3. Assign forklift tasks.
4. Start available receiving/packing/shipping services.
5. Assign eligible FIFO orders to free pickers.
6. Repeat only newly enabled bookkeeping/service-start decisions until stable.

Within each category, use explicit stable keys: actor ID, station ID, `(ready_tick, cargo_id)`, or `(arrival_tick, order_id)`.

Do not allow independently running SimPy `Store` callbacks or process wakeups to mutate domain state outside this ordering. Resource availability and bounded FIFO state live in the dataclasses; SimPy provides time and event scheduling. Actor workflows are explicit state machines.

### Exact clock

Plain integer microseconds cannot represent `2 / 1.2 = 5/3` seconds exactly. Rounding every edge can accumulate error and can eventually change a conveyor admission tick.

Use `clock.py::TimeGrid`:

1. Parse configuration decimal numbers exactly.
2. Compute primitive durations as `Fraction` during configuration compilation: edge travel, service components, arrivals, timers.
3. Choose:

```text
ticks_per_second = lcm(1_000_000, primitive-duration denominators)
```

For the supplied layout/defaults, **3,000,000 ticks/s** represents the required thirds and decimal service times exactly.
4. Convert compiled durations to integers. Runtime SimPy time is always integer.
5. Validate a bounded timebase and safe exported tick range. Unsupported parameter precision yields 422 rather than silent rounding.
6. Include the timebase/compiler version in the run input fingerprint.

Conveyor ticks satisfy:

```text
now_tick % ticks_per_second == 0
```

Admission after a completion uses exact integer ceiling. Thus:

- Handoff at 32.8 s → feed admission at 33 s.
- First movement → 34 s.
- Pack completion at 76.1 s → outfeed admission at 77 s.
- Completion exactly at integer 10 s in phase 0 → admission at 10 s in phase 2.

Wire `at_s` remains numeric seconds for v2 compatibility; the transport contract additionally carries exact ticks. `1e-6` is an assertion tolerance for exported seconds, never an epsilon used to reorder internal events.

### Conveyor

`topology.py::compile_cell_topology(layout)` builds indexed cells and ports from geometry:

- Use actual IDs such as `LOOP_TURN_E`, not abbreviated names in prose.
- `FEED01:0 → LOOP_W:52`.
- `LOOP_E:11 → BRANCH01:0`.
- Resolve interior ports, terminal offsets, and directed reachability.
- Validate all 18 induction-to-pack combinations.

`transfer.py::plan_tick(state)`:

1. Read immutable pre-tick occupancy.
2. Derive one eligible destination for each old cargo.
3. Resolve exits and vacancy propagation backwards through dependencies.
4. At merges, grant a destination to at most one contender.
5. Commit all old-cargo transfers atomically.
6. Admit pending new cargo into eligible feed/outfeed cells.
7. Set newly admitted cargo’s first movement time to the next tick.

A target cell may receive cargo if it was empty or its old occupant has a granted departure. A cargo can never become a source twice in the same tick.

The loop is cyclic, so a naïve topological sort is invalid. Resolve vacancy propagation from empty cells and valid exits using a worklist. The supported configuration has at least 16 empty loop cells; a full-ring configuration is rejected until a separate deadlock policy exists.

`arbitration.py::RoundRobinArbiter`:

- Stable ordered predecessor list.
- Cursor points to the next preferred source.
- Skip sources without an eligible request.
- Advance only on a successful grant.
- Store cursor in initial state, snapshots, and resume checkpoints.

The selected target station never changes. At its divert, full-buffer policy blocks onward loop travel; no recirculation. Freeze the precise branch-buffer admission rule at H0, including whether the check uses projected end-of-tick buffer occupancy.

### Picker and packer blocking

`PickerController` follows:

```text
IDLE → TRAVEL/PICK → TRAVEL_HOME → HANDOFF
     → BLOCKED_INDUCTION → IDLE
```

- Allocate actor, tote, and whole-order reservations atomically.
- `handoff_ready` creates a persistent admission request.
- Assign target pack station before induction, using minimum reserved WIP and stable pack ID.
- Increment station reservation exactly once when the target is fixed.
- Release picker only when feed admission commits.

`PackStationController` follows:

```text
IDLE → PACK → BLOCKED_OUTPUT → IDLE
```

- Buffer capacity four excludes the item in service.
- At pack completion: transfer contents to parcel, release tote, retain actor/station and reserved WIP.
- At outfeed acceptance: release station reservation and allow the next PACK in phase 3.

### Pallets and D8

`Palletizer` states:

```text
OPEN → SEAL_PENDING → SEALED → CLAIMED/IN_TRANSIT → DISPATCHED
```

Maintain:

```text
placed_count + reserved_slots ≤ 10
```

`reserve_scan_slot()` atomically reserves both the parcel and a pallet slot before scan begins.

- First completed placement starts the 300-second age timer.
- Filling the last available reservation prevents further reservations.
- Timeout marks `SEAL_PENDING`.
- Existing reservations remain valid and must finish.
- Seal requires `reserved_slots == 0` and space in the sealed queue.
- `seal_once()` freezes parcel membership and creates one deterministic forklift task.
- Timer generation IDs make obsolete timeout callbacks harmless.
- Drain does not flush a partial pallet early.

D8 execution:

```text
296: scan starts; reservation belongs to pallet A
300: expiry → A becomes SEAL_PENDING
300: no new reservation can target A
304 phase 0: scan placement completes; outstanding reservation becomes zero
304 phase 3: seal A, create one task, assign forklift if available
```

### Forklift tasks

`ForkliftController` executes:

```text
EMPTY_TRAVEL → PICKUP → LOADED_TRAVEL → DROP → RETURN_HOME
```

Each task references one vehicle, one driver, one cargo, and an allowed graph. Driver and vehicle share trajectory timestamps.

Outbound fixture:

```text
seal432 → arrive435 → pickup450 → dock454 → dispatch469 → home474
```

Dispatch occurs at completed dock transfer, not at seal, forklift assignment, or return.

Inbound tasks reserve a destination staging position before collecting cargo. Full reserve staging prevents additional putaway assignments and propagates blocking to receiving.

## 4. Snapshots, chunks, seek, and recovery

Separate **replay snapshots** from **engine restart checkpoints**. They share state serialization but have different operational purposes.

`checkpoint.py::EngineCheckpoint` contains:

- Immutable input references/hashes and engine/timebase versions.
- Actors: state, position, current action, action start, ready time, route cursor.
- Active orders: stage, assigned resources, remaining picks, reservations.
- Inventory balances and claims.
- Cargo contents/locations/parent relationships.
- Cell occupancy, entry/ready times, pending admissions.
- FIFO queues and service occupants.
- Tote pool.
- Station reserved WIP.
- Merge cursors.
- Open/sealed pallets, slot reservations, expiry ticks, timer generations.
- Forklift tasks and task progress.
- Metrics accumulators and last integration timestamps.
- Pending event descriptors with `schedule_seq`.
- Next scheduler/event/action counters.
- Export journal offsets and last committed event cursor.

No pickle of SimPy environments, generators, closures, or `Resource` objects.

`SimulationEngine.restore(checkpoint)`:

1. Verify versions and hashes.
2. Reconstruct plain state.
3. Create a new SimPy environment at checkpoint time.
4. Recreate pending `PhaseEvent`s in saved scheduling order.
5. Resume open actions from their original starts.
6. Resume export after the checkpoint cursor without duplicating committed records.

Because the engine uses explicit state machines, there are no indispensable suspended generator locals. Any wrapper process is disposable and reconstructible.

**Replay snapshots**

`exporter/snapshots.py::build_snapshot()` runs after phase 3 at 0, 30, 60, … seconds and at final termination. Initial pre-event state is separate from the post-phase snapshot at t=0.

Snapshots reference immutable layout/catalog/order definitions. They store mutable state and compact status vectors, not repeated order histories.

**Chunks**

`chunks.py::ChunkWriter` uses:

```text
[k×60, (k+1)×60)
```

- Events exactly at 60 s belong to the next chunk.
- Same-timestamp atomic transactions cannot be split.
- A terminal event exactly on a boundary still needs an owning chunk.
- Index contains time bounds, cursor bounds, count, byte size, and SHA-256.
- Actions crossing chunks have one identity and immutable interval; overlapping chunks may carry deduplicated references.
- A snapshot includes active action references so a seek does not need all earlier chunks.

**Pure replay**

```python
seek(snapshot, transactions, target_tick) -> ReplayState
```

`replay/reducer.py::apply_transaction()` applies exported state changes. It does not call SimPy, regenerate arrivals, run a planner, or make resource decisions.

Algorithm:

1. Select latest snapshot at or before target.
2. Start strictly after its saved event cursor.
3. Apply transactions through target.
4. Derive positions from supplied intervals and waypoints.
5. Clamp completed runs to final state.

Atomic cell batches are authoritative. Logical `cell_exited`/`cell_entered` pairs are views of the same committed transfer, not independent debit/credit mutations. This prevents intermediate cargo disappearance or double occupancy during replay.

The Python reducer is Arman’s executable contract oracle. Tilek implements its semantics in his frontend; Arman supplies seek/reset/boundary input-output fixtures.

## 5. Required modules and algorithms

| Module | Responsibilities and concrete algorithms |
|---|---|
| `data/scenario_materializer.py::materialize()` | Persist catalog, history, orders, receipts, generator recipe, and hashes before any simulation. Use `Generator(PCG64)` with named independent streams. Freeze a derivation such as `SeedSequence([20261107, stream_code])` for history/orders/receipts; record codes and generator version. |
| `data/history.py::generate_history()` | 56 calendar days; 1,920 weekday orders and 1,344 weekend orders. With eight complete weeks this is 98,304 historical orders. Each order draws 2/3/4 distinct SKU uniformly in count, weighted without replacement by rank^-0.9; quantities 1–4. |
| Materialized scenarios | Exactly 240/600 orders per hour and 1,920/4,800 per eight hours. Global midpoint arrivals, not a Poisson process. Receipts: `(i+0.5)×180`, 500 units, cyclic DEMO SKU. Promotion multiplies DEMO_173’s generation weight by five before normalization. |
| `forecast/features.py::build_features()` | Sort by SKU/date; lags 1/7/14/28; shifted rolling means 7/28; day-of-week; deterministic SKU one-hot. No lag2/month copied accidentally from v1. Reject targets lacking the full 28-day history. |
| `forecast/mean28.py::predict()` | Mean of previous 28 calendar days for each SKU; zero-filled days only because this synthetic generator defines the full calendar. |
| `forecast/hgb.py::fit_predict()` | Global Poisson HGB: 150 iterations, 15 leaves, learning rate .06, L2=1, random_state=42. Dense one-hot; `early_stopping=False` to prevent implicit random validation. Explicit CPU thread cap. Validate nonnegative targets and finite predictions. Poisson requires nonnegative targets with positive total; handle an all-zero training set explicitly. [HGB documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html) |
| `forecast/evaluation.py::temporal_evaluate()` | First 42 days train, next 14 validation. With lag28, eligible training targets are days29–42: 2,800 rows; validation has 2,800 rows. Fit once for validation; each validation date may use only previously observed days. Final fit on past56 gives 5,600 eligible rows. Test stream never enters training or plan selection. |
| Forecast reporting | `WAPE = sum(abs(pred-actual))/sum(actual)`; zero denominator → null. Also MAE, bias, per-SKU errors, fit/predict CPU time, cutoff, feature schema, environment fingerprint. HGB must produce an actual planner input before release; preserve mean28 comparison regardless of which wins. |
| Forecast-to-horizon | `scale_to_offered_load()` explicitly converts daily visits to the requested run horizon. Proposed rule: preserve predicted SKU shares and scale to known `E[lines/order]×N = 3N`. Compare shortlist changes against the baseline scaled to the same horizon. Promotion adjustment is a declared intervention, not learned uplift. |
| `navigation/shortest_paths.py::AllPairsPaths` | Run Dijkstra from all184 nodes; cache distance and canonical predecessor/next-hop matrices by layout hash. Sorted adjacency and deterministic equal-distance path tie-break. Distances in exact half-metre units for this geometry. Cache forklift graphs separately. |
| `navigation/picking_routes.py::nearest_neighbour()` | Unique SKU stops; select `(distance, sku_id)` minimum; expand each leg through graph edges; return to actor’s fixed home. Same service node may host L/R SKU: zero travel between them, distinct PICK services. |
| `planning/abc.py::build_frozen_abc()` | Rank SKU by visits over the frozen42-day training period, descending then SKU ID. Rank288 faces by `(mean round-trip from three homes, slot_id)`; assign first200. Preserve reserve placement independently. |
| `planning/surrogate.py::evaluate()` | `J = Σ forecast_visits×mean_home_roundtrip/walk_speed + relocation_labor`. Report as expected labor surrogate, not throughput or realized savings. |
| `planning/greedy.py::generate_plans()` | Budgets0/2/8. Fixed shortlist≤32 by absolute forecast-load change against comparable train baseline; tie SKU. Evaluate≤496 pairs, choose highest strictly positive net gain, stable pair tie-break, exclude touched SKU, repeat. No moves into empty faces under this swap contract. |
| `planning/relocation.py::price_swap()` | Evaluate both orientations of `I02→A→buffer→B→A→buffer→B→I02`; cost is graph travel/1.2 + six×8 s. Each swap returns home, matching the supplied probe’s costing convention. |
| `inventory/relocation.py::execute_plan()` | Three transfers: A→buffer, B→A, buffer→B. Move whole lots with SKU; reserve unchanged. Pre-shift transaction journal is separate from nonnegative shift actions. Buffer empty before/after. |
| `inventory` | Whole-order admission against active stock, reservations, pick transfers, pack conversion, receipt entry, dispatch, conservation. No implicit reserve picking or replenishment. |
| `workforce` | Registry for all24 humans; fixed homes, FIFO eligible orders, stable actor allocation, tote waiting, nonoverlapping half-open actions. Productive labor is only TRAVEL+BUSY_SERVICE. |
| `conveyor` | Compiled cell graph, one-hop atomic updates, persistent source requests, finite capacity, RR merges, immutable targets, backpressure. |
| `packing` | Six stations, one packer each, four waiting positions, service `20+2×lines+.05×units`, tote release at completion, blocked output until actual admission. |
| `receiving` | External waiting receipts, boundary admission, two90-second receivers, processed pallets, inbound forklift tasks,40 staging positions. Accepted receipts enter the ledger on boundary crossing. |
| `shipping` |40-parcel waiting buffer, two8-second scanners, atomic pallet slot reservation, full/age sealing, finite8-pallet sealed queue, outbound forklift tasks, dock dispatch. |
| `metrics` | Incremental exact-duration integrals, stage counts, labor, blocked time, backlog, cycle distributions, occupancy, jam spans, tote availability, stock summaries. |
| `exporter` | Typed event payloads, action validation, compact atomic transfers, snapshots, chunks, checksums, manifest, inline-v2 projection, reference replay equivalence. |

**Metrics semantics**

- Keep shift totals over `[0,H)` separate from eventual totals after drain.
- Integrate queue length before every change; divide area by H.
- Queue excludes active service. Queue maxima are sampled after instantaneous dispatch has settled.
- Labor/utilization clips actions to `[0,H)` and divides by `role_count×H`.
- Report active utilization and unavailable utilization separately.
- P95 uses NumPy `quantile(method="linear")` over completed cycles; report completion rate and unfinished ages beside it.
- `backlog_at_H = arrived_before_H - dispatched_before_H`, including inventory refusals.
- Net active labor saving subtracts relocation exactly once.
- A timestamp at H can affect post-H state but must not enter shift throughput.
- Stop after all real work drains, or identify terminal refusal/deadlock/cap. Periodic ticks/snapshots alone are not useful future work.
- Preserve partial receiving status even if every order dispatched. Order makespan and subsystem completion are distinct.

## 6. API, contracts, hashing, and artifact storage

### Contract completion

The supplied `run.schema.json` is too restrictive for all prose requirements: it lacks several versions/hashes, vehicles, detailed termination information, and some metrics. It also leaves event payloads and snapshot state effectively untyped.

At H0, define a **versioned run-bundle envelope** with:

- Existing v2 inline run as a compatible logical projection.
- Typed manifest metadata and complete input fingerprint.
- Typed snapshot/event payload schemas.
- Exact clock metadata.
- Chunk index and encoding version.
- Expanded metrics and subsystem termination details.
- Actor/vehicle registry and immutable catalog references.

Keep `schema_version="2.0"` truthful for the existing logical projection; give the new transport envelope its own version. Do not add forbidden fields to the current schema and still claim it validates. Shared contract changes are a handoff to Tilek, not frontend work.

### Endpoints

| Endpoint | Contract |
|---|---|
| `GET /api/catalog` | Profiles, compatible layouts/configs, provenance, supported models, policy versions and parameter bounds |
| `POST /api/scenarios/materialize` | Validated recipe → immutable scenario reference;202 if queued,200 if already present |
| `POST /api/forecast` | History/cutoff/model references → forecast and temporal evaluation |
| `POST /api/plans` | Forecast/assignment/config/horizon references →0/2/8 candidate plans and selected decision |
| `POST /api/compare` | Experiment type, scenario, selected plan → comparison job, baseline/candidate run IDs |
| `GET /api/jobs/{id}` | Queued/running/succeeded/failed/cancelled, progress, result references |
| `DELETE /api/jobs/{id}` | Request cancellation at a safe checkpoint; job cancellation does not invent a completed run |
| `GET /api/runs/{id}/manifest` | Immutable metadata and artifact index |
| `GET /api/runs/{id}/chunks?from_s=…&to_s=…` | Bounded chunk window, including boundary/action dependencies |
| `GET /api/runs/{id}/chunks/{chunk_id}` | Immutable chunk; ETag/content hash |
| `GET /api/runs/{id}/snapshots?at_or_before_s=…` | Nearest replay checkpoint |
| `GET /api/runs/{id}/metrics` | Shift, drain, stage, resource, and inventory summaries |
| `GET /health/live`, `/health/ready` | Process health; storage/worker/schema readiness |

CPU work runs in spawned worker processes, not inside an async request handler or FastAPI `BackgroundTasks`. Default concurrency is one simulation worker on the demo laptop; bounded configurable concurrency for deployment.

Use durable SQLite job metadata on the same host. Transactional claim/lease, heartbeat, attempt count, and idempotent result publication survive API restarts.

### Error envelope

```json
{
  "error": {
    "code": "INVALID_REFERENCE",
    "message": "Order ORD_004 references an unknown SKU.",
    "request_id": "request-identifier",
    "details": [
      {
        "path": ["orders", 3, "lines", 0, "sku_id"],
        "code": "unknown_sku",
        "value": "DEMO_999"
      }
    ]
  }
}
```

422 conditions:

- Unknown SKU/slot/node/actor/station/cargo references inside submitted inputs.
- Duplicate IDs, duplicate SKU lines, empty order lines, nonpositive/noninteger quantities.
- NaN/Infinity, negative times, arrival outside `[0,H)`, invalid duration/capacity.
- Unsupported schema/layout/policy versions or v1 input without explicit adapter.
- Invalid graph weights, rack-crossing edges, inaccessible active slots, upper-slot walking access.
- Inconsistent segment length/cell count/port geometry.
- Noninjective active assignment, wrong lot quantities/locations, wrong stock totals.
- Staffing/actor/vehicle mismatch.
- Unsupported ring pool, inconsistent speed/tick/cell length.
- Forecast cutoff leakage or incompatible forecast/plan/scenario references.
- Slotting comparison changing resources, orders, receipts, stock quantities, routing, or failure schedule.
- Time parameters not representable under the bounded exact-clock policy.

Use404 for a nonexistent resource addressed directly by URL,409 for incompatible resource state,429/503 for capacity limits, and500 for internal failures. Do not expose stack traces or silently repair inputs.

### Run identity

`storage/canonical_json.py::canonicalize()` defines a versioned canonicalization:

- UTF-8; sorted object keys.
- Normalized decimal representation; reject nonfinite values.
- Canonical ordering for set-like records by IDs.
- Preserve semantically ordered arrays such as routes and FIFO arrivals.
- Explicit defaults included.
- No wall time, request ID, absolute path, or runtime duration.

```text
run_id = sha256(canonical_json({
  canonicalization_version,
  engine_version,
  dependency_lock_fingerprint,
  timebase_policy,
  layout_hash,
  config_hash,
  actors_hash,
  scenario_hash,
  orders_hash,
  receipts_hash,
  initial_stock_by_sku_lot_hash,
  assignment_hash,
  relocation_plan_hash,
  forecast_snapshot_hash,
  operations_hash,
  routing_policy_hash,
  failure_schedule_hash,
  experiment_type
}))
```

Separate assignment-independent stock quantities from lot placements. Otherwise a valid swap changes `initial_inventory` and accidentally fails the A/B equality check.

A no-op from different forecast provenance may have a different run identity while retaining identical substantive simulation events and metrics.

### Disk layout and reliability

```text
ARTIFACT_ROOT/
├── objects/sha256/<prefix>/<digest>
├── scenarios/<scenario_id>/manifest.json
├── forecasts/<forecast_id>/manifest.json
├── plans/<plan_id>/manifest.json
├── comparisons/<comparison_id>/manifest.json
├── runs/<run_id>/
│   ├── manifest.json
│   ├── initial-state.json
│   ├── metrics.json
│   ├── chunks/000000.json
│   ├── snapshots/000000.json
│   └── verification.json
├── work/<job_id>/<attempt>/
└── jobs.sqlite3
```

- Write temporary artifacts, flush, validate, hash, then atomically publish manifest last.
- Existing digest with different bytes is corruption, never overwrite.
- Use only validated digest IDs in paths; reject traversal.
- Serve immutable artifacts with ETags and compression.
- Recover interrupted jobs from checkpoints or deterministic restart; never publish incomplete chunks as complete.
- Retention/GC deletes only unreferenced artifacts under the configured root.
- Structured logs include request/job/run IDs, engine version, simulation time, phase, and exception category.
- Expose queue depth, worker RSS, wall/CPU time, artifact bytes, and invariant-failure counters.
- Default local binding is loopback. Remote mode requires configured authentication, CORS allowlist, request-size limits, and job quotas.
- Backups include immutable objects plus job metadata; test restore and corruption detection.

## 7. Complete acceptance-test matrix

Paths below are relative to `backend/tests/`. Each test records input identity, expected value, actual value, and status. UI-dependent items have a backend conformance test plus a separate joint acceptance requirement.

### Geometry and picking

| ID | Test |
|---|---|
| G1 | `acceptance/test_geometry.py::test_G1_graph_counts_reachability_and_reserve_access` |
| G2 | `acceptance/test_geometry.py::test_G2_home_to_first_bay_is_four_metres` |
| G3 | `acceptance/test_geometry.py::test_G3_adjacent_aisle_requires_eight_point_five_metres` |
| G4 | `acceptance/test_geometry.py::test_G4_two_sku_round_trip_is_twenty_one_metres` |
| S1 | `acceptance/test_picking.py::test_S1_handoff_ready_at_32_8` |
| S2 | `acceptance/test_picking.py::test_S2_admission_33_release_33_first_hop_34` |
| S3 | `acceptance/test_picking.py::test_S3_quantity_100_is_one_stop_and_21_seconds` |
| S4 | `acceptance/test_picking.py::test_S4_stable_actor_order_unique_resources_nonoverlap` |
| S5 | `acceptance/test_picking.py::test_S5_full_feed_retains_picker_and_tote` |

### Full fixture timeline

All tests use `acceptance/test_analytical_timeline.py`; compute the run once using a session fixture, but compare against independent constants from the analytical fixture.

| Time | Test and assertion |
|---|---|
|32.8 | `test_handoff_ready_32_8`: route21 m, walk17.5, pick12.3, handoff3 |
|33 | `test_induction_and_picker_release_33`: blocked induction duration.2 |
|34 | `test_first_conveyor_hop_34` |
|52 | `test_pack_buffer_arrival_and_pack_start_52`: transport19 seconds |
|76.1 | `test_pack_completion_and_single_tote_release_76_1` |
|77 | `test_outfeed_acceptance_and_station_release_77`: blocked output.9 |
|124 | `test_shipping_arrival_and_scan_start_124`: transport47 seconds |
|132 | `test_first_placement_and_age_timer_start_132` |
|432 | `test_seal_and_single_forklift_task_432` |
|435 | `test_forklift_arrival_and_pickup_start_435` |
|450 | `test_pickup_complete_and_loaded_departure_450` |
|454 | `test_dock_arrival_and_loading_start_454` |
|469 | `test_dispatch_and_order_cycle_469` |
|474 | `test_forklift_home_and_available_474` |

### Conveyor

| ID | Test |
|---|---|
| C1 | `acceptance/test_conveyor.py::test_C1_one_hop_per_tick_and_exit_at_three` |
| C2 | `acceptance/test_conveyor.py::test_C2_occupied_entry_preserves_pending_request` |
| C3 | `acceptance/test_conveyor.py::test_C3_downstream_release_propagates_without_double_hop` |
| C4 | `acceptance/test_conveyor.py::test_C4_round_robin_grants_1212_deterministically` |
| C5 | `acceptance/test_conveyor.py::test_C5_checkpoint_preserves_next_merge_grant` |
| C6 | `acceptance/test_conveyor.py::test_C6_full_target_buffer_blocks_divert_and_loop` |
| C7 | `acceptance/test_conveyor.py::test_C7_unblocking_preserves_tick_semantics` |
| C8 | `acceptance/test_conveyor.py::test_C8_tote_returns_once_without_reverse_belt` |

Additional: `test_all_eighteen_induction_pack_routes`, `test_target_uses_in_transit_and_blocked_reserved_wip`, `test_target_never_changes`, `test_ring_occupancy_below_112`.

### Packing and labor

| ID | Test |
|---|---|
| K1 | `acceptance/test_packing.py::test_K1_six_parallel_packs_then_seventh_and_wait_integral` |
| K2 | `acceptance/test_packing.py::test_K2_four_waiting_excludes_service` |
| K3 | `acceptance/test_packing.py::test_K3_output_block_holds_station_until_15` |
| K4 | `acceptance/test_packing.py::test_K4_tote_released_10_reservation_released_15` |
| K5 | `acceptance/test_labor.py::test_K5_actions_are_clipped_to_shift_horizon` |
| K6 | `acceptance/test_labor.py::test_K6_role_denominator_and_active_state_classification` |

### Inventory

| ID | Test |
|---|---|
| I1 | `acceptance/test_inventory.py::test_I1_competing_orders_cannot_overreserve` |
| I2 | `acceptance/test_inventory.py::test_I2_reservation_does_not_add_physical_stock` |
| I3 | `acceptance/test_inventory.py::test_I3_pick_moves_reserved_units_into_tote` |
| I4 | `acceptance/test_inventory.py::test_I4_missing_line_rolls_back_whole_reservation` |
| I5 | `acceptance/test_inventory.py::test_I5_initial_plus_receipts_equals_stock_plus_dispatch` |
| I6 | `acceptance/test_inventory.py::test_I6_external_receipt_is_not_accepted_inventory` |
| I7 | `acceptance/test_inventory.py::test_I7_ground_reserve_cannot_supply_active_pickface` |
| I8 | `acceptance/test_inventory.py::test_I8_pack_reset_seek_preserve_units` |
| I9 | `acceptance/test_inventory.py::test_I9_swap_moves_lots_preserves_reserve_and_empties_buffer` |

### Receiving and shipping

| ID | Test |
|---|---|
| R1 | `acceptance/test_receiving.py::test_R1_full_receiving_and_reserve_hold_receipts_outside` |
| R2 | `acceptance/test_receiving.py::test_R2_processed_receipt_has_cargo_service_and_putaway_task` |
| R3 | `acceptance/test_receiving.py::test_R3_putaway_only_changes_ground_reserve` |
| D1 | `acceptance/test_shipping.py::test_D1_two_shippers_compete_atomically_for_last_slot` |
| D2 | `acceptance/test_shipping.py::test_D2_full_pallet_seals_54_and_stale_timer_is_inert` |
| D3 | `acceptance/test_shipping.py::test_D3_three_parcels_seal_at_300` |
| D4 | `acceptance/test_shipping.py::test_D4_drain_preserves_age_timer_without_empty_or_early_seal` |
| D5 | `acceptance/test_shipping.py::test_D5_shipping_capacity_40_backpressures_outbound` |
| D6 | `acceptance/test_shipping.py::test_D6_packed_10_is_not_completed_until_dispatch_100` |
| D7 | `acceptance/test_shipping.py::test_D7_dispatch_once_before_forklift_return` |
| D8 | `acceptance/test_shipping.py::test_D8_timeout_300_waits_for_reserved_scan_until_304` |

Additional: `test_sealed_queue_capacity_eight_blocks_seal`, `test_driver_vehicle_trajectories_match`, `test_inbound_transit_remains_in_ledger`.

### Termination and planning

| ID | Test |
|---|---|
| T1 | `acceptance/test_termination.py::test_T1_empty_run_has_zero_counts_and_null_undefined_metrics` |
| T2 | `acceptance/test_termination.py::test_T2_late_dispatch_does_not_rewrite_horizon_backlog` |
| T3 | `acceptance/test_termination.py::test_T3_terminal_stockout_returns_partial_without_wait_loop` |
| T4 | `acceptance/test_termination.py::test_T4_deadlock_or_drain_cap_preserves_remaining_locations` |
| T5 | `acceptance/test_metrics.py::test_T5_linear_p95_completion_rate_and_unfinished_age` |
| T6 | `acceptance/test_termination.py::test_T6_peak_keeps_all_600_arrivals_despite_backlog` |
| P1 | `acceptance/test_planning.py::test_P1_noop_preserves_assignment_lots_events_and_metrics` |
| P2 | `acceptance/test_planning.py::test_P2_swap_has_three_transfers_and_six_handling_actions` |
| P3 | `acceptance/test_planning.py::test_P3_budgets_two_eight_use_disjoint_ground_pairs` |
| P4 | `acceptance/test_planning.py::test_P4_unprofitable_swap_selects_noop` |
| P5 | `acceptance/test_planning.py::test_P5_relocation_uses_edges_and_cheaper_orientation` |
| P6 | `acceptance/test_planning.py::test_P6_negative_test_effect_is_preserved_without_reselection` |

### Hash/replay criteria 1–10

| ID | Test and ownership boundary |
|---|---|
| HR1 | `acceptance/test_hash_replay.py::test_HR1_semantic_inputs_and_engine_determine_run_id` |
| HR2 | `acceptance/test_hash_replay.py::test_HR2_phase_sequence_and_half_open_boundaries` |
| HR3 | `acceptance/test_hash_replay.py::test_HR3_snapshot_contains_complete_mutable_state` |
| HR4 | `acceptance/test_hash_replay.py::test_HR4_seek_10_80_20_80_matches_continuous_state` |
| HR5 | `acceptance/test_hash_replay.py::test_HR5_chunk_snapshot_boundaries_apply_each_transaction_once` |
| HR6 | `acceptance/test_replay_boundary.py::test_HR6_sampling_rate_and_paused_clock_do_not_change_state_or_kpi`; actual UI pause is joint acceptance |
| HR7 | `acceptance/test_replay_boundary.py::test_HR7_pick_handoff_and_blocked_intervals_are_stationary`; rendered behavior is Tilek’s check |
| HR8 | `acceptance/test_replay_boundary.py::test_HR8_ab_states_share_requested_time_and_finished_run_clamps`; camera/selection preservation is frontend acceptance |
| HR9 | `acceptance/test_hash_replay.py::test_HR9_reset_restores_initial_state_without_stale_counters` |
| HR10 | `acceptance/test_contract_boundary.py::test_HR10_incompatible_schema_layout_and_v1_are_rejected` |

Backend tests cannot certify browser FPS, camera state, or visual positioning. They produce the exact fixtures needed for joint verification without pretending to cover Tilek’s implementation.

### Property, integration, and operational tests

| File/test | Property |
|---|---|
| `properties/test_ledger_state_machine.py::TestLedgerMachine` | Conservation after every committed event; nonnegative stock; reservation≤on_hand; rejected transaction leaves identical state |
| `properties/test_conveyor.py::test_unique_cell_and_cargo_occupancy` | No double occupancy, cargo loss, overtaking on a single lane, or second hop |
| `properties/test_actions.py::test_actor_actions_never_overlap` | Half-open actions, positive durations, continuous graph travel |
| `properties/test_determinism.py::test_two_runs_have_identical_semantic_artifacts` | Same materialized inputs yield identical events, snapshots, metrics; vary process hash seed |
| `properties/test_totes.py::test_pool_partition_is_always_96` | Allocation/release partition invariant |
| `properties/test_pallets.py::test_sealed_membership_never_changes` | No overreservation, late insertion, duplicate seal/task/dispatch |
| `properties/test_replay.py::test_arbitrary_seek_matches_event_prefix` | Random forward/backward seeks equal reference reduction |
| `properties/test_checkpoint.py::test_resume_matches_uninterrupted_run` | Resume at arbitrary safe checkpoints preserves output |
| `integration/test_scenarios.py::test_normal_peak_hour_and_shift_counts` |240/600/1920/4800 orders;20/160 scheduled receipts |
| `integration/test_forecast.py::test_future_perturbation_cannot_change_prior_forecast` | Leakage prevention |
| `integration/test_forecast.py::test_hgb_predictions_feed_selected_plan` | Actual ML-to-planner wiring |
| `integration/test_api.py::test_validation_idempotency_and_job_lifecycle` | Errors, repeated requests, polling, cancellation |
| `integration/test_storage.py::test_crash_before_manifest_publish_is_recoverable` | Atomic publication and restart |
| `integration/test_storage.py::test_corrupt_chunk_is_rejected` | Hash verification |
| `integration/test_comparison.py::test_slotting_rejects_changed_resource_hashes` | Experiment integrity |
| `performance/test_peak_shift.py::test_peak_shift_resource_budget` | Runtime, RSS, artifact size, event counts |

## 8. Build order and gates aligned with H0–H48

The 48-hour document budgets approximately26 individual hours for Arman. That is an integration schedule, not a credible guarantee of complete startup-grade hardening. Preserve its checkpoints, but do not declare production readiness until the release gates below pass.

| Window | Backend work | Runnable artifact and gate |
|---|---|---|
| H0–H1 | Dependency lock, schema ownership, time grid, phase ordering, capacity semantics, bundle contract | `validate-contracts` emits a contract report; unresolved decisions documented and frozen |
| H1–H4 — B1 | Typed layout/actors/config, all-pairs paths, cell topology, fixture builder | Geometry CLI passes G1–G4 and exports fixture inputs on full geometry |
| H4–H8 — B3/B4 vertical slice | SimPy adapter, picker, ledger, basic conveyor/pack/outbound, full single-order path | Executable fixture reaches469 dispatch/474 home; initial inline export for Tilek |
| H8–H16 — B2/B4/B5 | All24 actors, finite buffers, merges, blocking, receiving, pallet races, forklifts, checkpoints | Saturated short run with real role tasks; C/K/I/R/D suites; first30-second snapshots and60-second chunks |
| H16–H24 — B6/B7 | Materialized normal/peak, mean28, frozen ABC, greedy plans, relocation, comparison/API | One-hour baseline/candidate artifacts with matching inputs and measured metrics; no-op supported |
| H24 | Scope review | Freeze feature additions; retain full requested APIs/seek as release requirements even if demonstration uses saved artifacts |
| H24–H34 — B6/B8 | HGB wiring/evaluation, eight-hour runs, property tests, replay/resume equivalence | Normal/peak shift reports, forecast comparison, deterministic reruns, performance measurements |
| H34–H42 — B7/B8 | Durable jobs/storage, errors, packaging, startup docs, artifact verification | Clean-environment launch; verified immutable run bundle and acceptance report |
| H42–H46 | Cold-start/offline rehearsals, recovery checks | Two successful offline starts and artifact replays; no external runtime dependencies |
| H46–H48 | Defect reserve | Release candidate or explicit failed gates; no new algorithms |

**Release hardening gate after H48 if unfinished:** allocate a separate engineering allowance, initially5–10 working days, re-estimated from H24 evidence. Complete API concurrency/idempotency, restart recovery, authentication deployment mode, storage fault injection, Windows/Linux compatibility, coverage, payload budgets, and sustained-run testing.

“Done” requires:

- Every backend acceptance ID passes.
- All integration and property suites pass.
- Coverage gates pass.
- Eight-hour normal/peak calculations actually run.
- No unresolved ledger, scheduler, or pallet race defects.
- Clean install and offline execution work.
- Tilek receives versioned conformance artifacts.
- Performance results are measured and recorded.
- Any remaining frontend-only acceptance remains explicitly joint, not falsely marked backend pass.

## 9. Top 15 specification traps and resolutions

| # | Finding | Resolution |
|---|---|---|
|1 | `run.schema.json` forbids fields required by §11, including richer versions/hashes/metrics; event and snapshot payloads are untyped | Versioned bundle envelope and strict payload models; preserve a schema-valid v2 projection |
|2 | Current extracted workspace lacks referenced `contracts/README.md`, legacy directory, data artifacts, and requirements files; README exists as `contracts_README.md` | Use supplied files as current inputs; record absent assets. Do not treat package-manifest listings as available files |
|3 | `validate_spec_v2.py` writes `verification_report.json` and requires missing legacy files; it checks prepared materials, not runtime | Extract equivalent pure validation functions into backend tests. Do not use its report as simulator acceptance |
|4 | v1 forecast uses lag2/month, weekday targets,20 SKU, and different geometry; v2 specifies a different feature/calendar protocol | Carry over only stated HGB hyperparameters. Implement v2 feature/split rules explicitly |
|5 | Master seed is specified, but concrete independent stream seeds/derivation are not | Freeze named stream derivation, sampling order, NumPy version, and generator version before materialization |
|6 | Forecasts are daily while simulation horizons/load vary; raw daily counts can misprice relocation or distort shortlist changes | Define horizon scaling and promotion adjustment before evaluation; normalize forecast and train comparator to the same horizon |
|7 | Binary floating-point travel times can cross integer conveyor boundaries | Exact rational compilation to integer SimPy ticks; tolerance only for external numeric assertions |
|8 | Tick processing over an in-place cell array can give multiple hops or overwrite cargo; loop is cyclic | Pre-state planning, vacancy worklist, RR arbitration, atomic batch commit, separate admissions |
|9 | Full pack buffer versus two physical branch cells lacks a fully explicit admission rule | Freeze one rule at H0. Recommended: a tote at its divert cannot enter while projected destination buffer is full; already diverted totes retain their finite branch positions |
|10 | Receiving “queue8” conflicts with ambiguous treatment of service/processed pallets; an unbounded ready-pallet list would defeat backpressure | Explicitly define eight physical receiving positions shared by waiting/service/processed pallets; queue KPI excludes service. This is a proposed clarification, not an existing unambiguous rule |
|11 | Tote release and station release occur at different times | Release tote at `order_packed`; retain station WIP and packer until `parcel_outfed` |
|12 | Pallet timer can expire while a scan owns a reserved slot; full sealed queue adds another race | `SEAL_PENDING`, immutable reservation ownership, generation-tagged timers, seal only after outstanding placements and queue availability |
|13 | “Run complete” and “all orders dispatched” differ because reserve staging eventually blocks receiving | Track subsystem termination separately. A partial run may have all orders dispatched; do not invent missing order failures or erase inbound backlog |
|14 | A/B requires equal initial inventory hashes, but relocation changes lot locations | Hash stock quantities/lot identities separately from assignment-dependent placement. Move lots with SKU and charge relocation once |
|15 |48-hour cuts allow reduced API/seek, but this request requires a complete backend; supplied timings are unimplemented expectations | Treat H48 as a gated release candidate. Do not remove required capabilities from the final plan or label expected results as measured |

Additional numeric conclusions:

-179 cells is correct:112+3+12+6+46.
-600 occupied slots is correct:200 active+400 reserve;264 empty.
-600,000 units is correct:200×(2,000+500+500).
-40 reserve staging positions with20 receipts/hour necessarily create inbound blocking during an eight-hour run without replenishment.
-The fixture’s469-second order cycle excludes the final5-second forklift return.
-32 shortlisted SKU give496 unordered pairs; “up to8 swaps” touches at most16 SKU.
-The analytical fixture is a special two-SKU scenario on full geometry; production200-SKU validation must not reject it when `experiment_type="fixture"` is explicit.

## 10. Performance budget and safe optimization

**Workload**

```text
Peak orders:               600 × 8 = 4,800
Expected order lines:      4,800 × 3 = 14,400
Expected units:            14,400 × 2.5 = 36,000
Scheduled receipts:        20 × 8 = 160
Maximum simulated span:    28,800 + 7,200 = 36,000 s
Dense conveyor cell checks: 179 × 36,000 = 6,444,000
```

There can be an additional initialization/final boundary tick depending on interval convention; document it rather than obscuring an off-by-one.

The raw conveyor workload is modest. Millions of Python objects, repeated Pydantic validation, full-state snapshots, and JSON output are more likely bottlenecks than6.44 million indexed cell checks.

**Transport volume estimate**

For an unobstructed order, induction-to-pack distance ranges19–85 m; pack-to-shipping ranges17–47 m.

Because both legs depend on the same pack station, their combined distance simplifies to:

```text
induction_x + 56 metres = 66 / 84 / 102 metres
```

Thus4,800 completed orders generate approximately317,000–490,000 conveyor boundary transfers, plus admissions and non-conveyor events. Blocked ticks add time but not movement records. Actual counts depend on admissions, stockouts, and completion.

Expanded paired cell events can approach one million records. Naïve JSON can therefore exceed the one-hour30 MB target even when engine runtime is acceptable.

**Proposed engineering budgets — to measure**

Reference: ordinary4-core laptop,16 GB RAM, one worker, warm dependencies.

| Operation | Initial budget |
|---|---:|
| Compile layout/all-pairs cache |≤1 s |
| Materialize56-day history plus shift |≤10 s |
| HGB fit/evaluate/predict |≤30 s |
|0/2/8 planning |≤1 s |
| One peak eight-hour run including export |≤60 s |
| Baseline/candidate comparison |≤120 s |
| Worker peak RSS |≤512 MiB |
| API cached metadata p95 |≤100 ms |
| Replay seek over snapshot+≤30 s events |≤100 ms in Python reference harness |
| One-hour raw logical transport bundle |≤30 MB target |
| Contractual client event window |≤64 MB; browser heap measurement remains Tilek’s responsibility |

These are release targets, not performance claims. Record hardware, dependency lock, scenario/run IDs, CPU/wall time, RSS, transfer count, snapshot count, and raw/compressed bytes.

**Optimization order**

1. **Compile IDs to integer indices.** Use fixed arrays for179 cells and200 SKU totals; retain string dictionaries for export.
2. **Keep Pydantic at boundaries.** Runtime uses dataclasses, integer arrays, and typed commands.
3. **Cache paths and relocation prices.**184² distance entries are only33,856 values; route expansion can use next-hop indices.
4. **Use incremental ledger checks.** Validate affected SKU after every transaction; run full reconciliation at snapshots and termination.
5. **Write only changes.** No179-cell snapshot per tick, no repeated stationary movement records.
6. **Stream chunks.** Do not retain the entire event history in RAM. Build final metrics from online accumulators and verify against streamed events.
7. **Compact transport encoding.** Stable ID dictionaries and one atomic transfer record; provide an adapter to the required logical event form.
8. **Compact snapshots.** Reference static lots/orders/catalogs; store active state, changed balances, compact order-status vectors, and counters.
9. **Skip empty conveyor ticks.** If no cargo is on any belt and no admission is pending, schedule the next needed integer tick from the earliest ready request. Arrivals and service completions still wake their proper phases.
10. **Skip provably blocked intervals only after correctness is established.** If no move/admission is possible and no capacity-changing event occurs before T, jump to the first eligible integer tick at/after T. Preserve unchanged merge cursors, waiting durations, and occupancy integrals.
11. **Keep snapshot/H boundaries scheduled independently.** Skipping conveyor work must not skip30-second snapshots, horizon accounting, pallet expiry, or drain deadlines.
12. **Compare optimized and dense engines.** Require identical semantic events, state hashes, metrics, and fixture times before enabling skipped ticks by default.

The release artifact is a reproducible backend whose events explain its metrics and whose replay reconstructs those same states. Performance improvements are acceptable only when they preserve that equivalence.