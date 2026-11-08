# ADR0071: Observable coordinator KPI projections

Status: proposed implementation; tests authored, all execution deferred to final assembly.

## Requirement and boundary

The technical specification section 10 and the backend PDF page 6 require operational
metrics, including travel, workstation load, queues and inventory. The C namespace's
existing summary already reports unit/whole business cycle samples, unfinished and
unadmitted count-time areas, actual paid labor by effective role, port work, and separate
horizon/end observations. Those metrics must not be duplicated with different names or
silently replaced by older single-station or V2 quantities.

This additive projection consumes a validated `CoordinatorProfile`, its actual
`CoordinatorOutcome`, and either captured horizon or end snapshot. It does not dispatch
work, grant capabilities, re-run the engine, infer physical contact, or convert an
analytical reducer fixture into native publication evidence. The existing compiler and
native reader remain responsible for full source, profile, journal and snapshot validity.
The reducers reject local accounting contradictions rather than silently correcting them.

All counts use the settled inclusive observation at T. All areas use `[0,T)` in integer
microsecond ticks. At T=0, ratios are null; zero counts and distances remain meaningful.
If actual resource completion precedes H, each window retains its own denominator.
Planned movement contributes only its observed prefix, never a future completion.

## Added projections

| Field family | Authority and definition |
| --- | --- |
| Travel | Actual `operation_started` actor and `CandidateRoute.length_m`. Distance is the exact route length times elapsed/quantized operation duration, with a linear progress policy explicitly named. This measures logical paid route travel, not mesh-contact odometry. Stationary services add no distance. Every one of the original24 actors has a row and primary role; effective role attribution follows actual role transitions. Cart-push distance is the subset with actual operation.cart_id. |
| Six stations | Pack and clear operation intervals mapped through actual `PackingView.actor_id/station_id`. Bench reservation runs from assigned_tick until cleared_tick; it includes approach and any reservation wait. Pack/clear service utilization excludes approach/return and divides by T. Bench reservation utilization divides by T separately. Worker return cannot keep a physically released bench busy. Duplicate/overlapping service or reservation intervals reject. |
| Additional queues | Unit and whole admitted business WIP from admission until actual shipment, excluding pre-admission waiting and paid return. Receipt unadmitted waiting from offer arrival until actual admission, plus credited-but-unplaced HU exposure from actual credit until putaway. Future offers contribute zero. Existing unfinished/unadmitted unit/whole metrics remain authoritative in their original fields. These are distinct populations; do not add them as independent labor. |
| Materials | Current actual material containers and exact container-time/empty-unbound-time areas by declared material pool and finite empty-carrier rack. Initial containers come only from explicit materials; every change follows StockDelta before/after in journal order. A physically empty unsealed container is available here only if no admitted, unshipped order binds it. Admission therefore removes availability before physical pickup. Rack clearing is not replenishment of the original pool. Same-tick changes precede the next positive interval. Zero-empty-supply duration and physical free-place duration are separate: an empty rack has free storage positions but no empty carrier stock. |
| Inventory | Actual credited UnitToken identities, current container custody, SKU quantities and exact gross mass. Future receipt definitions do not exist in inventory until a ReceiptDelta creates their tokens. Container tare is counted once, unit contents/primary tare once. Owner-kind grouping distinguishes onsite, shipped and disposed packaging; disposed product units reject. Compare computed per-SKU/mass totals with native StockBalance. |
| Source storage zones | Re-load and verify the pinned source package, compare its raw source identities with the profile, then use the raw storage-slots zone_id mapping. No zone is inferred by splitting an owner name. Zone rows represent current storage-slot inventory only; worker/cart/belt/buffer custody remains explicit under owners. An analytical profile has no authoritative source zone table and reports unavailable. |
| Belt | Actual admitted→completed carrier count-time and current admitted carriers; native stopped-carrier exposure, including paid output pickup, remains separately named. Current physical body-occupied cell count comes from captured occupied_cells. Leased cells include reservations and must not be represented as body occupancy. |

Continuous body-cell occupancy integral is explicitly unavailable: the retained journal
does not record every continuous footprint/cell crossing. Blockage by cause is also
unavailable because the stopped counter does not classify every interval. Neither is
reported as zero. Actual stopped exposure is not the same as equipment failure or jam
time. The projection does not infer total belt capacity from module count.

## Independent arithmetic, written before implementation

- A10m route over2..7s contributes0/4/10m at2/4/7s. A4m return over7..9s makes12m
  at8s and14m at9s. Paid operation overlap must reject. A helper's distance follows
  actual transition/pack roles without adding staff.
- Station reserved10..16s, pack12..15s, clear15..16s: at15s service3, reservation5;
  at16s service4, reservation6; worker home20s changes neither area.
- Admission5s, shipment15s: admitted WIP area at10s is5 order-seconds and at20s10.
  Receipt arrival2/admission5/credit12/putaway23 gives3 waiting HU-seconds and11
  credited-unplaced HU-seconds, independent of return33.
- Two declared carriers in a pool over0..10s give20 carrier-seconds. O1 binding at4s
  leaves14 empty-unbound carrier-seconds even if the actual take occurs at5s.
  Binding both at4s gives8 empty-unbound carrier-seconds and6 zero-supply seconds.
  Empty rack capacity2 over10s has20 free-place-seconds, not20 available-carrier-seconds.
-24 SMALL units weigh24*(.03+.005)+.1 wrapper=.94kg. Two carriers(.2 each) and
  two packages(.05 each) make1.44kg. A credited24-unit receipt adds.94kg:
  before credit24 units/1.44kg, at credit48 units/2.38kg. Changing only a SKU label
  with total count24 cannot pass accounting reconciliation.
- Belt admitted3s/completed10s gives7 carrier-seconds. A recorded stopped3s remains
 3 stopped-carrier-seconds; this does not prove physical cell occupancy or cause.

## Integration and versioning

The new `coordinator_metrics_observed.observed_kpis(profile,outcome,point)` returns an
additive object with its own `qoima-coordinator-observed-kpi-proposal-1` version. The
owner of `coordinator_metrics.py` must connect it under each horizon/end window and
advance that summary's version in the final assembly. This package supplies an exact
small proposed diff with a raw preimage; it does not edit the shared module.

Existing published native bytes are immutable. An updated publisher must recompute
and validate the new summary rather than copying old metrics under a new capability.
Whether the new publisher/run version or explicit metrics policy joins run identity is
an integration decision for its owner before publication; old IDs must not receive
different content. Full source validation, profile/role-plan identity, no-op comparison,
and semantic reader validation cannot be bypassed by this reducer.

No runtime, CLI, API, frontend or shared contract changes are part of ADR0071. No tests,
static checks, AST checks, DES or benchmarks have been executed for this authored package.
Final acceptance requires the deferred focused checks and native composition tests;
the pure interval fixtures alone are not evidence of source-workload execution.
