# ADR 0079: Source-bound E011 pallet pickup geometry

Status: accepted as a bounded geometry proposal; no operational admission.

## Context

The original `v3:HU:initial:DEMO_172:01` contains 24 PALLET_LOAD units at
`v3:slot:HEAVY_E:011:L1:B1`. The outbound pair is F02/FL02. ADR0042 verifies
an isolated mesh fixture, while ADR0066 deliberately limits its runtime to a
different F01/FL01/E001 analytical job. ADR0070 does not grant outbound pickup.
Renaming any of those certificates would lose the actual source binding.

The independently retained E011 V5 data/geometry packet established a finite
candidate: pickup the source HU and withdraw loaded to its actual prehandle.
Its six continuous intervals and contact areas are test oracles here. Source
traffic, B2B receiving support, runtime timing and physical retention remain
separate work.

## Decision

Add only `pallet_outbound_pickup_*` modules. They authenticate all 24 files and
three provenance manifests of the pinned base, vehicle and mesh packages.
Inputs retain immutable raw bytes; every public plan/certificate validation
checks SHA-256, byte lengths, Git blob ancestry, exact document universe and
order. No caller-supplied source hash substitutes for those checks.

`load_pickup_source(data_root)` returns an immutable `PickupSource`.
`compile_pickup_plan(source)` derives one `PickupPlan` for the original HU,
slot, actor and vehicle. `certify_pickup(source, plan)` verifies the exact
plan, decodes the actual GLB, and recomputes the complete bounded geometry.
`verify_pickup_certificate(source, plan, certificate)` recomputes that evidence
and compares exact typed canonical records. Boolean/integer/Fraction aliases,
changed record types, duplicate IDs and rehashed false assertions reject.
The canonical unit names follow the existing `stock_source.source_seed`
original-HU ordinal convention; this code creates no stock or custody state.

The local-to-world frame has yaw `pi/2` and origin `[124.2,0,29.5]`.
The source prehandle is local root_z `-1`, world `[123.2,0,29.5]`.
C02 signed HU axes are aligned with the module, whose world yaw is `3*pi/2`.
Therefore the derived HU node has local `R_y(pi)`, rather than the old
fixture's identity rotation. Original triangles, scale and hierarchy are
preserved. The original fixture frame is validated before deriving this
explicit new binding. Source pose checks use the existing 2e-6 m residual.

The proposed dimensionless states `(root_z, fork_top, reach)` are:

```text
(-1,.70,0) -> (-1,.70,.40) -> (-1,.18,.40) -> (0,.18,.40)
           -> (0,.70,.40) -> (0,.70,0) -> (-1,.70,0)
```

Attachment changes only after insertion, with coincident HU pose. The HU
retains source yaw throughout. These states are an explicit proposed policy;
they are not source-measured poses or operational timestamps. Source C08
supplies the fork/reach design values, not execution of this sequence.

Reuse the existing whole-interval affine cover, relative-motion, full-wheel
envelope and finite-contact helpers. All six intervals must pass. Both forks
need actual positive-area contact and the declared CoG must be within the
combined support hull; original platform support is checked separately.
Other module operating bounds, all other original HU boxes and the source
envelope are checked conservatively. The loaded endpoint must fit C08
component boxes and match the first reverse arc's root/axle/yaw seam.

## Explicit limits

At the lowering pose the extended fork tip and nearest HU face have nominal
zero fore-aft separation. The numerical open-interior collision check accepts
that boundary. Moving 1 mm inward produces actual blade/HU triangle intrusion.
This is not positive approach clearance, a robust pickup or a safety margin.
The contact support-hull margin is a different quantity. If an applicable
handling rule requires positive fore-aft clearance, this six-step variant
fails that requirement; changing the rule is not allowed. Existing slot
placement clearance, route padding and collision/contact tolerances remain
unchanged.

The certificate explicitly retains `operational_admission=False` and
`positive_fore_aft_clearance=False`. It does not establish seated F02,
available FL02, a loaded route, traffic reservations, dynamic occupancy,
operation durations, paid accounting, ledger transfers, partial runtime caps,
retention/strength/rating, or B2B support and handoff. Relative HU-to-vehicle
yaw remains pi; matching component bounds is not a semantic travel grant.
The same pinned C08 builder rejects `relative_yaw_rad != 0` or nonzero tilt
with `ORIENTATION_FORBIDDEN`. It does not derive that job field from absolute
source HU/vehicle poses, so the nominal load-frame binding still needs an
explicit resolution. The certificate records geometric relative yaw pi and
`not_admitted_pending_C08_relative_yaw_frame_binding`. It neither waives the
zero-yaw rule nor asserts an unproved mapping of the job field to mesh axes.
Builder source evidence is commit `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`,
`tools/visual/v3/build_vehicle_handling.py`, lines 193–203, raw SHA-256
`8291404c8c7ad9caf44e5f5ddc1f143996610a66e37bdbc329a1a0b510efb8d7`.
The C08 document already pins that builder hash; the verifier adds no new
runtime policy choices or source files.
Mechanical self-contacts and dynamic stability remain outside ADR0042's
underlying proof scope. No engine, scheduler, API or GUI is added or invoked.

## Validation

Tests were authored before implementation and first failed on the absent
new module. Independent V5 expectations cover exact source identities,
proposed states, six interval counts, nine contact observations, all 131 other
module and 529 other HU bounds, and endpoint/C08 seam. Physical negative cases
retain inward-1mm, low loaded travel, blocked lane, raised support, missing
fork, discontinuous attachment and old HU heading. Additional tests alter raw
source bytes, exact types, identities and rehashed plan/certificate content.
A fresh subprocess confirms that the public verifier imports no scheduler,
coordinator, local pallet runtime, SimPy or stock ledger.

This focused evidence does not claim a full source execution or a full V3 gate.
