The geometry and analytical fixture arithmetic agree. The largest risks are unfinished runtime contracts, ambiguous scheduling at phase boundaries, and replay state that cannot yet be reconstructed from schema-validated data.

No files were modified. I independently counted the layout’s **184 picker nodes, 205 edges, and 179 conveyor cells**. Python execution failed in this environment, so I did **not** execute the validator or claim its checks passed. Some large file reads were truncated; consequently, this is a substantive audit, **not a certified exhaustive reading of every line**.

## A. Spec audit and proposed ADR decisions

Locations below use document sections and JSON paths. Quotes identify the relevant requirement; proposed decisions are recommendations to freeze.

### Arithmetic verified

| Item | Independent calculation | Finding |
|---|---|---|
| Building | 72×48=3,456 m²; 3,456/(20×18)=9.6 | Correct |
| Storage | 12×12×2×3=864; ground=288; reserve=576 | Correct |
| Picker graph | 12×15+3 homes+1 relocation buffer=184; 12×14+3×11+3+1=205 edges | Correct; matches JSON counts |
| Occupied addresses | 200 ground+400 reserve=600; empty=88+176=264 | Correct |
| Inventory | 200×(2,000+500+500)=600,000 units | Correct |
| Staff | 12+6+2+2+2=24 | Correct; vehicles are additional entities, not people |
| Conveyor | 54+2+54+2+3×1+6×2+6×1+46=179 | Correct; matches JSON sum |
| Feed destination offsets | LOOP_W runs X62→8: offsets 52,34,16 for X10,28,46 | Destinations `LOOP_W:52/:34/:16` |
| Branch source offsets | LOOP_E runs X8→62: offsets 12,18,24,30,36,42 | Sources `LOOP_E:11/:17/:23/:29/:35/:41` |
| Outfeed destinations | OUT_MAIN runs X20→66: offsets 0,6,12,18,24,30 | Destinations `OUT_MAIN:0/:6/:12/:18/:24/:30` |
| I01→PK01 | feed1+west2+turn2+east12+branch2=19 m | Correct |
| PK01→shipping | outfeed1+main46=47 m | Correct |

Fixture timeline:

```text
walk:                 (4 + 8.5 + 8.5)/1.2 = 17.5
pick:                 2 × (6 + .15)       = 12.3
handoff ready:         17.5 + 12.3 + 3     = 32.8
feed accepted:        ceil(32.8)          = 33
first movement:                            34
pack arrival/start:   33 + 19              = 52
pack complete:        52 + 20 + 2×2 + .05×2 = 76.1
outfeed accepted:     ceil(76.1)           = 77
shipping arrival:    77 + 47               = 124
scan/placement:      124 + 8               = 132
seal:                132 + 300             = 432
dispatch:            432 + 6/2 + 15 + 8/2 + 15 = 469
forklift home:       469 + 10/2             = 474
```

**Important:** 19 and 47 include the final cell’s traversal before delivery to the external buffer. Counting only cell-to-cell hops gives an off-by-one error.

### Contradictions and missing decisions

| ID / location and quote | Issue | Precise ADR decision |
|---|---|---|
| A01 — `01` introduction, multiple references: `contracts/README.md` | Supplied active file is root `contracts_README.md`. Relative `legacy-v1` links in that file also assume a different location. | Declare one canonical contract document path and repair references in the next revision. |
| A02 — `01 §11`: “структура manifest/chunks сохраняется”; contracts README: “первый runtime может использовать inline” | Delivery structure is mandatory, but no manifest/chunk schema exists. | Inline and chunked transports implement one logical contract; freeze both schemas in H1. |
| A03 — `04 §8`: seek may be replaced by snapshot controls; `05 §10`: arbitrary seek identity required | Cut line changes acceptance without explicitly changing the gate. | Define full and reduced demo profiles. Reduced profile disables arbitrary seek visibly and cannot claim the full seek gate passed. |
| A04 — `01 §10`: drain until no active work; contracts README: partial receiving blockage | No definition of terminal work versus inert stored inventory. Forklift return also continues after dispatch. | Drain includes admitted receipts, pending transfers, timers, scans and vehicle return; static reserve stock and empty recurring ticks do not keep a run alive. |
| A05 — `01 §10`: stockout/deadlock/cap; run `termination_reason` scalar | Multiple independent failures cannot be represented honestly. | Add subsystem outcomes plus reason list; define a deterministic primary-reason precedence. |
| A06 — `05 T2`, `01 §10`: shift throughput versus drain | `packed_total`/`dispatched_total` do not identify their observation window. | Export separate `at_horizon` and `at_end` metrics. Shift throughput uses `[0,H)` exclusively. |
| A07 — `05 §10`: events apply at `at_s<=clock`; utilization `[0,H)` | State “at H” could include events that shift metrics exclude. | Define snapshots as post-phase-4 state at time t; define shift metrics separately over `[0,H)`. Label boundary conventions explicitly. |
| A08 — `01 §6`: inventory checked before assignment; defaults: `eligible_fifo_by_arrival_and_order_id` | Arrival-time checking versus dispatch-time checking changes stockout winners. “Eligible” can imply bypassing the head. | At phase 3, process FIFO orders: atomically test free stock, reject shortages, otherwise require picker+tote and reserve together. No bypass of an admissible head waiting for resources. |
| A09 — `01 §6`: atomically allocate picker, tote and lines | No stable worker/tote selection rule. | Choose lowest available actor ID and tote ID after sorting orders; perform allocation in one transaction. |
| A10 — `01 §5`: target set “на индукции” / “до индукции” | Does blocked handoff already reserve station WIP? | Select and reserve target when handoff becomes ready, before waiting for feed admission; retain until parcel outfeed acceptance. |
| A11 — `01 §5`: “атомарно, затем принять новые грузы” | Merge arbitration versus new source admission priority unspecified. | Existing conveyor transfers arbitrate first. External admissions use only remaining free inlet cells, in stable request order. |
| A12 — contracts README: “от выходов к входам” | Loop has no natural topological order; an in-place sweep can move cargo twice or introduce bias. | Solve moves from immutable occupancy with dependency propagation; cycles need an explicit rule. Do not use segment iteration order as semantics. |
| A13 — `01 §5`: blocked branch, no recirculation | Generic layout graph retains the straight-through loop edge at a diverter. Shortest-path reachability does not prove routing compliance. | Targeted tote must take its designated branch; when unavailable it waits at the diverter and cannot follow the straight edge. |
| A14 — contracts README: cell-boundary movement | Logical occupancy and rendered position can disagree during a blocked tick. | Cargo occupies its current cell throughout traversal; interpolation ends at its exit boundary and holds there until accepted downstream. |
| A15 — phases table versus pallet timeout | At expiry, phase-3 task assignment could reserve another pallet slot before sealing. | In phase 3: expire/mark `SEAL_PENDING`, finalize eligible seals, then allocate new scans/tasks. |
| A16 — `05 D8`: in-flight scan survives timeout | What happens to a parcel and shipping-buffer capacity while scanned? | Remove parcel from shipping queue at scan start; record shipper ownership and reserved pallet slot; place at scan completion. |
| A17 — `01 §6`: sealed queue capacity8 | Does forklift pickup free queue space at task assignment or after pickup15s? | Reserve task at assignment; pallet remains queue-owned until pickup completes. Define capacity ownership accordingly. |
| A18 — receiving queue8; glossary excludes service from queues | Total receiving capacity could be8 or10 with two receivers. | Define queue capacity8 excluding service; separately cap processing and processed-awaiting-pickup positions. Specify whether receivers remain blocked holding processed pallets. |
| A19 — receiving outside boundary | External backlog can disappear from reports or block “drained” forever. | Materialized receipts persist in an external FIFO; record scheduled/accepted/processed/stored counts and terminal pending locations. |
| A20 — reserve staging40, “примерно через два часа” | This is approximate, not exactly t7200: receipts start90s and transport adds delay. | Report the actual 40th putaway time; do not encode7200 as a golden result. |
| A21 — `01 §8`: independent streams with “закреплёнными seed” | Actual substream seeds/derivation and test date are absent. | Freeze test date, calendar, RNG version, explicit stream derivation, SKU sampling algorithm and draw order. |
| A22 — `01 §8`: promotion multiplier5 | Weight multiplier is not a fivefold increase in realized visits because of normalization and sampling without replacement. | Label as a sampling-weight multiplier; store original/normalized weights and observed visits. |
| A23 — `01 §9`: ABC “training visits”; shortlist “изменению … к train baseline” | 42 versus56 days; total visits versus daily rates; forecast duration unspecified. | Freeze ABC cutoff/window and units. Compare normalized visits per common planning horizon; scale forecast to1h/8h explicitly. |
| A24 — `01 §9`: shortlist32, greedy disjoint swaps | Pair ties, positive-gain tolerance, and multi-swap relocation route composition unspecified. | Freeze canonical pair ordering, exact gain comparison and tie-break. Charge each swap’s stated home-to-home route independently unless a different route optimizer is explicitly adopted. |
| A25 — relocation before shift, 24 staff during shift | Relocation actor and replay time domain absent. | Treat relocation as a separately identified pre-shift labor artifact; initial shift state is post-relocation. Do not overlap it with shift actions or subtract its cost twice. |
| A26 — cargo registry includes `contents`; tote reused | One static tote content list cannot describe multiple orders; pallet aggregation can duplicate parcel units. | Registry stores identity/static metadata; mutable contents and containment live in state/events. Count inventory only at leaf ownership locations. |
| A27 — fixture `scenario.arrivals`, `assignment_override`, forced actor/post | Fixture wrapper does not conform to `scenario.schema.json`. | Publish a valid materialized scenario plus a separate fixture setup/config artifact; never treat wrapper as schema-valid input. |
| A28 — `03` visual states versus run action states | WAITING/WALK/PACK labels differ from canonical state enum. | Freeze a presentation mapping from `(state,operation,reason)`; visual labels never become engine states. |
| A29 — hash requirements `01 §10–11`, `05 §9–10` | Layout, operations, failure schedule and forecast provenance are incompletely represented in run hashes. Canonicalization unspecified. | Hash canonical UTF-8 JSON with fixed numeric normalization; distinguish physical stock identity from placement-dependent inventory serialization. |
| A30 — `tools/validate_spec_v2.py` | Writes `verification_report.json`; checks schema structure, not runtime run validity. Missing legacy artifacts can fail preparation checks. | Split read-only validation from explicit report generation; label geometry/schema checks separately from engine/replay gates. |
| A31 — `tools/qoyma_decision_probe.py`, `06` | Probe is explicitly legacy31-node/20-SKU and writes data artifacts. It cannot validate v2 forecasting or throughput. | Keep legacy probe in a separate CI job; require fresh v2 materialized artifacts and measured results. |

The documented work-hour arithmetic is internally reasonable: **26 individual +4 shared hours per person**, or60 person-hours, within48 calendar hours. The risk is scope and sequencing, not addition.

## B. H1 contract freeze: v2.1 delta

`run.schema.json` currently validates envelopes much more strongly than behavior. Empty payloads, empty snapshots and malformed inner state can pass.

### Required schema changes

| Area | Current gap | Freeze in v2.1 |
|---|---|---|
| Run metadata | Missing config/assignment/forecast versions and complete provenance | Versioned artifact references, hashes, scenario provenance, selected plan and model references |
| Timing | Only `horizon_s` | `ended_at_s`, drain limit, last dispatch, checkpoint convention, time representation |
| Events | Arbitrary `payload`; phase has no upper bound | Discriminated `oneOf` per kind; phase0…4; per-kind phase constraints |
| Actions | Both/neither geometry modes allowed | TRAVEL requires≥2 waypoints and forbids stationary `pos`; other states require `pos` and forbid waypoints |
| Cargo movement | Actions require `actor_id`; no dedicated cargo intervals | Separate `cargo_intervals` with container/cell geometry and absolute times |
| Cargo hierarchy | No parcel-child references for pallet | Typed containment links; ownership and content mutation semantics |
| Initial state | Inner arrays/objects untyped | Shared typed `State` definition |
| Snapshots | Only `{at_s,state:{}}` | `last_seq`, phase convention, state hash, typed full mutable state |
| Metrics | Numerous text-required metrics absent/untyped | Typed horizon/end metrics, role/post/queue/conveyor/tote/inventory metrics |
| Termination | Scalar reason only | Per-subsystem status/reasons, unresolved work, final locations, error diagnostics |
| Transport | Inline only; root rejects extras | Separate manifest/chunk schemas and declared encoding |
| Scenario | Empty order lines allowed | `minItems:1`; semantic unique SKU/order/receipt checks |
| Scenario references | Arbitrary IDs/times | Known catalog references; arrivals in `[0,H)`; reject duplicate IDs and nonfinite numbers |
| Scenario config | No explicit binding to complete immutable inputs | Configuration/stock/assignment references and hash-normalization version |

Cross-field checks such as `end>start`, monotone waypoints, reference integrity and uniqueness by a specific key need semantic validators; ordinary `uniqueItems` is insufficient.

### Event payload requirements

Use strict payload objects with `additionalProperties:false`.

| Kinds | Required logical fields |
|---|---|
| `order_arrived` | `order_id`, immutable order reference |
| `order_rejected_inventory` | order, shortage lines with requested/free units, reason |
| `order_assigned` | order, actor, tote |
| `stock_reserved` | order, SKU, slot, lot, quantity, reservation ID |
| `sku_picked` | same identifiers plus actor and transfer ID |
| `picked_last` | order, actor, tote |
| `handoff_ready` | order, tote, actor, induction, ready time |
| `tote_inducted` | preceding IDs plus target post, cell, station reservation |
| `cell_entered` / `cell_exited` | cargo, cell, shared transition ID, source/destination container |
| `pack_started` | order, post, actor, tote |
| `order_packed` | order, post, actor, tote, newly created parcel; atomic content transfer and tote release |
| `parcel_outfed` | order, post, actor, parcel, cell; WIP release |
| `shipping_arrived` | order, parcel, shipping buffer |
| `parcel_scanned` | order, parcel, pallet, actor, slot reservation |
| `pallet_seal_pending` | pallet, trigger, expiry/full time, outstanding reservations |
| `pallet_sealed` | pallet, parcel IDs, order IDs, task ID, actual seal time |
| `order_dispatched` | order, parcel, pallet, actor, dock, task |
| `receipt_accepted` | receipt, pallet, SKU, quantity, ledger destination; actor nullable before service |
| `receipt_processed` / `pallet_putaway` | receipt, pallet, SKU, quantity, actor, task, source/destination |
| `stock_transferred` | transaction ID, SKU/lot/quantity, source/destination, cause |
| `actor_state_changed` | actor, state, operation, reason, entity, action ID |

The text’s blanket actor requirement for `receipt_*` needs correction: acceptance into a waiting queue can occur without an assigned receiver.

Also freeze **which event mutates which state**. Otherwise `sku_picked` plus `stock_transferred`, or `cell_exited` plus `cell_entered`, can apply the same transfer twice.

### Snapshot minimum

```text
actors: position, state, current action/task
cargo: contents, containment, location, target, traversal timing
inventory: lots, on_hand, reservations
orders: stage, milestones, rejection reasons
queues: ordered membership
totes: available and allocated ownership
stations: service, waiting FIFO, blocked parcel, reserved WIP
pallets: contents, reserved slots, state, first placement, expiry generation
merges: stable input order and next cursor
pending transfers/tasks/timers: IDs, ready times, cancellation generations
metrics accumulators: counts, integrals, interval boundaries
last_seq and state_hash
```

A replay checkpoint is not automatically a resumable engine checkpoint. If engine resume is required, specify the scheduler state separately.

## C. SimPy pitfalls and mitigation patterns

These are implementation patterns to validate against the pinned SimPy version.

### 1. One timestamp coordinator

`timeout(0)` is not a phase barrier. Process creation order must not determine warehouse semantics.

```python
# Conceptual coordinator; SimPy callbacks enqueue commands.
while pending:
    t = next_business_time()
    advance_clock(t)
    for phase in range(5):
        for cmd in stable_commands_at(t, phase):
            apply(cmd)
    if debug:
        check_invariants(state)
    checkpoint_if_due(t)
```

Commands scheduled at the current timestamp must not retroactively enter an already completed phase. Reject such scheduling or define an explicit same-phase closure rule.

### 2. Exact time and integer ticks

With speeds1.2 and2, current decimal service times can be represented using rational arithmetic. Avoid repeated floating-point addition.

```python
from fractions import Fraction


def ceil_fraction(x):
    return -(-x.numerator // x.denominator)


ready = Fraction(164, 5)  # 32.8
admit_tick = ceil_fraction(ready)  # 33
```

A completion exactly at33 in phase0 is eligible for phase2 admission at33. New cargo cannot move again until34. Generate ticks from integer indices, not `tick += float_dt`.

### 3. Atomic conveyor movement

```python
before = occupancy.copy()
moves = resolve_moves(before, requests, cursors)
validate_unique_sources_and_destinations(moves)

after = before.copy()
for move in moves:
    del after[move.source]
for move in moves:
    after[move.destination] = move.cargo

occupancy = after
```

Resolve dependencies before commit. Downstream vacancies can propagate through a chain, but every old cargo gets at most one move. External buffer exits also participate atomically.

### 4. Round-robin state

```python
inputs = tuple(sorted(merge_input_ids))
winner = first_eligible_cyclic(inputs, cursor, eligible)
if winner is not None and commit_succeeded:
    cursor = (inputs.index(winner) + 1) % len(inputs)
```

Persist cursor and input ordering. Do not advance on a failed proposal. Include internal belt continuation and competing feed/outfeed inputs in the same arbitration model.

### 5. Cancellation without cargo loss

```python
request = resource.request()
try:
    result = yield request | stop_event
    if stop_event in result:
        return
    yield perform_work()
finally:
    if request in resource.users:
        resource.release(request)
    else:
        request.cancel()
```

Resource cleanup is separate from business-state rollback. At terminal cutoff:

- Cancel pending requests and invalidate stale callbacks.
- Preserve physical cargo at its last valid location.
- Release inventory reservations only according to an explicit cancellation policy.
- Close open action intervals at `ended_at_s`.
- Never manufacture completion events.

### 6. Drain and deadlock

- Stop external generation atH; retain already materialized pending receipts.
- Deadline is `H+max_drain_s`, not last-progress time plus7200.
- A live pallet expiry is useful future work.
- A recurring conveyor tick alone is not useful future work.
- Static reserve inventory is not unfinished work.
- Detect deadlock from blocked dependencies and absence of future enabling work; a timeout alone is only a stall heuristic.
- A full reserve with pending receipts is a terminal capacity blockage, even when customer orders have all dispatched.

### 7. Determinism

- Sort IDs at every arbitration boundary.
- Use heap entries `(time,phase,priority,stable_id,serial)`.
- Never compare callbacks or mutable objects in heap ties.
- Use materialized exogenous inputs rather than drawing randomness during divergent A/B execution.
- Pin dependencies and RNG implementation.
- Hash canonical semantic output, excluding wall-clock timings.
- Use generation tokens for pallet timers so stale expiry callbacks cannot seal twice.

## D. Bug-prevention strategy

### Invariants after every settled timestamp

Run after phase4, not halfway through an atomic transfer.

```python
def check_invariants(s):
    for sku in s.skus:
        assert s.initial[sku] + s.accepted[sku] == physical_units(s, sku)

    assert set(s.available_totes).isdisjoint(s.allocated_totes)
    assert set(s.available_totes) | set(s.allocated_totes) == s.all_totes
    assert len(s.all_totes) == 96

    assert unique_cargo_locations(s)
    assert capacities_hold(s)
    assert reservations_within_on_hand(s)
    assert station_wip_matches_owned_work(s)
    assert pallet_contents_and_reservations_fit(s)
    assert actor_intervals_do_not_overlap(s)
    assert event_sequence_is_valid(s)
```

Additional assertions:

- Each physical cargo has exactly one owner/location.
- Parent pallet contents are not counted again alongside child parcels.
- Pack waiting≤4, excluding service.
- Shipping waiting≤40; sealed queue≤8; reserve staging≤40.
- `0≤reserved≤on_hand`.
- Tote release, parcel creation, seal task and dispatch occur exactly once.
- Target post never changes after reservation.
- No worker becomes free before successful handoff/outfeed acceptance.
- Every conveyor move follows a legal target-sensitive edge.
- Event `seq` is unique and increases in emission order; `(time,phase,seq)` is sorted.
- Driver and vehicle trajectories agree.

### Test portfolio

| Layer | Concrete tests |
|---|---|
| Golden fixture | Exact milestone table above; ordered transfers; actor intervals; ledger balances; final forklift availability474 |
| Boundary goldens | Completion32.999/33/33.001; snapshot30; chunk60; arrivalH; max-drain deadline |
| Acceptance fixtures | Translate every numbered gate in `05` into executable input/expected assertions |
| Hypothesis | Small queues, simultaneous completions, randomized capacities, stock shortages, merge contention, interrupted scans |
| Differential replay | At every checkpoint: independently reduce events from initial state and compare canonical state to engine checkpoint |
| Transport differential | Inline decode equals chunked decode equals dictionary-decoded logical stream |
| Metamorphic | Change JSON object insertion order; repeat run; change playback FPS/speed; no-op plan; all must preserve semantic result |
| Negative mutations | Duplicate transfer, missing exit, wrong phase, illegal cell, over-reservation, stale timer, duplicate seal, missing snapshot field |
| Browser integration | Seek10→80→20→80; reset; A/B toggle; chunk unload/reload; missing/corrupt chunk |

Keep the replay reducer independent of engine mutation helpers; otherwise both sides can reproduce the same defect.

**CI gates:** schema and semantic validation → fixture/invariants → property tests → determinism → replay differential → normal/peak export → production browser smoke/offline. Run8h and performance budgets as release gates with recorded hardware and artifacts.

## E. Frontend integration risks and early handoff

### Size and streaming

The30MB target is demanding. At600 orders, even just19+47 cell traversals per order produce roughly39,600 traversals, or79,200 entered/exited records. At300 bytes per record, that is already about23.8MB before snapshots, actions, other events and longer routes. Actual throughput may be lower, but this illustrates the risk.

Freeze:

- **30MB means total raw UTF-8 bytes across the entire1h run export**, with an explicit decision on whether drain is included.
- Compression does not satisfy a raw-byte limit.
- Streaming reduces memory, not total payload.
-64MB cache is measured as retained decoded event data; separately measure total browser heap.
- Dictionary IDs are run-global or explicitly chunk-scoped.
- Atomic transfer encoding has a deterministic adapter to the logical event stream.
- Snapshot state excludes immutable history but retains all mutable reconstruction state.

### Manifest/chunk rules

```text
manifest:
  versions, input hashes, encoding version, dictionary reference
  initial-state/catalog references
  chunks[{id,start_s,end_s,first_seq,last_seq,sha256,bytes,url}]
  snapshots[{at_s,last_seq,state_hash,chunk_id}]
  final metrics and termination

chunk:
  run_id, schema_version, encoding_version
  [start_s,end_s) coverage
  events, action/interval references, snapshots
```

Define a final-boundary rule for events exactly at run end. Hash the exact downloaded bytes. Actions crossing chunks need stable IDs and deduplication, or one owning chunk plus an interval index.

### H4/H8 handoff

- **H4:** schema-valid hand-authored run on full geometry, all24 actor identities, one complete order, explicit synthetic-stub provenance, fixture milestones through474. Include a chunk boundary and snapshot boundary.
- **H8:** engine-generated equivalent using the identical reader interface. Compare normalized fixture state and events; do not patch missing semantics inside the renderer.
- Add a second early fixture containing blocked induction, blocked pack output and simultaneous pallet reservations.

Shared `contracts/` fixtures should cover valid inline/chunked runs and invalid payloads. Both Python validation and frontend JSON Schema validation must accept/reject the same corpus. TypeScript types alone do not validate downloaded JSON.

Version checks must cover schema, layout, config and encoding. Unknown major semantics should fail before playback. Do not silently interpret a new event kind as a harmless no-op.

## F. Ten most likely demo failures

| Rank | Failure | Prevention |
|---|---|---|
| 1 | Frontend/backend disagree on payload meanings | H1 discriminated schemas; shared fixtures; H4 reader working |
| 2 | Off-by-one conveyor timing | Freeze33→34→52 and77→124 goldens |
| 3 | Tote, parcel or inventory duplicates during seek | Atomic transfer IDs, snapshot watermark, independent replay differential |
| 4 | Conveyor sweep permits double movement or collisions | Immutable pre-tick state, dependency solver, per-tick invariants |
| 5 | Final pallet never seals or seals twice | Generation-token timer; `SEAL_PENDING`; D8 concurrency fixture |
| 6 | Run never terminates because of ticks, reserve blockage or stale requests | Explicit useful-work predicate, subsystem outcomes, deadline and cancellation tests |
| 7 | Browser freezes loading a large inline run | Measure bytes early; compact transfers; chunk streaming; bounded decoded cache |
| 8 | KPI shows drain dispatches as shift throughput | Separate horizon/end metrics; boundary tests; labels tied to metric window |
| 9 | Rendering is fast on static assets but slow during replay | Test mass movement and jam scenes on target laptop; instancing, low mode, one viewport |
| 10 | Live backend/network fails during presentation | Local validated runs/assets, cold offline rehearsal, visible saved-run label |

**Release recommendation:** freeze v2.1 semantics before implementing further exporter or replay behavior. The existing arithmetic is a useful foundation; it does not yet establish a safe integration contract.