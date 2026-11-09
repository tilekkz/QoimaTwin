# ADR 0032: Frozen synthetic whole-HU manual execution profile

Status: accepted for the bounded backend demo proposal, not full V3 admission.

The pinned V3 package defines static stock, typed geometry and source-labelled
synthetic local port durations. It does not supply a timed scenario, complete
operator homes/skills, or all local handling durations. Unclocked expected moves
cannot generate arrivals. The backend must make those missing choices explicit
before creating the engine or comparing placements.

Compile the independently versioned `manual-whole-hu-demo-v1.json` against the
unchanged 22296bc source bundle. Preserve all 530 baseline HUs, 200 SKU, 12,256
units and 24 original worker identities. Retain unsupported stock as inventory;
only SMALL_CARTON and STANDARD_CARTON whole-HU inbound/outbound jobs are admitted.
No splitting, totes, carts, extra handlers, vehicles, packing or conveyor process
is implied. Reserve and nonmanual addresses reject runnable jobs.

The demo freezes four jobs: source DEMO_001 HU01 and DEMO_111 HU01 ship at 0/60s;
two new synthetic receipt HUs, cloned explicitly from those source HU templates,
arrive at 0/60s. Receipts use initially free SMALL_W017 L1B1 and STANDARD_E016 L1B1.
The new HU identities do not replace baseline identities or consume their stock.
Each receipt carries the source SKU's entire 24-unit HU; no wrappers are added.
H=600s, end cap=900s, calendar=`fixed-explicit-arrivals-v1`. These are demo choices,
not measured demand, a rate model, or a throughput benchmark.
Calendar timestamps use the same microsecond ceiling as operation durations:
for example, an explicit arrival at 1.0000001s becomes tick 1000001. Positive
fractional ticks cannot create an earlier arrival; integer-microsecond inputs
remain exact. This policy is part of the frozen profile materialization.

All 24 actor IDs/homes/skills/speed/mass are explicit proposal records. R01/R02
receive at IN_E_PARCEL; S01/S02 ship at OUT_S_EXPRESS. The other 20 actors remain
idle, unskilled for this slice, at the real typed PK01 service node. Homes and
eligibility are synthetic choices, not source-provided worker schedules. Speed
is the V3 1.3m/s pedestrian assumption; the F3 1.4m/s fixture is unrelated.
Synthetic pickup and place operations each take 2s. Actor mass capacity is 15kg.

Reuse source local durations: IN_E_PARCEL SMALL10/STANDARD14s and OUT_S_EXPRESS
SMALL20/STANDARD30s, with source [0,28800)s windows. These source values are
themselves labelled synthetic, not measured. Service excludes approach, waiting,
buffer transport, putaway, return and their separately timed handling operations.

Use one finite compatible buffer place at each selected port, a conservative
synthetic reduction from each source ceiling of eight. OUT_S_EXPRESS preserves
source cell08, centred (39,5), 1.2m square. IN_E_PARCEL uses an explicitly new
1.2m square centred (130,59), contained in its allocated staging zone. Height1.2m
and payload15kg are synthetic restrictions for these places. Service anchors are
keep-clear and cannot hold parked inventory.

The source compiled walk graph has no staging-cell nodes. Add only these explicit
bidirectional polylines, in floor XZ metres:

- IN_E_PARCEL: (138,54), (138,63), (130,63), (130,59); length21m.
- OUT_S_EXPRESS: (48,6), (48,8.8), (40.5,8.8), (40.5,5), (39,5); length15.6m.

Validate each axis-aligned leg's swept rectangle with radius0.4m against building
bounds, every prohibited zone and every rack's conservative outer bounds. Only
circulation and that port's staging zone may be traversed. Buffers must lie in
allocated staging and outside all protected approaches, be mutually disjoint,
and have access that avoids other modelled buffers. Reject precision loss when
serializing synthetic geometry into compiled JSON numbers. No straight fallback
or alias of a remote cell to a service node is permitted.

Carry admission requires width0.7m and height1.8m. Width covers the largest .6m
carton axis plus .05m each side. The local connector corridor is conservatively
.8m wide/2.2m high. Existing source pedestrian paths include .7m widths. Prove
directed reachability for relevant service/buffer/slot/home anchors and require
the engine's actual mode-only shortest route to equal the clearance-filtered
route. Missing clearance rejects. This is bounded declared geometry admission;
no actor collision, ergonomics certification or full traffic allocator is claimed.

Slot fit uses exact source decimal geometry with twice source per-side clearance
removed from each usable axis. Observe source manual/reserve flags. Conservatively
check module payload against all initial stock plus all receipts, without relying
on earlier shipments. Inactive heavy stock retains typed pedestrian observer
anchors; these grant no cargo handling permission at those addresses.

Hash canonical source fingerprints, full synthetic proposal, exact augmented
graph, layout hash, H/end and calendar/jobs using repository qoima-json-v1.
The graph document carries connector provenance and is returned immutably for
export; reconstruct DirectedGraph from those exact bytes. Freeze operator choices
before a comparison and reuse the same materialized jobs. Engine version remains
an independent run/export binding owned by ADR0031.

Verification is the hand geometry/clock oracle, actual-source compiler rejection
checks, reproducible full materialized profile and actual-source ManualEngine run
with per-SKU conservation. This decision authorizes no full N0-N4/all-eight-class
claim. Relocation, reserve retrieval, heavy/forklift work, splitting, packing,
conveyors, automatic slotting and forecasts remain unsupported processes.
