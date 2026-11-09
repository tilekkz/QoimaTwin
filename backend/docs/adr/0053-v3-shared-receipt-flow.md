# ADR0053: one calendar and stock authority for SMALL receipt-to-shipment

Status: backend proposal; bounded typed runtime. Source binding is a separate ADR0052
compiler. No shared frontend contract or full V3 execution claim is changed.

## Context

ADR0050 adds receipt registration and protected whole-HU custody to the existing
StockLedger. Accounting permission alone does not perform physical receipt work.
Joining a manual-engine history to a light-engine history would duplicate initial
stock, actors and clocks. The first connected extension must operate on the same
ledger, existing 24 actor objects, cart, belt and microsecond calendar.

The pinned inbound proposal explicitly intersects its service window with the
supplied horizon. A common clock therefore does not imply a common inbound and
outbound service deadline. Source service duration excludes approach, local buffer
handling, putaway and return. External deliveries are not warehouse inventory yet.

## Decision

ReceiptFlowEngine extends the existing LightFlowEngine calendar through narrowly
scoped initialization, calendar, dispatch, stock-pick and observation hooks. Normal
LightFlowEngine profiles retain their event vocabulary, ordering and semantics.
There is no second simulation loop, duplicated worker pool, or concatenated history.
The native version is `qoima-receipt-flow-v3-proposal-1`; its output includes receipt
views and the complete ADR0050 inventory snapshot. It is not a legacy light run.

ReceiptFlowProfile explicitly declares ports, finite single-cell buffers, target
slots, receiver IDs, arrival definitions, and positive pickup/place durations.
It embeds the full original FlowProfile, including all stock, material recipes,
actor homes/speeds/capacities and existing process choices. Future ReceiptDefinitions
remain separate from the immutable baseline. `validate_receipt_flow(profile,
conveyor)` uses a separate prospective ledger for physical-content preflight and
returns a clean live ledger with zero revisions, receipts, claims or history.
Prospective units are never inserted into `flow.stock` or exposed as live inventory.

This first operational slice accepts only SMALL_CARTON receipts, max15kg including
all tare, and the declared R01/R02 receiver pool. Other seven accounting-supported
classes remain inert baseline inventory or are rejected as receipt jobs. Loaded
travel requires a directed graph route with declared cargo clearance; absent reverse
arcs fail. Neither a straight-line shortcut nor a remote buffer teleport is supplied.
The source compiler must bind actual source geometry, module ratings, service
windows, receiver pool and local connectors. Hand profiles remain explicitly
synthetic and do not certify source-layout physical geometry.

## Time and credit

Every new job is admitted in [0,H). Receipt service must finish <=min(H,window end).
Approach may occur before the opening; dispatch wakes at opening minus paid approach.
An exact boundary completion is credited. Completed receipt service may be followed
by putaway and paid return after H, bounded by the requested end cap. The downstream
order is admitted only after actual putaway, and only before H. Already admitted
outbound work follows its own source window and can drain after H.

Receipt credit is a single ReceiveHUCommand at service completion. Before that
instant the offered HU is outside the warehouse registry. Credit creates its exact
immutable ancestry once and places custody at `actor:<receiver>`. The same intact
wrapper then moves to buffer, back to receiver at physical pickup, and to the target
slot at physical place completion. The existing pick/pack/ship operations consume
its exact unit IDs from this ledger. The residual original wrapper remains in its
slot; neither wrapper disposal nor material replenishment is implicit.

The single global event sequence describes operation starts/completions, stock
transactions, receipt state changes, inventory claims and resource transitions.
Snapshots include settled state after events with tick<=T. Planned future operation
ends remain plans when an end cap clips motion; no future stock delta is emitted.
StockDelta/ReceiptDelta observations are transaction-level; physical consistency is
checked after the whole tick settles, not between adjacent same-tick events.

## Resources, waiting and claims

Admission atomically reserves an idle shared receiver, a free finite buffer, the
empty target cell, and the future HU identity. The bay is acquired only when actual
service starts. Bay release occurs at service completion; buffer reservation ends
only after physical pickup; target and whole-HU reservation end at putaway. Only the
receiver remains leased through paid return. Reservations and actual occupation are
checked together so a different HU cannot occupy a reserved cell.

Two receivers can approach one port concurrently but cannot overlap its service.
If queueing makes the next service miss its source deadline, the job remains an
explicit waiting, uncredited external delivery with its actual acquired resources
until the end cap. This first version has no invented cancellation or truck-return
operation. Such a run is partial. ReceiptView.paid_exposure_ticks integrates the
receiver lease, including waiting, on [0,T); existing FlowWorker.paid_ticks retains
its active-operation meaning and queue_ticks exposes waiting separately.

Credited whole HUs remain claimed until putaway. A downstream pick claims its exact
unit set at order admission and consumes the claim with the actual pick transaction.
At settled ticks the coordinator checks receipt custody, shared-worker ownership,
staged resource leases, whole-HU and pending exact-unit claims, operation-to-plan
consistency, unchanged baseline-wrapper custody, and SKU conservation:
initial plus credited receipts equals all registered onsite/shipped stock. The
ledger retains its full independent immutable-authority and conservation audit.
No invariant-skipping optimization is introduced.

## Hand oracles fixed before execution

The receipt graph has home-to-port2m, port-to-buffer3m and buffer-to-slot5m, with
explicit reverse arcs, speed1m/s, service10s, and each place/pick1s. It produces
credit12s, buffer place16s, buffer pickup17s, putaway23s and receiver home33s.
The unchanged three-unit light fixture is admitted at23s: pick29s, intake36s,
picker home43s, shipment215.17s and final shipper home220.17s. Total active human
work is92s = receiver33 + picker20 + packer8 + shipper31.

The hand stock starts with24 units/.94kg and explicit materials.20+.05kg. Receipt
adds24 units/.94kg. Final total48units/2.13kg equals onsite45units/1.975kg plus
shipped3units/.155kg. The new residual source HU contains21units and its.10kg
wrapper, totaling.835kg. Initial HU1 is unchanged.

H=12s credits the receipt and permits putaway/return drain; H=11.999999s does not
admit it. End cap20s retains actual receiver custody and a planned22s travel end.
A future [5,15]s service window dispatches at3s, credits15s, puts away26s and returns36s.
A declared home at the service point pays zero approach, then credits10s, puts away21s
and returns29s. With two receivers and one buffer, the second admits17s, credits29s,
puts away40s and returns50s. With two buffers and one bay, both admit0; the second
waits10s, credits22s and returns43s, with33s active work and43s paid lease exposure.

## Limits and next integration

This milestone connects receipt and existing SMALL shipment at the runtime layer.
Actual source compiler verification, public publication/replay/API support and the
global integration gate remain separate. It does not implement IN_W/heavy handling,
all6ports/all8classes, N0-N4, automatic replenishment, slot reuse after empty-wrapper
removal, or source-layout collision certification. A conservative declared finite
buffer subset is not proof that every source buffer count fits arbitrary HU geometry.
