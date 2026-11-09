# ADR 0082: Conditional source F02/FL02 operator fit

Status: accepted as a bounded geometry proposal; no operational admission.

## Context

ADR0079 retains an unproved seated-F02 prerequisite for the E011 pickup. The
source policy has distinct inbound F01/FL01 and outbound F02/FL02 pairs. The
existing worker-base mesh and forklift specification supply a common unchanged
driver body and seated pose. An old inbound certificate is insufficient evidence
for this pair. The external 2026-11-09 probe recomputed nine positive checks and
ten rejected controls against the actual source meshes.

## Decision

Add only new `pallet_operator_fit_*` modules and a separate worker asset package
under `backend/docs/proposals/pallet-operator-fit-v1`. The package contains one
original raw GLB and pinned provenance, not a regenerated body, old PASS report,
new worker, or amendment to the existing seven-file mesh supplement. Its authority
binds historical Git revision/path/blob SHA-1/length/SHA-256 and independently the
existing forklift specification's worker fingerprint. Filesystem paths locate
bytes; they do not establish source identity.

`load_operator_fit_source(data_root, worker_root)` returns immutable raw source
bytes plus the existing authenticated `PickupSource`. The source hash binds both
and the complete worker provenance. `certify_operator_fit(source, pickup_plan)`
revalidates all source bytes and the exact ADR0079 plan before computing new
evidence. It explicitly checks the outbound direction, original 24-actor inventory,
F02/FL02 pair, unchanged body template and scale. No inbound certificate is reused.

`verify_operator_fit_certificate(source, plan, retained)` recomputes the geometry,
compares exact typed canonical records, and returns a fresh immutable certificate.
Rehashing false evidence, Boolean/numeric aliases, changed IDs, changed raw source,
different proposed motion and expanded scope do not confer authority.

The source seated pose uses intrinsic Euler XYZ with unit scale. Rigid transforms
are copied; the original body triangles remain unchanged. Five actual body anchors
are compared to actual vehicle anchors and to source targets: seat, both soles and
both steering grips. Actual seat and roof solids are uniquely matched by decoded
mesh bounds to their named source boxes. Actual horizontal triangles must form
positive finite pelvis/seat and two boot/support patches.

All 57 complete body solids receive conservative local boxes checked against all
68 actual vehicle solids. These are whole-solid covers rather than vertex samples.
The proposed six pickup intervals are bound by the verified plan hash. With the
body fixed to the vehicle root, common root translation cancels. Conservative
affine covers check complete carriage/reach/fork movement relative to the body;
full-radial envelopes cover wheel rotations. Endpoint-only checks are insufficient.
The method keeps source minimum helmet/roof clearance 0.045 m and anchor tolerance
2e-5 m. Existing numerical policy remains: open-interior inset 3e-7 m, contact/frame
residual 2e-6 m, minimum contact area 1e-12 m². No physical threshold is relaxed.

The source E011 vehicle prehandle plus source body offset yields conditional body
root `[122.585, 0.29, 29.5]`. This is a derived frame relation under the specified
pose and vehicle location, not a measurement of actual initial placement. The
portal check is only the seated body's Y/Z projection through the declared lateral
portal. It is explicitly not a walking, climbing or boarding trajectory.

## Limits

Every certificate retains false flags for operational admission, actual initial
state, boarding path and travel admission. It certifies conditional source-template
geometry only. It does not establish F02 availability, approach, actual presence,
FL02 availability/lease, loaded route/steering/traffic, cargo/body or warehouse
clearance, body CoG, dynamic restraint, ergonomic or strength ratings, paid time,
stock custody, B2B support or handoff. ADR0079's zero approach gap and unresolved
C08 relative-yaw binding remain unchanged. Its existing certificate is not edited.

The six affine component checks do not turn the pickup plan into a runtime action.
No engine, scheduler, HTTP/API, GUI, source DES or operational clock is added.

## Validation

Tests precede implementation and first fail on missing new modules. Independent
closed-box tests cover exact touching versus 1 mm penetration and a moving body
collision present only between clear endpoints. Actual source perturbations cover
floating/penetrating seat, raised foot, insufficient roof gap, displaced grip and
portal failure. Raw/provenance tampering, wrong source pair, mutated typed metadata
and rehashed fake contacts reject. Source location changes preserve identity.
The owner gate checks strict Windows/Linux-target mypy, Ruff, and functions shorter
than 50 physical lines. Runtime admission and full N1 acceptance remain separate.
