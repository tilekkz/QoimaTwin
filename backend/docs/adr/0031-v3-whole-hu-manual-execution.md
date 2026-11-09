# 0031. Explicit whole-HU manual execution proposal

Status: backend proposal for a bounded executable V3 slice. This does not approve or implement
the complete V3 contract, conveyor, vehicle, picking/packing, staffing-calendar or scale model.
Upstream source proposals remain immutable. The execution profile is a separately versioned,
explicit synthetic input; unclocked baseline move expectations never generate timed jobs.

## Inputs and capability

The profile preserves all 24 actual actor IDs with explicit graph homes, receive/ship skills,
speed and mass limits. Inactive actors remain present with no relevant skill. Every port binds
actual eligible IDs; each job uses one actual worker. No implicit carts, totes, packaging,
forklift or new workers exist in this slice. The profile binds the graph layout version and
SHA256 exactly and records source fingerprints and synthetic-assumption provenance.

Preserve all declared initial HUs and quantities, including inert heavy inventory. Only an
executed job is restricted to a complete SMALL_CARTON or STANDARD_CARTON HU with known positive
gross mass at most 15kg, within its actual worker's limit. No split, repack, SKU substitution
or implicit HU creation occurs. Every HU originates once in initial stock or a timed receipt;
the same received HU may have a later outbound job. One place holds at most one whole HU.
Positive exact XYZ dimensions must fit the supplied fixed upright place envelope and payload.
The source compiler separately checks original placement/orientation and manual admission.

All 530 baseline HUs, all 200 SKU and all eight archetypes can therefore remain represented
even when only a light manual job executes. A heavy initial slot need not have a walk anchor;
only a manually executed slot must. Original graph-qualified source references are validated
by the compiler, not replaced with invented walk anchors.

Every job has an explicit integer arrival tick, direction, HU, port and storage slot. All
arrivals lie in [0,H). The profile supplies positive local pickup/place durations separately
from source port service. Workers use ADR0026 exact length/speed with one microsecond ceiling
per travel operation; service and handling already have explicit integer durations.

## Route and stage semantics

Directed pedestrian graph candidates are the only travel paths. Every leg starts at the
worker's actual current node, and every return to the declared home is paid. Missing paths
leave an explicit no_route wait; no straight-line or reverse-arc fallback is created.
The compiler must expose and hash any added local connector geometry with its synthetic
provenance and validation limits. Upstream compiled walk graphs currently lack port-buffer
access nodes; a port service point cannot silently stand in for a remote staging cell.
Exact augmented graph_document nodes/world poses/arcs are also required by the exporter.
Candidate reachability alone does not establish loaded route or collision admission.

Inbound operations are: empty approach to port, intake service, carry to reserved buffer,
place, pickup, carry to reserved storage approach, placement, empty return home. Outbound
operations are: empty approach to occupied stock, pickup, carry to reserved buffer, place,
wait for bay/window, pickup, carry to service, shipping service, empty return home. Port
service excludes travel. Internal local pickup/place times are explicit synthetic assumptions.

Dispatch sorts (arrival_tick, job_id), then eligible actor ID and compatible buffer ID. A
blocked earlier job may be bypassed by an independent feasible later job; priority is stable,
not a promise that a blocked queue head globally stops the warehouse. Atomic acquisition
checks a complete currently needed set before any reservation, using stable resource ordering.
Initial dispatch reserves the worker, HU and buffer; inbound also reserves destination slot
and its imminent service bay. Outbound acquires its bay only at the buffer before pickup,
loaded travel and service. It retains the worker while waiting there.

Release the service bay immediately at service completion, buffer after actual pickup,
source-slot occupancy after pickup, target-slot reservation after actual placement and HU
lease after placement or shipment. Only the worker lease continues through the paid return.
This preserves finite capacity without incorrectly blocking ports or buffers during return.
No shared actor performs two port jobs simultaneously. Traffic intersection/edge capacity
scheduling is outside this manual slice and is not claimed by these resource leases.

## Clock boundaries and honest outcomes

For both inbound and outbound, service start is inside an open window and service completion
must be <= min(window_end,H). Exact equality at the end is accepted. This explicitly resolves
the unspecified inbound completion boundary and the outbound prose 'before window end' as a
finish-by condition. A reservation includes the required approach/pickup travel when checking
the window; a job never assumes instantaneous arrival at the service point.

No new job dispatch occurs at tick>=H. Already admitted internal putaway and return work may
drain after H to a separately supplied finite end cap. At H and end, observe all events with
tick<=boundary, following completion, arrival, dispatch and checkpoint phase ordering. Future
planned motion end ticks remain plans, never completed events. Waiting, moving or returning
jobs make status partial. Complete requires all jobs and paid returns completed.

at_horizon.tick is always H. If complete before H, at_end.tick is the last actual operational
event (zero for an empty run); at_horizon is a later observation of the same settled state.
Otherwise complete end is the final actual event after H, or the explicit end cap if partial.
The requested end cap belongs in exported identity separately from observed completion time.

Inbound arrivals blocked outside are explicit outside ownership, with no warehouse inventory
credit. At every settled tick, initial+arrived = outside+stock+warehouseWIP+shipped per SKU;
initial+admitted = stock+warehouseWIP+shipped. Admission occurs when intake service starts.
Every HU has one owner; workers, bays and buffer places are exclusive. These checks also run
initially and at returned end, and raise explicit exceptions under Python optimization.

## Independent evidence and limits

On H-P-B-S with separately declared reverse arcs, distances2/3/5m, speed1m/s, port service10s
and each pickup/place1s: inbound stock at23s and paid return33s; outbound shipped31s and
return33s. These are direct hand arithmetic. Separate shared-worker/three-port and finite
buffer tests use their own declared small graphs. Real-source compilation and demonstration
must preserve source hashes and geometry labels; it cannot convert static planning distances
into an independent performance oracle.

Manual events carry explicit job/worker/owner/lease changes for deterministic replay. Integer
ticks are authoritative; exact Fraction distances remain exact. MANUAL_ENGINE_VERSION is
independent of V2 ENGINE_VERSION. No throughput or complete V3 capability claim follows from
this slice, and no frontend/shared contract changes are made by this ADR.
