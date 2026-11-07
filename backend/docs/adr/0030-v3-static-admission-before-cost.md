# ADR 0030: Exact static admission before V3 placement cost

Status: accepted for the isolated backend V3 proposal; shared contracts are unchanged.

## Context

The pinned V3 design brief requires compatibility before assignment scoring. C04/C05 retain
the cargo dimensions and mass, allowed upright orientation, finite slot and module payload,
conditional handling options, and blocked reserve retrieval. Geometry alone is insufficient.
F2 independently requires rejecting two 8 kg boxes on a 15 kg support even when their dimensions
fit. C04's FRAGILE boundary has height .95 m plus .10 m clearance in a 1.05 m useful envelope.

## Decision

`app.v3.admission` evaluates adding one complete HU against explicit frozen cargo, slot,
current occupancy and handler capabilities. It returns stable reason codes in physical order:
reserve access, permitted archetype, orientation, dimensions, aggregate payload/HU capacity,
module mass, handler and service height. It does not evaluate cost or acquire resources.

Only the canonical upright local XYZ mapping is supported by this slice. The internal name
`xyz` maps to the source `upright_xyz` / `upright_xyz_in_module` pair; module world yaw is
separate. No reflection, tipping or new yaw permission is inferred. Exact dimensions include
the source `dimension + 2 * clearance <= usable` budget on all axes. Cargo rests on the support
plane with zero bottom gap; the complete vertical clearance budget remains above the HU.

All numeric inputs are finite Decimal values. Arithmetic precision is derived from their
decimal exponents before addition/subtraction, independent of a caller's decimal context;
there is no epsilon tolerance. Unknown mass, inconsistent occupancy and invalid numbers fail
closed. Handler capability is an explicit input, never an assertion of a free worker or vehicle.

The separate candidate composition requires a trusted loaded-route proof bound to layout,
complete cargo parameters, slot identity and complete handler parameters. A missing, stale or
unreachable proof rejects `PATH_CLEARANCE`. This is an internal composition boundary: an API
client cannot certify a route merely by submitting `reachable=true`. The route evaluator must
produce that proof from the pinned graph and load restrictions. No network or source mutation
occurs during evaluation.

## Scope and consequences

`eligible` means the stated static checks passed. `operational_admission` and `cost_evaluated`
remain false. Source-specific conditional equipment/support checks must be applied by the input
adapter before constructing a handler. This function neither supplies missing forklift support
evidence nor schedules a job. Reserve remains inaccessible. Multiple-HU occupied-volume packing
requires its own arrangement proof; aggregate mass/count alone does not establish nonoverlap.
Current pinned source slots allow one HU, and the F2 multiple-box case is an analytical witness.

Tests use source and hand values, including exact clearance excess, slot/module aggregation,
handler/height exclusions, stale route bindings, and altered global decimal precision. This
addition leaves V2 engine constants and the 32.8 / 469 / 474 s regression unchanged.

Sources: Tilek revision `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`,
`docs/adaptive-v3/brief/02_DESIGN_V3.md` sections 5 and 8,
`docs/adaptive-v3/specs/C04.md`, `C05.md`, and their exact-byte contract proposals.
