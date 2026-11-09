# ADR0063: concurrent unit workflows on one physical coordinator

Status: proposed implementation, isolated C-stage; not an N4 acceptance claim.

## Context

ADR0059 B2 proves actual helper packing on one goods station and cart. The V3 brief
retains twelve picker identities, six packing stations and shared receiver/shipper pools.
Changing the singleton FlowProfile during concurrent work would silently change existing
routes, custody and resource ownership. Multiple engines would duplicate the clock and stock.

## Decision

The new coordinator namespace accepts explicit immutable UnitResources alongside the
existing common world and Registry A. It lists six GoodsStation values, actual UnitCart
values, all twelve PickerBinding identities, ParcelPort values and exactly one UnitAssignment
for every unit order. The assignment fixes picker, cart, station, shipper and port; there is
no implicit fallback or optimization policy. This is a declared allocation, not evidence of
full physical A/B input identity. Empty cart eligibility means no compatible declared cart;
an assigned cart must be in that picker's explicit eligibility list.

Every station has a distinct local bench, empty-carrier rack and package material pool.
The package pool is co-located with the station for the declared local preparation operation.
Each cart has a carrier material pool at its home; carts may share that pool only at the same
home. Material recipes and placements remain explicit. No hidden replenishment or carrier
reuse is introduced. Future source compilation must bind these physical locations explicitly.

One authoritative cart-state map stores actual positions and open operations. Legacy
cart_node/cart_operation properties reference its default cart, rather than another state.
The new coordinator snapshot publishes every cart. Old light/receipt/whole codecs are not
used to publish this new namespace and must not silently discard additional cart state.

Each order uses an immutable FlowProfile view for pure planning and validation. The engine's
common profile is never temporarily swapped. Prospective validation uses one ledger across
all orders and declared receipts; it does not create independent credits for each view.
Public old validators remain strict. An internal coordinator-only validation seam supplies
the actual unit bindings; serialized input cannot supply a validation callback.

Admission considers waiting orders in (arrival_tick, order_id) order. An order may proceed
when its declared actor and cart are actually returned, available, eligible and free and
its exact stock claim can be acquired. A blocked assignment does not block a different
independent actor/cart pair. Actor capabilities alone do not grant admission. A picker whose
home differs from the cart home pays the directed approach and return legs. The cart remains reserved through actual cart return and the explicit declared release
handling duration. It then releases independently while a different picker home may still
require paid walking. UnitCart requires an explicit release_tick; the hand fixture declares
zero additional handling after the existing completed return, without inferring a source norm.
The actual cart_released_tick/event records this boundary; the worker stays busy until home.

The shared finite intake reservation is acquired before paid deposit. Packing retains B2's
atomic local bench/rack/material/target-footprint reservation and actual clear boundary.
Whole-HU and parcel shipping share the same worker states, readiness ordering and physical
port namespace. Each declared parcel port's windows and shipped owner must agree with any
whole-HU definition of that port. Port service may finish exactly at its closing time. A held named parcel-port lease is also
its promise of one shipped position, until actual handoff. The common whole-flow
_owner_usage includes placed containers, whole-HU promises and these parcel promises.
The coordinator resolves each parcel promise through its immutable actual port/owner view;
there is no second inventory or independently mutable capacity-reservation map.

Initial unit/whole admission remains strictly before H; admitted work and paid returns drain
on the existing calendar, while future receipt offers remain uncredited. Staffing role
requests, actual ownership release and helper restoration retain ADR0059 semantics. No
second worker map, scheduler, ledger or conveyor is introduced.

## Hand acceptance fixed before execution

The explicit hand graph and declared materials are synthetic. Source conveyor edge lengths
and ceiling arithmetic yield PK05 prefix50.915449s/suffix96.254551s, and PK06
prefix30.915448s/suffix116.254552s. The one-microsecond asymmetry is retained.

Two arrivals at80s, one cart/picker, deposits93/113s reach PK05 at143.915449s and PK06
at143.915448s. Helpers P11/P12 pack3s and clear1s, then restore at160s. Outputs244.17/264.17s
and one actual S01 give shipments270.17/301.17s, final paid return306.17s. The same common
break without helpers makes both primary services start162s and clear166s; outputs
262.254551/282.254552s give shipments288.254551/319.254551s and return324.254551s.
At H300 both variants have shipped three units, not six. Total24 source units and six
distinct picked units, including wrappers/materials1.44kg, are conserved.

A second declared cart/picker can have simultaneous paid picking and disjoint exact-unit
claims. Shared intake, belt, station and shipping capacity still apply. Additional tests must
cover all six goods stations, all twelve picker assignments, concurrent port use, actual
role returns and H/end boundaries before claiming the corresponding coverage. No source
throughput, all-archetype warehouse completion or human hand-contact proof is asserted.
