# Source-bound single-candidate placement decision

`app.v3.outbound_placement_decision` exports:

```python
prepare_placement_decision(stock, choices) -> N1PlacementDecision
load_placement_decision(raw_bytes) -> N1PlacementDecision
verify_placement_decision(retained) -> N1PlacementDecision
```

Supply a freshly bound `BoundOutboundStock` and explicit immutable
`PlacementChoices`; there is no workload, speed, horizon or receipt default.
Choices contain zero or one original-HU candidate. The decision retains the entire
offered population, source/stock identity and original placement. B2B, receipts and
shortage are preserved even though the one candidate is limited to manual
SMALL/STANDARD. Missing customer or receipt destination bindings yield explicit
`not_evaluable` reasons and no cost rather than a zero-cost assumption.

A `PlacementCustomer` names the unique allocated offer and exact source port. Its
`buffer_choice` is canonical UTF-8 JSON with existing `BufferChoice` fields:
`place_id`, `port_id`, `zone_id`, `bounds_xz`, `path_xz`, `height_m`,
`max_payload_kg`; physical numeric values are explicit decimal strings. The source
cell bounds are preserved and its proposed local connector is geometrically
checked. Customer pickup/place ticks are explicit choices; service ticks must equal
the source per-class service. Both customer cycles use the same actor/home/speed
as the complete transfer. Incoming targets bind exact declared job/HU IDs and
reserve initially free source slots; this creates neither stock nor readiness.

`evaluations` retains feasibility, affected HU/offer, complete operation routes,
Fraction seconds, rounded ticks and negative as well as positive results. `no_op`
is expected when full transfer cost exceeds the single affected cycle's saving.
For example, 16 s gross saving minus22 s transfer is net-6 s; no second subtraction
is made. No-op wins ties. `placements` is a proposed projection, never a ledger
mutation or a rewritten source baseline.

`price_candidate(graph, facts)` in `outbound_placement_cost` is an analytical helper
for independent hand tests. Its graph is not accepted as source input by the public
decision API. It requires edge cost equal physical length. The source API always
reconstructs pinned graph facts and typed choices; readers recompute all evidence.

All outcomes remain planning-only: `operational_admission=false` and
`full_n1_acceptance=false`. No execution, staffing availability, queues, deadlines,
port-window success, traffic proof or B2B runtime support follows from these costs.
See ADR0083 for the single-consumption bound and receipt reservation limitations.
