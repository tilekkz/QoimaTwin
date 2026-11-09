# ADR 0045: Bounded connected SMALL picking, conveyor, packing and shipping

Status: accepted backend implementation decision; V3 proposal, not a shared contract agreement.

## Context and source boundary

The immutable `22296bc` V3 proposal provides stock, directed access paths, L08 conveyor geometry,
station anchors and port service rules. ADRs 0037/0040 provide the finite conveyor model; ADR 0041
provides conserved unit/container ownership. Running these independently cannot establish one
physical pick-to-ship workflow or backpressure across human and conveyor handoffs.

The base input bundle contains 14 files. Conveyor geometry and cell membership are a separately
verified immutable supplement. The source binder records both sets of raw hashes and the revision.
It replaces template stock, worker/cart source anchors, directed graph, L08 service anchors,
conveyor route and outbound port rule with those authoritative inputs.

This slice executes SMALL units only. All 24 worker identities remain in the roster; P01, K06 and
S01 perform work. Other identities retain declared logical homes, without claiming collision-free
placement of 24 human meshes. The source example preserves all 530 initial HUs and 12,256 units.

## Decision

`LightFlowEngine(profile, conveyor).run(horizon_tick, end_tick)` coordinates human and conveyor
work on one integer microsecond clock. The frozen standalone belt implementation is unchanged;
`FlowBelt` supplies explicit admission, station and output orchestration. At a tick, actual due
completions settle before deterministic dispatch reaches a fixed point. Invariants run after
settlement. Future planned completions remain plans, never observed ownership changes.

Every material recipe, initial carrier/wrapper quantity, handling duration, human/cart speed,
finite handoff owner and route clearance is explicit. No V2 tote count or service duration is
inherited. Constructor validation checks actual initial material pools, unit placements, full gross
mass including tare, loaded paths and the complete future parcel conveyor route. It rejects
missing owners/materials, unknown references and shortcut routes that omit physical intake/output.

The picker and cart start together. The cart is exclusive through its paid return. At source slots
whose cart stop differs from the worker point, paid parking, detachment, pedestrian empty-carrier
access, picking, loaded return and reattachment connect those points. No cart enters a pedestrian
terminal. Route filtering uses declared transport modes, carried width plus twice the explicit
clearance, and carried height plus clearance. This is a logical envelope check, not human mesh,
grip, whole-cart swept-volume or traffic collision proof.

Unit transfer is atomic at completed picking service. Intake cells are reserved before paid
deposit; ownership and actual belt admission change only when deposit completes. Carrier identity
is the declared material ID, while unit tokens preserve original HU, SKU and lot ancestry. Two
orders may take different units from one HU without duplicating that original HU on the belt.

The station retains physical reservations while awaiting its real packer. A declared wrapper moves
to the finite bench at packing start; units enter the sealed parcel at packing completion. Paid
clearing moves the empty carrier into a finite station rack and loads the parcel at the current
belt pose. The parcel's dimensions and gross mass are revalidated against the remaining route;
expanded occupancy is acquired before clearing. Elapsed motion prefixes and prior events remain
immutable. Empty carriers stay in the rack; this slice does not invent a return/reuse process.

The final belt footprint stays occupied through shipper approach and paid pickup. Pickup completion
releases cells and transfers the parcel to the shipper. Business completion is completed outbound
port service; the worker's paid return finishes later. A full declared shipped owner blocks service
before it starts and keeps the parcel with the shipper. Port service must fit an actual declared
window, including completion exactly at its end. Source OUT_S_EXPRESS uses its SMALL 20-second rule;
applying that rule to these SMALL parcels is the explicit process classification for this slice.

New order admission is strictly before H. Already admitted workflows and paid returns drain after
H, subject to actual port windows and the end cap. Queued orders that never gain admission remain
backlog. State at H/end includes all actual completions at that tick. A partial operational result
can have all business shipments complete while a worker is still returning.

Human paid ticks include actual travel and service, clipped to the observation. Human waiting is
separate. Belt queue exposure means stopped-carrier time: waiting for a worker and paid output
pickup while the body still occupies cells both count. Active movement, pivot, packing and clearing
do not. This named exposure must not be presented as pure unpaid queue time.

Immutable current-state checkpoints are captured at zero, every settled 30 seconds, and actual
end/cap. Optional `on_tick_settled(snapshot, last_seq)` exposes every settled tick for an external
compact replay journal. The engine does not put whole stock snapshots into native events or infer
earlier state from final state. The callback is opt-in; invariants are always enabled.

## Independent arithmetic and recipes

The hand graph declares distances 2 m home-to-slot, 3 m slot-to-park, 1 m park-to-intake, 2 m
packer approach, 2 m shipper approach, and 3 m output-to-port, with 1 m/s speeds. Attach, park,
detach, deposit, pickup and clearing each take 1 second; picking takes 1 second per unit and
packing 3 seconds. These are synthetic timings, not measurements from the source or engine.

For three SMALL units, paid picker stages end at 1, 3, 6, 9, 10, 11, 12 and 13 seconds; its
return ends at 20. Source conveyor edge arithmetic gives 30.915448 seconds to the PK06 stop and
116.254552 seconds after clearing to output. Station arrival is 43.915448; approach, packing and
clearing end at 45.915448, 48.915448 and 49.915448. Output is 166.17; pickup completes 169.17,
port arrival is 172.17, shipment completes 192.17 and paid return ends 197.17 seconds.

Two orders with distinct initial carriers/wrappers deposit at 13/33 seconds. The second reaches
output at 186.17, waits for the shipper until 197.17, is collected at 200.17, ships at 223.17 and
finishes its return at 228.17. Stopped-carrier exposure is 5 seconds for one order and 21 for two;
paid P01/K06/S01 time is respectively 20/8/31 and 40/16/62 person-seconds.

Each primary unit weighs 0.035 kg. Three units weigh 0.105; carrier tare 0.20 gives loaded 0.305,
and parcel tare 0.05 gives sealed 0.155. Original HU mass 0.94 includes retained outer tare 0.10.
One-order conservation is `0.94 + 0.20 + 0.05 = 0.835 + 0.20 + 0.155 = 1.19 kg`.
Two-order conservation is `0.94 + 0.40 + 0.10 = 0.73 + 0.40 + 0.31 = 1.44 kg`.

The hand carrier is explicitly 0.60 x 0.34 x 0.40 m. The source-bound example separately declares
a synthetic 0.32 x 0.24 x 0.24 m carrier, with 0.20 kg tare; it is not a resized M07 asset. Its
choice does not prove that a 0.60 m carrier fails the source's actual 0.70 m worker connector.
The source-bound example uses real graph paths, not the hand graph's shorter distances. Its mass
is the conserved initial 9403.85 kg plus the explicitly introduced 0.25 kg materials, or 9404.10 kg.

## Limits and follow-up

This is a runnable bounded logical workflow with real finite belt backpressure, not full N0-N4
warehouse execution. Heavy workflows, multiple active pickers/stations, replenishment and empty
carrier circulation are outside this slice. Source allocation is explicit, not an invented demand
fulfilment policy. Packaging bench/rack placement and paid logical handling are declared
assumptions.

Latest upstream hand-control work describes two primary units and leaves reach/pick work pending.
The three-unit logical service here does not establish finger contact, gripping, reach or visual
animation correctness. A canonical tote-at-cart workflow needs a separate explicit primary-unit
carrying/ownership and hand-contact recipe. Public profile parsing, publication, metrics and replay
are separate integrations that consume this engine's frozen typed inputs and actual settled state.
