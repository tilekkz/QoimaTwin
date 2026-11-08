# ADR0056: intact manual SMALL/STANDARD work on the connected inventory clock

Status: backend proposal, bounded typed runtime and typed source binding. This does
not extend the approved shared frontend contract or introduce a public JSON/CLI API.

## Context and decision

ADR0050 protects the original wrapper and ancestry; ADR0053 connects SMALL receipt
to unit picking on one ledger and calendar. The next operation must share those
objects. `WholeFlowEngine` extends that existing loop, with the same 24 workers,
StockLedger, cart and belt. It does not run or join another ManualEngine timeline.
The native version is `qoima-whole-flow-v3-proposal-1`; observations add whole-order
stage facts to native receipt observations. Legacy light/receipt publications keep
their versions and public admission policies.

WholeFlowProfile supplies intact whole orders, selected outbound ports and finite
places, positive pickup/place ticks, and the complete explicit ReceiptFlowProfile.
Only SMALL_CARTON and STANDARD_CARTON execute manually, with one eligible S01/S02
and gross mass <=min(15kg,declared actor capacity). R01/R02 can receive those classes
on this new version. The old receipt entrypoint still accepts only SMALL; STANDARD
unit picking remains forbidden. Other source classes remain inert original stock.

One `actor:<id>` owner of kind worker and capacity one represents actual custody.
`StockLedger.relocate` keeps its old material/workstation-only policy. The separate
`transfer_material_to_worker` operation reuses its CAS, claims, rollback and commit
path, but explicitly permits worker custody for a carrier/package only. The new
engine's protected material hook selects it; old engines retain old relocation.
No caller force flag, duplicate S01 owner or implicit material pool is introduced.

## Conservative service reservation and time

Arrival/admission is [0,H). Receipt service must finish <=min(H,source window end);
completed intake can put away and return after H. A future whole outbound job cannot
admit until actual putaway. Once admitted, outbound service may finish after H but
must finish within the actual source port window and requested end cap.

At a finite outbound buffer, the job reserves the source service bay and a finite
shipped-owner position *before* picking the buffer HU and paying the buffer-to-port
approach. It holds the bay through service completion. This intentionally conservative
policy avoids an unimplemented appointment scheduler. Service duration excludes
approach and queueing. Observations report port reservation exposure separately from
actual service exposure; both are integrated on [0,T). Future openings wake before
pickup/approach so service can start exactly at the opening. The final completion
at a window end is eligible; one microsecond later is not.

Whole jobs and ready parcels compete for the same eligible actor by effective-ready
tick, offered arrival and stable job ID. A worker remains occupied through paid home
return. Business completion is actual intact-HU shipment, not the later worker return.
Counts use settled state after all events with tick<=T; planned future ends stay plans.

## Physical custody, finite resources and claims

Admission atomically reserves the actor, a finite buffer and an intact whole-HU claim.
The source slot remains occupied until actual pickup. The same original wrapper moves
slot -> worker -> buffer -> worker -> shipped; no unit split, recipe substitution or
new ancestry occurs. Buffer capacity releases at completed buffer pickup, the service
bay at completed service, and the worker only at home return. Finite shipped capacity
is reserved before the port approach and also blocks competing parcel handover.

Stage checks derive expected HU owners from completed operation facts, including
unassigned baseline HUs and future received HUs. Until receipt putaway, the receipt
checker remains authoritative. The whole checker then extends it with exact expected
custody and outstanding claims, not a blanket exception for whole-job IDs. Balanced
but unperformed ledger moves, removed claims/resources and missing carried-HU motion
observations are rejected. Claim retirement at shipment never removes ancestry.

## Source binding and limits

`bind_whole_source` first verifies exact pinned source types, canonical document bytes
and hashes using the existing authority guard. It derives baseline530HUs/12256units,
source slots/worker anchors, port service/windows, and conservative initial+allfuture
module mass. Initial outbound slots must be active/manual-compatible; future target
slots must be unique, initially free and compatible. Source count ceilings alone do
not prove geometric fit. Explicit BufferChoice paths use the existing exact swept
rectangle checks, actual outbound cell bounds and declared payload/clearance.

On a fresh verified walk graph only, C09's pedestrian/manual-carry intent is projected
to SMALL/STANDARD where BOTH cargo whitelist and support fields are absent. Explicit
false, explicit empty/nonmatching whitelist, modes, direction and geometry are kept.
New checked synthetic connector arcs receive those same bounded manual classes.
The policy `c09-manual-small-standard-source-mode-projection-v1`, complete augmented
graph, full source/material catalogues, process choices and initial inventory are
frozen together; no graph cache or event history is serialized as immutable inputs.
Caller graph/stock/slot/service placeholders are derived outputs, not overrides.

Source pin22296bc: `data/v3-proposal/docs/v3/contract-proposals/cargo-catalog-v3.json`
records0/1 give SMALL24units/.94kg and STANDARD24units/6.35kg. `ports-v3.inbound.json`
IN_N_STANDARD gives STANDARD18s, one bay, four staging HUs split between west/east
zones, and the horizon-intersection rule. `ports-v3.outbound.json` OUT_W_RETAIL gives
SMALL25s/STANDARD35s, one bay, six exact cells and the shared S01/S02 pool. C09 manual
access does not grant forklift admission. No source1500/hour rate, replenishment,
mesh hand-contact proof or global collision-free pedestrian model is inferred.

## Independent arithmetic and boundaries

Hand graph: H-slot2m, slot-buffer3m, buffer-port4m, port-H5m, speed1m/s;
pickup/place1s. Whole pickup3, buffer place7, buffer pickup8, service begins12.
SMALL ship37/home42; STANDARD ship47/home52. Two actors/two buffers/one bay:
SMALL reserves7..37; second STANDARD reserves37..77 and returns82, with actual
service25/35 seconds versus reservation30/40 seconds. With one buffer, the second
job admits only at first completed buffer pickup8.

STANDARD receipt graph: home-port2m, port-buffer3m, buffer-slot5m, service18s.
Credit20, putaway31, receiver home41; same-HU whole ship78/shipper home83. H20 can
credit and put away but cannot admit outbound31; H19.999999 cannot credit. These
values were recorded and accepted before implementation.

Mixed hand flow: original STANDARD starts160, ships207, returns212; a ready SMALL
parcel then uses the same S01, ships238 and returns243. Total stock48units/7.54kg
=onsite21units/1.035kg +shipped27units/6.505kg, including explicit .20 carrier and
.05 parcel tare. The source-layout proof reports observed clocks separately; those
measurements are not substituted for analytical expected values.

Remaining scope includes other handling classes, IN_W, all6ports/N0-N4 execution,
actual vehicle/contact proof integration, allocation/replenishment, public whole-run
publication/replay/API and broader coupled workflow source scenarios.
