# ADR0090: Forecast planning placement with shared physical checks

Status: implemented proposal; focused verification belongs to the delivery packet.

## Authority and scope

ADR0087 supplies an authenticated offer forecast; ADR0088 freezes a fixed-budget
predicted outbound stream; ADR0089 associates that stream with finite original
stock. Add a separate immutable `ForecastPlacementDecision` for zero or one
explicit original SMALL/STANDARD whole-HU candidate. It is neither the C11 N1
outbound-shift namespace nor an actual future evaluation workload.

`prepare_forecast_placement_decision(stock, choices)` accepts only exact
`ForecastBoundStock` and the existing strict `PlacementChoices`. It freshly
verifies the stock/projection/forecast chain, then reloads the pinned physical
bundle and requires its complete `WorkloadSource` to match `projection.source`.
No caller graph, reconstructed fake C11 input, stock override or actual test stream
argument is accepted. Source rights, initial stock and source placement remain
unchanged. All predicted offers, arrivals, B2B work and shortages survive even
when they cannot participate in the manual candidate.

The closed wire namespace is `qoima-forecast-placement-decision-0.1.0`, scope
`predicted_offers_single_original_hu_planning_only`. Bind the full stock bytes,
explicit forecast/projection/stock IDs, exact choices, evaluations, selected
candidate, reasons and all 530 proposed placements. The stock object still holds
all original placements independently of that proposal. `load` recomputes the
complete result from its authenticated inputs; `verify` returns that fresh object
after recursive exact type/value comparison. Canonical JSON alone or a recomputed
hash cannot confer authority. CPU observations do not enter the forecast's
semantic bytes and therefore do not become decision identity.

## Shared checks, without cross-namespace admission

Add a read-only `PlacementInventory` Protocol exposing only `original_stock`,
`declared_receipts` and `allocations`. It is a structural internal interface, not a
runtime authorization token. Both public stock types fit it without casts. Public
decision entry points continue to authenticate their own exact types.

The existing `evaluate_candidate` is a C11 wrapper around
`evaluate_source_candidate(bundle, inventory, source, choices, candidate)` using
`stock.inputs.scenario.baseline`. Its customer facts wrapper similarly supplies
that explicit source to `customer_source_facts`. The forecast adapter supplies
`stock.projection.source`. Physical and reservation helpers change only their stock
annotation. Their implementation and the complete `price_candidate` calculation
are shared. The old C11 public prepare/load/verify and serialization are unchanged.

ADR0083's source feasibility precedes cost: unique original HU; distinct vacant
compatible L1 manual slot; dimensions/orientation/payload/module capacity; existing
S01/S02 plus explicit permission; mass <= min(15 kg, actor limit); source-port cargo
service; declared customer buffer and connectors; absent-only manual route policy.
Caller actor/home/speed/handling and customer-buffer choices remain explicit
planning choices, not measured facts or runtime grants. Each original whole HU
can fund at most one original-bound offer. ADR0089 P0 has no incoming offers or
receipt declarations; inventing a receipt reservation is rejected.

## Full cost and honest selection

Retain exact directed route IDs and Fraction durations, with a ceiling for each
complete operation. Pay approach, take, loaded carry, place and return, and compare
complete baseline/adapted customer cycles using the same actor, home and speed.
Gross customer saving minus the full transfer is the net, once. Select only a
strictly positive net; no candidate, missing evidence, infeasibility, zero or
negative net keeps no-op. No improvement threshold is manufactured from forecast
weights and no repeated visits to an already consumed whole HU are inferred.

Independent hand oracle: baseline 25 s, adapted 9 s, full transfer 22 s; net -6 s.
The declared source example forecasts only DEMO_113, uses an explicit permitted
mix with EXPRESS share 1, budget 4, H=1000 s and inbound budget 0. The sole affected
original HU is `v3:HU:initial:DEMO_113:01`, STANDARD_W:004:L1:B1 to free
FLEX_W:003:L1:B1, with S01 and EXPRESS cell 08 choices. Full transfer costs
196160001 ticks, gross saving 140799998, net -55360003: keep the negative evaluation
and select no-op. Repeated predicted DEMO_113 offers use other stock or remain
shortages, never repeat this HU's saving.

## Boundaries and verification

`operational_admission`, `actual_test_stream` and `full_n1_acceptance` stay false.
Uncontended planning work is not an observed paid integral, elapsed completion,
throughput or realized benefit. Queues, contention, actual held-out workload,
physical execution, heavy cargo controllers and full N1 comparison remain separate.
No engine, ledger mutation, API, DES or source-capability expansion is performed.

Tests precede implementation. Cover the hand arithmetic, actual source negative
decision, distinct infeasible/unpriced explanations, unchanged full allocation
stream, fresh source reads, exact aliases and rehashed IDs/costs/placements, and
mutual C11/forecast namespace rejection. Before/after raw C11 decision snapshots
guard the narrow shared-helper extraction, alongside existing placement tests.
