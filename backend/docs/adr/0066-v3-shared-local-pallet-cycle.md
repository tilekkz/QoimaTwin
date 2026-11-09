# ADR 0066: Shared-ledger local PALLET cycle prerequisite

Status: Proposed implementation; checks deferred to final assembly by the user's instruction.

## Context and evidence boundary

ADR 0042 proves the pinned local fixed-yaw PALLET fixture geometry. ADR 0046 adds explicit
synthetic rates and two separately checked 5 cm approach/return connectors. Neither proves a
loaded route from IN_W, receipt credit, arbitrary warehouse placement, steering, or a complete
forklift workflow. The standalone cycle's `PalletOwner` is not the warehouse inventory ledger.

The pinned `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` baseline assignment has **no initial HU at
HEAVY_E:001:L1:B1**, although the isolated mesh fixture places its one PALLET there. This is a
scope distinction, not authorization to relocate a source HU or insert a 531st HU. C02 declares
24 PALLET_LOAD units: each is 17.2 kg contents + 0.8 kg primary packaging; the outer wrapper is
23 kg. Thus the intact HU is 455 kg, with outer dimensions 1.20 x 1.35 x 1.00 m.

## Decision

Introduce `PalletSharedEngine` in native namespace `qoima-shared-local-pallet-v3-proposal-1`.
It subclasses `WholeFlowEngine` and uses its actual pending heap, worker map, `StockLedger`,
inventory claims, belt and observation clock. It never constructs `PalletCycleEngine` or a
second scheduler, worker map, ledger, or mutable PALLET-owner mirror.

The first version accepts only a declared `analytical_hand` inventory with `source_revision=None`.
The existing PALLET must already be represented by the exact C02 wrapper and 24 original unit
tokens in that inventory at the proved platform. `UNSUPPORTED_SOURCE_INITIAL_PLACEMENT` rejects
source-mode claims. `UNSUPPORTED_PALLET_RECEIPT`, `UNSUPPORTED_PALLET_CLASS` and
`UNSUPPORTED_PALLET_SLOT` distinguish other unsupported requests. A local cycle cannot create
tokens, receive a new HU, infer a loaded route, or claim full-source PALLET throughput.

F01 starts explicitly seated in FL01. Its declared home is an isolated logical moving-frame
anchor with no pedestrian arcs; this assumption is required input. Actual exact vehicle pose is
observed separately in `pallet_fixture_local`. Constant human-frame coordinates do not stand for
a free approach, driver walking, steering, boarding, or proof of human contact. The two optional
source connectors are the already proved local 5 cm segments only, not an IN_W route.

Each paid `HumanStep` corresponds to one operation from `build_cycle_plan`; the retained proof
is independently validated against raw pinned geometry, and optional connectors use
`build_bridges`. The shared calendar drives all operations. Future planned finishes remain
plans at a cap; completed stock transactions occur only at actual attach/release completion.

The exact whole-HU inventory claim and exclusive F01, FL01, platform, HU and local action-space
leases are acquired atomically before execution. Optional bridge resource IDs join this set.
The platform lease is retained even while the PALLET is carried. `_place_free` therefore rejects
receipt/whole use of the temporarily empty platform. At attach completion the real ledger moves
the existing HU to `vehicle:FL01`; at release completion it returns it to the platform. Claim,
platform and driver reservations persist until the actual safe return. Repeated requests use
FIFO `(ready_tick, job_id)` and the same original HU, never a clone.

The only common-engine extension is `_additional_whole_ownership()`, empty by default. A native
subclass first validates its real operation, worker, pose, claims, resources and ledger custody.
The parent rejects overlaps with existing whole work, then invokes the common receipt/stock
checker once with the combined authority. Existing light/receipt/whole scheduling is unchanged.

## Horizon, observations and compatibility

As in the shared light/whole engines, every offered local request arrives strictly before H;
new admission at H is forbidden. Admitted operations and paid returns drain to the end cap.
This deliberately differs from the standalone ADR 0046 component's arrival-at-H vocabulary.
Waiting, unadmitted requests remain backlog; receipt service windows retain their existing
shared-engine rules. State at H includes actual completions with tick <= H. Paid exposure is
clipped to [0,H), and business release precedes safe resource return.

Distinct native events/snapshots expose all 24 workers, shared stock/claims/leases, local job
progress and the one vehicle pose/active operation. The outcome retains the geometry proof,
profile digest, explicit engine version and end limit. The profile digest is not a published
run ID and does not establish full physical A/B sameness. Old whole codecs are not a serializer
for this extended snapshot. No CLI/API/exporter is added here. Capability flags explicitly say
shared inventory=true, source inventory binding=false, PALLET receiving=false, full warehouse=false,
operational admission=false. The latter preserves the distinction between a runnable analytical
fixture and a proved warehouse production operation.

## Hand oracles written before execution

Using declared root=1 m/s, lift=0.52 m/s, reach=0.4 m/s, attach=0.2 s, release=0.3 s and hold=1 s:

| Case | Independent expectation |
| --- | --- |
| Local cycle | attach 3.25 s; release 10.65 s; safe home 13.7 s |
| Two local cycles | second admission 13.7 s; safe home 27.4 s; one HU, 24 original tokens |
| Two optional 5 cm connectors | attach 3.30 s; release 10.70 s; safe home 13.8 s |
| H=3.25 s, two requests | attachment included; second request remains unadmitted |
| Cap=11 s | PALLET on platform; F01 still paid and reserved; claim retained |
| H=5 s / cap=6 s | reach=0.1 m at H; root_z=-0.75 m at cap; planned finish6.3 s uncompleted |
| Added SMALL whole dispatch | S01 ships37 s, returns42 s while F01 finishes13.7 s |
| Receipt + three-unit order + PALLET | receipt credit12 s/place23 s/return33 s; parcel ship192.17 s/home197.17 s |

Local stock is 24 SMALL + 24 PALLET units and 0.25 kg empty materials: 456.19 kg. Adding a
24-unit SMALL receipt credits 0.94 kg, giving 72 units and 457.13 kg. Shipping three SMALL units
in a 0.05 kg parcel gives 0.155 kg shipped and 456.975 kg onsite. These are explicit hand fixtures,
not a claim about the original 530-HU source inventory.

Authored tests cover these arithmetic oracles, actual concurrent R/S/P/K/F work, claim/resource
corruption, a hidden paid operation after completion, exact typed inputs, retained authority,
and unsupported scope. RED/GREEN and static execution remain deferred, not claimed passed.
