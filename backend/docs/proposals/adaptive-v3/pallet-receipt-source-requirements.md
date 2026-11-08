# PALLET receipt: source geometry and process proposal

Status: proposal for backend/frontend coordination; not an adopted contract or an executed
receipt. Canonical `contracts/` and Tilek's `frontend/` are unchanged. See
[ADR0070](../../adr/0070-v3-source-pallet-receipt-prerequisites.md).

The current pinned sources identify intake ports, finite staging counts, actor/vehicle
pairs, a directed vehicle graph and cargo/vehicle dimensions. Those facts do not locate an
actual staging support or establish that forks can enter beneath a staged PALLET. A service
node is an interface anchor, not an invented physical storage surface.

The existing local PALLET proof concerns `HEAVY_E:001:L1:B1`. The source baseline has no HU
there. A new receipt must obtain its own identity and be credited exactly once at a defined
completed handoff; the template HU is not moved or cloned. A separate local analytical
fixture must not be presented as source receiving.

## Minimal source additions to agree

| Record | Required fields | Purpose |
| --- | --- | --- |
| Physical staging position | Stable position/support IDs, raw model reference and SHA256, XYZ/yaw, actual support/contact height, footprint and payload bound | Locate one of the already finite source positions |
| Staged PALLET pose | Cargo orientation and actual pose, fork-access channels and clearances, contact surfaces | Establish pickup feasibility without passing through solid floor |
| Vehicle access | Stopped root/front-axle pose and yaw, directed connector geometry, allowed fixed pair/cargo/profile, action-space and traffic resources | Connect the position to the actual source vehicle graph |
| Pickup/handoff action | Continuous action phases, attachment/release boundaries, two-fork contact and retention proof references | Establish supported custody transfer rather than a teleport |
| Loaded routing | Actual loaded-model envelopes, permitted facing/reverse transitions, stop and steering obligations, mixed-traffic reservation references | Preserve cargo geometry through turns and corridor transitions |
| Receipt process policy | The completed action that credits inventory, joint receiver/driver/vehicle ownership, which phases belong to the source intake service, separate explicit movement/handling clocks | Prevent double credit, free labor or double-counted port service |

Do not populate missing support height with the target platform's height, reuse an empty
vehicle sweep for loaded travel, or create a new worker/vehicle to satisfy the process.
These records can use explicit proposed geometry, but it must be marked as an assumption
until independently checked and agreed; it is not a newly discovered source fact.

## Backend integration boundary

The authored prerequisite compiler binds fresh pinned source bytes, the prospective receipt
definition, current target occupancy, finite port resources and directed route obligations.
Its metadata does not add stock. The authored local setdown primitive begins with an
already-loaded vehicle and therefore does not prove port pickup. An additional loaded
entry sweep must be computed independently of the existing empty entry proof.

Only a complete chain may authorize receipt credit and shared-clock execution:

1. Valid new identity and exact cargo recipe.
2. Available physical staging position and a defined credit/handoff boundary.
3. Supported pickup with actual receiver/driver/vehicle leases.
4. Loaded connector, route and turn coverage with paid operation clocks.
5. Supported setdown into a reserved target, followed by paid release and safe return.

The current proposal exposes explicit missing-proof reasons. New proof calculations,
runtime execution and final validation are pending. It makes no all-class, N2, performance
or frontend-adoption claim.
