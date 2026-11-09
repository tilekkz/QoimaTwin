# 0016. Planning and slotting comparison protocol

Status: proposed by Claude for integration by Codex main, 2026-11-07. Shared contracts v2.1 are not
agreed yet, so the artifacts below are backend-internal JSON proposals and `contracts/` is unchanged.

## Inputs

The planner takes pure inputs only (`app.planning.PlanningInputs`): layout, config, baseline
assignment, `training_visits` (first 42 history days) and `expected_visits` (already scaled to the
experiment horizon), both `Mapping[str, float]`, plus a non-empty `forecast_id`. There is no scenario
or test-order argument; a plan is fixed before test. The forecast worker's `ForecastSnapshot`
supplies `training_visits_by_sku` and `visits_by_sku` (8 h day); the caller scales the latter to H.
Each mapping must cover exactly the SKUs of the assignment with finite values >= 0; anything else
raises `PlanningInputError` (a future HTTP 422). Floats are converted to exact `Fraction`s.

## Frozen ABC

Ground slots are the 288 level-1 pick faces. Slot cost = mean over induction homes (I01, I02, I03,
weight 1/3 each) of the round trip `2 * d(home, service_node)` on `picker_graph`. Slots are ordered
by (cost, slot_id); SKUs by (-training visits, sku_id). The i-th SKU takes the i-th slot; 88 slots
stay empty. Each active lot moves with its SKU; reserve lots, empty reserve slots and quantities
are unchanged. The ID is `frozen-abc-<16 hex>` over the training-visit hash, the lots and
quantities (without active slots), reserve placement and the layout version.

## Greedy 0/2/8

`J = sum(expected_visits * mean_home_roundtrip_m / walk_speed) + relocation_labor_s` (surrogate of
single visits, not a throughput forecast).

- Baseline load of a SKU = its training visits rescaled so that their total equals the expected
  total (proportional to the training share). This is our resolution of "change of forecast load
  against the train baseline". The shortlist holds up to 32 SKUs by the absolute change, ties by
  sku_id.
- Each iteration evaluates every pair of shortlisted, still untouched SKUs: at most C(32,2) = 496.
  Gross gain of swapping SKUs a, b = `(E_a - E_b) * (cost(slot_a) - cost(slot_b)) / walk_speed`.
  Net gain = gross - relocation labor. The best net wins, ties by (sku_a, sku_b). The planner
  stops at the budget or when the best net is <= 0. Only occupied pairs are swapped.
- Budgets are integers in [0, 16]; the standard family is 0/2/8. Budget 0 gives
  `noop_reason="budget_zero"`; no profitable pair gives `"no_positive_net_gain"` and stores the
  best rejected pair (P4).

## Relocation route

For a swap A<->B one relocation worker walks `I02, A, buffer, B, A, buffer, B, I02`
(`layout.relocation_home_node_id`, `layout.relocation_buffer_node_id`, here `N_REL_BUFFER` with one
6.5 m edge to `N_A12_Z42`). Moves: A->buffer, B->A, buffer->B; six take/place of
`relocation_take_or_place_s` (8 s). Both orientations are computed; the shorter is chosen. On the
undirected graph their totals are always equal, so the tie keeps `a_first` deterministically.
Every leg is an exact shortest path along picker-graph edges; no rack shortcuts (P5).
`verify_plan` rejects a plan whose travel hop is not an edge, whose path is not a shortest path,
or whose duration disagrees with the distance. It then regenerates every selected pair (both
orientations, labor, gross/net from the shortlisted expected visits), the whole relocation
schedule, the paid labor/distance totals and the final-assignment hash, and requires exact
equality; only then does it check `plan_id`. A re-hashed plan with unpaid relocation, a foreign
SKU or a shortened handling is therefore rejected too.

## Plan artifact (`qoima-plan-v1`)

JSON-ready Pydantic model: forecast_id, baseline assignment ID/hash, training/expected visit hashes,
parameters, shortlist, per-iteration pair counts and best pair, selected pairs (routes, both
orientation distances, walk/handling/labor, gross/net), totals, predicted J, a before-shift
relocation schedule and the final assignment with its hash. `plan_id` is the SHA-256 of the
canonical JSON of all other fields; it contains no test result. No-op plans are explicit
artifacts with `final_assignment` identical to the baseline.

The relocation schedule uses its own `pre_shift` calendar: offsets in exact ticks (and float
seconds) from the window start, actor `RELOCATION_01` (not a roster member). Each swap yields three
transfer records with take/place tick intervals and 13 actions at most (zero-length walks between
equal nodes are omitted). The shift start (0) and arrival calendar do not move.

`apply_plan` replays the transfers on the active lots: the source must hold that exact lot, the
destination must be empty, the buffer must end empty and the same slot set must be occupied.
Lots move whole; nothing is created, split or counted twice. Assignment hashes equal the run
identity `assignment` hash (ADR 0008).

## Comparison (`qoima-compare-v1`)

`compare_slotting(baseline_inputs, plan)` builds the candidate by `apply_plan`, then requires equal
fingerprint hashes for layout, config (including operation policies), actors, orders, receipts and
initial inventory, and equal scenario_id, horizon, experiment_type ("slotting"), timebase and
engine version. Baseline and candidate assignment hashes must match the plan. No failure schedule
exists in v2 inputs (breakdowns are P1). Both runs use `Engine(check_invariants=True)`.

Labor = TRAVEL + BUSY_SERVICE per actor and role in [0, cutoff); BLOCKED (including open blocks)
and WAIT_RESOURCE are separate. Windows: at_horizon (cutoff H) and at_end (each run's end tick).
`net = baseline - candidate - relocation_labor`, shown for pickers and for all roles, computed in
exact ticks. The verdict (improved/worsened/unchanged) uses the all-role net. A worse result is
kept as is (P6). Each side stores event/action digests (semantic content, no IDs or wall time) and
the metrics summary; `semantic_identical` is true for a no-op (P1). `comparison_id` hashes the
artifact without itself; no wall-clock timings are stored.

## Run identity of forecast and plan (amends ADR 0008)

`RunInputs` has two optional keyword-only fields; the six positional arguments are unchanged.

- `forecast_snapshot`: `ForecastSnapshot.semantic_dict()` (protocol, model, history hash, cutoff,
  test day, per-day predictions and training visits, validation, parameters). CPU timings and a
  declared `semantic_id` are rejected with `InputError`; they are not semantics.
- `relocation_plan`: `PlanArtifact.model_dump(mode="json")`.

Both are deep-copied, validated as canonical JSON and frozen once in `__post_init__` as
`SemanticJson(canonical, sha256)`; read them with `forecast_json()` / `relocation_json()`
(`to_dict()` returns a fresh copy). Later mutation of the caller's dict cannot change identity.
A `SemanticJson` passed again (for example through `dataclasses.replace`) is re-verified.

Decision: identity uses the content hash, never a declared ID. The hash is
`sha256(canonical_json(content without its self-ID field))`. For a forecast this equals the
forecast worker's `semantic_id` and the API artifact-store ID of the stored semantic dict; for a
plan it equals `plan_id`, and a declared `plan_id` that differs raises `InputError`. Absent
semantics hash as `sha256(canonical_json(null))`, as before. Canonical JSON keeps the float/int
distinction and treats tuples as arrays, so key order and tuple/list do not matter.

## Comparison bindings

- Baseline and candidate must have the same forecast hash; the baseline has no relocation plan;
  the candidate's relocation hash must equal the compared `plan_id`. A budget-0 plan therefore
  has a different candidate identity, while its event semantics stay identical (P1).
- If a forecast snapshot is supplied, its hash must equal `plan.forecast_id`; otherwise
  `ComparisonInputError` ("plan was made for forecast ..."). Without a snapshot the artifact
  records `forecast_snapshot_sha256: null` and claims no forecast provenance.
- When `compare_slotting` builds the candidate itself it copies the baseline (keeping the
  caller's forecast) and attaches the plan; a caller-built candidate is validated, not rewritten.
- `on_run(variant, engine, outcome)` is called once per finished run, baseline then candidate,
  including partial outcomes, so the API exports the same two engines. Its exceptions propagate.
  The returned artifact holds no engine.

## Scaling of visit maps

The forecast gives per-day (28,800 s) means: `predictions.visits_by_sku` and
`training_visits_by_sku`. The caller scales both by `H / 28800`. The shortlist then rescales the
training baseline to the expected total, so only the per-SKU change in share remains; this is
the resolution of the spec's "change of forecast load against the train baseline".

## Integration seams

- CLI/API: `POST /api/plans` maps to `plan_budgets`, `POST /api/compare` to `compare_slotting`
  with `on_run`. `PlanningInputError`, `ComparisonInputError` and `InputError` subclass
  `ValueError` for 422 mapping.
- Exporter: relocation actions/transfers are ready for a pre-shift replay track.
