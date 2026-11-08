# ADR0050: One V3 inventory authority across receipts and connected operations

Status: **Proposed — not implemented or an approved shared contract**

Date: 2026-11-08. Source pin:
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`.

## Context

ADR0041 stock accounting preserves all530 initial HUs,12256 packed units and
separate unit/material tare. Its token/container universe is fixed; it supports
SMALL unit picks and sealed parcel shipping but does not register new receipts
or move original whole wrappers between admitted owners. Manual whole-HU
execution maintains a separate ownership map and credits intake at service
start. The connected SMALL engine creates its own ledger and worker state.
Running them independently would duplicate stock/actors and cannot represent a
received HU later losing three units to a parcel.

Current inbound source explicitly intersects service windows with the supplied
horizon; outbound specifies completion inside its source window. Uniform
inventory ownership does not justify overriding those different rules.

## Decision

1. Extend the existing stock authority. Initialize source stock once, then append
   admitted receipt definitions/tokens/wrappers through validated transactions.
   Registered identities and recipes are immutable; current owner and contents
   change only through that authority. All runtime components share its live
   instance, one clock and one24-person physical actor/lease registry.
2. Treat arrival and service-start custody as **uncredited external delivery**.
   Register exactly one HU and its source recipe's unit ordinals at actual
   intake service completion. Its first inventory owner is the actual worker,
   vehicle or finite staging place at that event; no direct jump to storage.
   Putaway and shipping business completion are separate physical handoffs.
3. Admit new jobs only in `[0,H)`. Source inbound service must start in its open
   window and complete by `min(window_end,H)`, including completion exactly at H.
   Afterwards putaway/return may drain. Outbound service follows its source
   completion rule and may drain after H. End cap stops observation/execution
   without creating future effects; state remains truthfully partial if needed.
   At T, observed state includes effects with tick<=T; utilization integrates
   `[0,T)`. Retain integer microseconds and ceiling for positive operations.
4. Preserve old engine/profile/event versions. New shared mode has an explicit
   engine/input identity and versioned creation delta. Legacy manual service-
   start accounting and existing profile contracts are not silently rewritten.
5. Add separate intact whole-HU transfer/shipment commands. They preserve one
   original wrapper and original token ancestry; they do not enable heavy unit
   splitting or treat a partly picked SMALL wrapper as a complete HU order.
   Existing SMALL placement/packing/seal/terminal guards remain in force.
6. Reserve finite source/target and physical resources with live C04/C05/C08
   admission. Slot/module payload uses actual remaining contents plus wrapper
   tare; same-HU module occupancy and incoming claims are deduplicated. Original
   geometry remains unchanged. Release source only at pickup, buffer when the
   load leaves, port after service, and worker/vehicle after paid safe return.
7. Add a versioned `apply_once` command seam: identical transaction fingerprint
   returns its prior result without effects; differing reuse rejects. First
   application checks exact current revision. Failed validation changes neither
   authority nor resources/history. Existing direct methods retain strict
   duplicate-ID rejection. Complete creation/custody deltas support replay.
8. Reuse the existing connected human/belt calendar for the first combined
   receipt adapter, with paid manual step plans and shared actor/lease state.
   Do not concatenate independently executed manual/light histories. Validate
   future receipt-derived token recipes before execution without inserting them
   into initial live stock, then wait for actual putaway before dispatching pick.

## Invariants

Per SKU: `initial + completed_receipts = onsite + shipped + product_waste`.
Product waste remains zero until an explicit future operation is specified.
Uncredited offers reconcile separately, including their service custody.

Every registered unit has exactly one container and every physical container
exactly one owner. A moving wrapper and its contents are a containment hierarchy,
not two copies. Current stock/WIP is a partition of onsite. Shipped records and
provenance remain in the registry; shipment does not erase tokens.

Contents mass, primary packed-unit tare, original wrapper tare, carrier/package
tare and reusable supports are distinct. Empty wrapper disposition removes no
product and keeps tare in a terminal material account. No default replacement
materials, automatic refill or implicit infinite packaging pool is introduced.

The initial immutable registries become immutable baseline plus append-only
validated receipt registrations. Existing exact-type/object-identity corruption
checks must be extended, not removed. Whole-HU and unit reservations conflict on
the same physical inventory. Physical actor/vehicle/conveyor handoffs and stock
commits must refer to the same live operation/leases and exact source/proof data.

## First acceptance target

One new source SMALL_CARTON receipt24 units/.94 kg at IN_E_PARCEL, put into the
initially free statically compatible `v3:slot:SMALL_W:017:L1:B1`; then exactly
three units of that received HU go through the connected carrier/pack/belt/
OUT_S_EXPRESS flow. Keep all530 original HUs unchanged. Carrier .20 kg and parcel
.05 kg, recipes/placements, actor homes/speeds, graph connectors and handling
times are explicit synthetic inputs. No M07/contact or eight-class operational
claim follows from this example.

With initial materials, initial gross9404.10 kg becomes9405.04 after receipt.
After parcel shipment, tokens remain12280; onsite12277 and shipped3. Shipped
gross is.155 kg, onsite9404.885 kg, received residual wrapper.835 kg. It remains
occupied with21 units; empty carrier retains its .20 kg. These are hand/C02
arithmetic assertions, not values generated by the engine under test.

Hand timeline: receipt approach2 s, service10 s, buffer carry3 s, place1 s,
pickup1 s, slot carry5 s, place1 s and return10 s yield credit12, putaway23,
home33. A separate picker waiting for that putaway has attach1+cart2+pick3,
so pick29; cart3+park1+detach1+carry1+deposit1 gives belt handoff36 and paid
return home43. All directed edges and speeds are declared before execution.

Boundary tests require successful credit at H=12 with putaway/return after H,
rejection of an intake ending12 when H=11.999999, no downstream new job after H,
outbound-after-H behavior inside its own window, cap with actual WIP, duplicate
and conflicting retries, overlapping HU/unit reservations and unavailable
finite storage/buffer. The first source fixture keeps handovers inside H.

## Consequences and limits

Eight-class accounting can be tested using source recipes: one receipt each is
107 units/1784.29 kg (contents1609.52, primary tare64.32, wrapper110.45). After
eight receipts and matching intact original-HU shipments, onsite baseline is
restored but retained registry is538 wrappers/12363 tokens. These accounting
tests do not authorize actual heavy motion. External LONG cradle40 kg is a
separate support, not part of1784.29.

Full N0–N4 remains dependent on explicit workload clocks and allocation, paid
relocation with temporary positions, heavy/IN_W/loaded handling proof, LONG
support and shared24-person role transitions. C10's1500 moves are unclocked;
no hourly rate is inferred. Static candidates, local PALLET proof or a merged
ledger alone do not close these requirements.

Future performance work may avoid repeated unchanged-state ledger scans only
with an immutable/revision authority proof that detects untracked mutation,
equivalent conservation tests and actual fresh-process benchmarks. Disabling
invariants is not an optimization permitted by this decision.

## Source references

`app/v3/stock_ledger.py`, `stock_state.py`, `stock_validation.py`,
`execution.py:229`, `execution_state.py:132`, `execution_plan.py:84`,
`light_flow_engine.py:27,225,456`, `light_flow_source.py:69`,
`admission_source.py:50,109`, `workload_materialize.py:28`.

Pinned `data/v3-proposal/docs/v3/contract-proposals/` C02 cargo catalog, C04 slots,
C05 compatibility, baseline assignment, `ports-v3.inbound.json`,
`ports-v3.outbound.json`, `port-resource-policy-v3.json`. Full source audit and
implementation split: the external source audit `v3-inventory-unification-plan.md` (2026-11-08).


## Stage1 implementation boundary and API

`StockLedger` remains the only accounting authority. The new operations are
`receive_hu(transaction_id, expected_revision, ReceiptDefinition, owner_id)`,
`transfer_whole_hu(...)` and `ship_whole_hu(...)`. ReceiptDefinition names a known
initial SKU and new HU/receipt IDs, lot and full recipe quantity. Recipe, unit
mass, outer packaging and unit ancestry are derived from that immutable source
SKU; no caller recipe override is accepted. Multiple HUs may share a lot of the
same SKU/recipe. Reusing a HU/receipt identity or conflicting lot/SKU rejects.
Receipt owners are buffer/worker/vehicle, never an unvisited remote slot.

`ReceiptDelta` extends StockDelta with receipt definition and created tokens;
its before-state is empty and its after-state contains the new physical wrapper.
Existing action deltas and legacy `snapshot()` keep their prior shape.
`inventory_snapshot()` is the new complete inventory view: it includes current
stock, registered receipts, active claims and `claim_generation`. Immutable
source definitions belong to the input catalog; this snapshot is not an event
history. `revision` advances only for actual stock commits. Successful claim
reserve/release/consumption advances a separate generation; reserving or releasing
never credits stock or changes provenance.

`reserve_hu(claim_id, job_id, expected_revision, hu_id)` conflicts with all unit
claims for that HU. `reserve_units(..., container_id, unit_ids)` allows disjoint
SMALL unit claims in one container; overlapping claims reject. `release_claim`
requires the owning job. Legacy pick/transfer/pack/ship/relocate/dispose and new
whole-HU operations check the same claims; authorized consumption uses an
explicit keyword `claim_id`. Unit moves and shipments consume their claim only
after successful commit; authorized material relocation and whole-HU transfer
retain it. Whole-HU claims cannot authorize a partial unit pick. Failed operations
leave claims, stock, history, receipt authority and retry cache unchanged.

`apply_once` accepts exact ReceiveHUCommand/TransferHUCommand/ShipHUCommand
values (`qoima-stock-command-v2-proposal`). It validates types before looking up
an old result, preventing bool/int/Fraction equality from hitting a cache entry.
Identical retry returns the original delta; a changed tick, expected revision or
payload rejects. Other legacy commands remain strict duplicate-ID operations.
The completed_tick is a provenance field, not proof that a physical operation
actually took place. The forthcoming coordinator must exclusively issue commands
at real completed events with matching source admission and leases.

Committed container and location object identities are retained in addition to
immutable recipe/token identities. An out-of-band otherwise valid movement or
numeric-equal type substitution must fail invariants. Full physical-content and
conservation audits still run. This is an integrity extension, not the proposed
future scan optimization, and no performance improvement is claimed.

This stage does not enforce physical slot/module/handler geometry or service
windows by inventing an inventory-only permit. The connected coordinator must
supply those gates. Accounting acceptance for eight classes is not operational
admission for heavy movement. The next required deliverable remains the single
received SMALL HU to three-unit parcel flow with one calendar and actor registry.
