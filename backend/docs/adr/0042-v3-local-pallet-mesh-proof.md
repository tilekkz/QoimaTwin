# ADR 0042: Independently verify the pinned local PALLET mesh action

Status: backend proposal; isolated geometry prerequisite, not operational admission.

## Context

ADR0036 preserves declared source vehicle restrictions but grants no physical
mesh proof. M14.8 publishes a local pickup/place path and native Blender checks.
Its `visual_fixture` and `engine_operation=false` declarations remain authoritative.
The backend now decodes the actual low-fixture GLB and independently recomputes
the bounded geometric obligations. No source mesh or shared contract is changed.

Inputs are the seven immutable files in `data/v3-mesh-proof-proposal`, pinned to
`1fcb775c4b7737745130c9efa87ba18e4b52dd09`. Its separate provenance does not replace
the V3 operational source pin `22296bc`. The only binary is 818,836 bytes with
SHA-256 `b172dc6dd245208a49fdddebccd6ff5d64cc3771c4e0259dabdd633adbd2808a`.

## Decision

Use stdlib GLB2 decoding and the existing NumPy dependency. The supported subset
is one embedded buffer, indexed float32-position triangle primitives, a unique
rigid node tree and unit scale. Reject unsupported compression, skinning, morphs,
animations, sparse accessors, external buffers, invalid indices/strides, duplicate
JSON keys, nonfinite data, shared/cyclic nodes and unreferenced geometry.
Matrix and quaternion rigid residual is bounded by 1e-6; matrices are retained,
not silently normalized. Semantic joint/frame residual is bounded by 2e-6 m.

Exact duplicate positions reunite normal/material seams. Connected components
are checked for paired opposite edges, positive signed volume and triangle area.
No tolerance welding or binary repair occurs. The actual GLB contains one exact
collinear triangle in mesh `Cylinder.041`, despite the native polygon check.
The generic decoder rejects degeneracy by default. This hash-bound source opts
into retaining exact-collinear faces: their lines remain in collision covers,
their zero surface measure contributes nothing to winding/contact area, and
closed topology is still required. Nonzero near-degenerate faces are rejected.

The published fourteen pose keys become thirteen dimensionless intervals. Each
interval interpolates root translation, carriage lift and reach extension;
attachment is fixed throughout its open interval and changed at the boundary.
The same HU node is used on both sides, with coincident floor pose. There is no
clock or warehouse speed in the proof API. Visual seconds bind the source file
but are not returned as operational duration.

For each solid, endpoint AABB hulls enclose its entire affine translation.
Wheel covers contain the full radial revolution. Fork covers contain complete
triangles in blade, heel and corner groups. This strengthens the native check:
four actual bevel triangles have vertices in the blade/heel union but interior
outside it. The separate corner cover retains that real surface in every check.
General chassis rotation and nonrigid motion are outside this method's scope.

Check full interval covers against actual platform triangles and closed-solid
winding, plus floor and action-space limits. When HU is fixed, check vehicle
covers against HU. When attached, remove common root, then carriage, then reach
translations and check each remaining relative interval. This avoids comparing
unrelated world sweeps while retaining all actual relative displacement.
Vehicle mechanism self-contacts, structural deflection and friction are outside
this proof; it covers vehicle/HU versus platform and HU versus vehicle.
Triangle/open-box SAT uses an inset of 3e-7 m, consistent with the original
defining module. Contact/frame residual is separately 2e-6 m. SAT projection
roundoff is 1e-12 and inactive-axis squared threshold 1e-22.

Compute opposing horizontal triangle intersections as finite convex polygons.
Edge-only contact is rejected. Overlapping positive-area contact polygons are
rejected rather than counted twice. Area resolution is 1e-12 square metres.
Both forks need positive area; the declared CoG projection must lie strictly
inside their combined support hull. The platform is checked similarly. Record
measured area, centroid, gap and support margin; do not substitute nominal board
dimensions or sampled rays. This is quasi-static support under vertical gravity,
not acceleration, strength, stability-at-speed or OEM certification.

The result binds method version, every input hash, actual triangle/component
counts, each declared motion interval, contact measurements and numerical scope.
`operational_admission` remains false. The 0.05 m source-route/action-start gap,
IN_W supported pickup fixture, actual warehouse obstacles/leases, driver actions
and paid operation timing still require separate execution work.

## Validation

Independent hand fixtures precede implementation: closed box/touch/penetration,
contained hull, mid-interval tunneling, SAT AABB false positive, invalid solids,
finite rectangular contact, edge-only/offset/overlapping contacts, CoG margin,
binary offsets/hierarchy/hash/unsupported modes and the concave fork bevel case.
The repository actual-source test verifies all thirteen intervals and actual
contact patches from the GLB. Tests contain no engine-derived expected timing.

## Sources

- [Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- Bound `pallet-pickup-cycle.json` and forklift/PALLET/HEAVY dimension documents.
- Bound native `verify_pallet_pickup.py` and `build_standard_carton.py`, retained
  as read-only text. The backend does not rely on their assertions or PASS flags.
