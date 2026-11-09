# ADR0081: One source-bound E011 loaded reverse arc

Status: Accepted for geometry evidence only; travel is not admitted.

Date: 2026-11-09

## Decision

Extend the completed ADR0079 pickup evidence by exactly one original directed
arc, `v3:module:HEAVY_E:011:B1:vehicle:segment:002:r`, for existing
`v3:HU:initial:DEMO_172:01` and F02/FL02. This is an independent bounded geometry
primitive, not a route runner, timed job, reservation, ledger effect or ordinary
B2B process. No existing source or pickup file changes.

Public functions are `compile_arc_plan` and `verify_arc_plan` in
`app/v3/pallet_outbound_arc_plan.py`, and `certify_arc` and
`verify_arc_certificate` in `app/v3/pallet_outbound_arc_verify.py`. They require
the exact ADR0079 `PickupSource`, `PickupPlan` and `PickupCertificate`.
`ArcPlan` and `ArcCertificate` are frozen typed values with canonical typed
identities. There is no caller-selectable arc, yaw, clearance, stop permission,
timing or alternative stock.

Every public compilation or certificate verification revalidates all27 retained
raw source/provenance documents against pinned bytes/Git ancestry and recomputes
the pickup's actual mesh certificate. Certificate verification additionally
recomputes the entire first-arc proof; saved hashes or caller-rehashed metadata
are not an authority cache. Exact typed comparison rejects retained bool/int,
float/int and bool/Fraction aliases even when their Python values compare equal.
The source package is an immutable portable raw-byte value; local paths are not
its identity and are not needed to verify it again.

## Source binding and continuous motion

The start is the authenticated pickup's final high/retracted attached state.
The raw arc must retain PALLET_LOAD cargo permission, C08 cargo eligibility,
OUTBOUND_FORKLIFT_PAIR, the original component profile, reverse sign, constant
source yaw and zero steering. Its exact source-decimal length is
`0.7917096231345369 m`; there are no invented seconds or rates.

The root moves from `[123.2,0,29.5]` to
`[122.40829037686547,0,29.5]`. Front axle remains `.4 m` along vehicle local+Z,
from `[123.6,0,29.5]` to `[122.80829037686547,0,29.5]`. The source frame is
origin `[124.2,0,29.5]`, yawπ/2. Local root z moves from−1 to
−1.7917096231345369. Fork top remains.70m, reach0. The original HU world yaw
remains3π/2, with unchanged relative R_y(π); its24 original unit IDs remain
bound through the pickup plan. No normalization or rotation is used to satisfy
an admission rule.

The actual source GLB is decoded again. Existing `mesh_proof_*` continuous-cover
and contact helpers, ADR0079 source-frame/scene/coordinate helpers and the
original-HU box derivation are reused. The primitive proves the whole affine
interval through conservative complete-triangle covers, full wheel envelopes,
and common rigid translation of all carried solids. Finite contact patches on
both forks and their declared-CoG support hull are checked at both ends; the
unchanged relative transform preserves them throughout the interval. Recomputed
pickup endpoint containment plus constant relative translation preserves the
same C08 component bounds. This is quasistatic geometry, not dynamic retention
or structural certification.

## Static obstacles and padding

All132 original module operating boxes, including E011, and529 other original
HU boxes are checked against the complete arc sweep with unchanged source.25m
horizontal padding. The moving HU is excluded from the stationary set only under
the explicit completed-pickup precondition. Its original raw assignment is never
edited or replaced. Floor/layout bounds, horizontal envelope padding and original
.25m top padding are checked independently.

The existing2e-6m frame/bounds residual and3e-7m open-interior collision inset are
unchanged. Module/HU bounds are conservative original static geometry only;
workers, other vehicles, offered receipts, temporary stock and traffic ownership
are outside this certificate. All these exclusions remain explicit limitations.

## Signed-frame policy boundary

Both plan and certificate report
`NOT_ADMITTED_PENDING_EXPLICIT_PALLET_SIGNED_FRAME_BINDING` and
`operational_admission=false`. The destination node's absent `stop_allowed`
remains `None`; no following steering change or stop is granted.

At pinned source commit `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`, C08's
`tools/visual/v3/build_vehicle_handling.py:202–203` rejects a nonzero declared
`job.relative_yaw_rad` or `relative_tilt_rad` as `ORIENTATION_FORBIDDEN`.
The builder SHA256 is
`8291404c8c7ad9caf44e5f5ddc1f143996610a66e37bdbc329a1a0b510efb8d7`, also recorded
by that commit's `docs/adaptive-v3/evidence/C08.json`. Constancy of a nonzero
declared scalar is insufficient.

However, that function consumes a caller scalar and does not derive it from a
source PALLET world pose or signed attachment matrix. Its literalzero fixture
at line288 and L05's explicit identity load axes refer to LONG. A PALLET-specific
nominal signed attachment transform and physical-to-job-field mapping are not
provided. If the field denotes actual signed HU-to-vehicle yaw, this preserved
R_y(π) state fails the zero rule. There is no source-backed basis to relabelπ as
zero delta from an alternative nominal frame. This ADR preserves the ambiguity
as an admission boundary; it introduces neither a waiver nor a new policy.

## Scope and verification

The original pickup's nominal zero fore-aft lowering gap remains a limitation.
This primitive grants no positive handling approach margin, other9 arcs, turns,
dynamic retention/lock, actor availability, traffic leases, timestamps, paid
return, stock custody or B2B support/handoff. The proposal example is an explicit
declaration of the one conditional case, not an executable warehouse profile.

Focused tests first recorded missing-public-module RED, then verify literal
source geometry and preserved pending policy, rehashed plan/certificate/source
corruption, exact-type aliases, actual low-fork intrusion, missing support,
root/axle confusion, horizontal/top padding and actual proof recomputation.
No engine, source DES, HTTP, GUI or full-suite execution belongs to this change.
