# ADR 0096: Source-bound LONG mechanism interlock

Status: bounded backend component; source-world and physical acceptance remain deferred.

Existing LONG geometry supplies real contacts and mechanisms. It is incorrect to describe
all LONG lock/support geometry as absent. The cached asset revision
`ceacd5180c273796ef34164b3d65e9082272650f` contains
`assets/v3/specs/long-cradle.geometry.json`, `long-cradle.glb`,
`long-restraint-rig.glb` and `long-cradle-loaded-fixture.glb`. C08 remains
`22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4`.
M14.6.3 records bounded loaded contacts and keeper/rig removal/rack-exit sweeps.
M14.8 is an isolated PALLET action. Neither closes the LONG operator installation,
pickup, removal/stow, warehouse route, stability or full N3 process.

## Interface and source authority

`load_long_mechanism_interface(asset_root, requirements)` requires an explicit asset
tree with the repository-relative paths in `long_mechanism_source.PINS`. It never
uses a personal path, downloads, substitutes another model or invokes Blender.
No new binary package is added. Missing or changed inputs fail closed. Deployments
must supply those exact existing source assets separately.

The immutable interface retains all original bytes and their raw SHA256, source
revision, verified LONG requirements, eight joint definitions and contact/mass facts.
For text only, UTF-8 CRLF is converted to LF for the pinned content fingerprint;
no other whitespace, BOM, number or key normalization is allowed. Raw bytes and raw
hashes remain part of interface identity, so LF/CRLF copies have equal mechanical
facts but distinct provenance IDs. Binary SHA256 is strict. JSON is decoded through
existing strict parsers; the existing GLB chunk reader reads node metadata only.
No triangle contact or dynamic proof is recomputed or implied.

Every public check reauthenticates retained raw sources, rebuilds the interface,
invokes `verify_long_freight_requirements` for fresh upstream source authority,
and compares exact nested types/values. Caller-retained hashes or validated flags
cannot replace those checks. The interface is a self-contained raw source snapshot;
subsequent changes to the original asset directory do not alter those retained bytes.
A new load always reads and checks the directory again.

## Mechanical state semantics

`check_long_mechanism(interface, state, requested_mode)` accepts exactly
`loaded_transit`, `empty_cradle_transit`, or `joint_adjustment`. State coordinates
are exact Fractions; all eight original joint IDs must appear once in source order.
Decoded GLB translations and declared nominal pivots are retained separately.

- Two vertical fork pins: `joint__cradle_lock_L/R`, Y translation 0..0.11 m.
- Four upper-rig keepers: `joint__restraint_keeper_{L,R}_{front,rear}`, outward
  X translation -0.35..0 for L and 0..0.35 m for R.
- Two upper bars: `joint__restraint_L/R`, X rotation -80..0 degrees.

Loaded transit requires every joint at zero, upper rig mounted, relative LONG yaw
zero, retracted reach and the C08 0.75 m travel fork top. Adjusting a joint requires
a stopped state. This is a predicate on a declared state, not an inferred transition
history or proof that an operator completed the adjustment.

The original HU/lot, existing actor/vehicle and attachment identities must agree
with the authenticated request. The assembly custody reference must name that
vehicle. This is identity consistency only: it does not authenticate actual ledger
ownership, move stock, mount an attachment, reserve a worker or create a second HU.
The interlock contains no scheduler, clock, operation duration or stock effect.

Empty-cradle transit with the rig mounted is blocked. Even a caller's `stowed`
state and named stow location retains `STOW_AUTHORITY_MISSING`: a physical stow
fixture and its completed transfer are not supplied by this component. Total
attachment mass stays 40 kg including the upper rig; no subpart mass split is
invented. Original HU mass is 200 kg and combined lifted mass 240 kg.

Results report only `mechanically_ready` for the requested declared-state predicate.
`operational_admission`, `full_n3_acceptance`, `stock_custody_verified` and
`physical_action_verified` remain false even when the predicate passes. No caller
may use this result as a route, pickup, installation, stow or shipment certificate.

## Focused verification boundary

Short tests use explicit metadata/GLB-container and upstream-authority doubles with
manual source joint ranges. They exercise each joint, type/ID/custody mismatch,
unknown nodes, corruption, newline provenance and fresh upstream verification.
They do not compile a source world, decode triangles or execute a model/engine.
Real cached header/hash observations establish available source data separately;
the complete public source-requirements path and physical acceptance remain a later
integration gate. No synthetic test authority is available in production.
