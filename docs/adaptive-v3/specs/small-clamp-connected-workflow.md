# SMALL clamp connected workflow

Status: frozen native outbound and original receiving implementation, 2026-11-10.
This is a technical contract for the visual fixture. Engine operation and force
certification remain false. Scenario admission must separately check concurrent
Source/LONG and other warehouse flows.

## Source identity and finite equipment

The unchanged outgoing request is `v3:request:base:outbound:01`, whole HU
`v3:HU:initial:DEMO_001:01`. The unchanged original incoming request is
`v3:request:base:inbound:01`, whole HU `v3:HU:incoming:DEMO_001:01`.
Both retain 24 units, 0.94 kg and dimensions `[0.32, 0.24, 0.24]` metres.
The incoming port is `IN_E_PARCEL`, actor `R02`, including the raw N1 request.
No supplemental request, inventory capacity or substitute STANDARD carton is
created by this workflow.

The unchanged SMALL outbound request uses `OUT_S_EXPRESS` in all four current
raw scenario inputs, including N1. `OUT_W_RETAIL` / S01 is an optional
engineering route variant verified by the isolated native checker; it is not
the current N1 input. The common Page derives the port from the actual raw
request and must not rewrite it. In N1, STANDARD and SMALL can both require
the same finite S02 employee, so a complete SMALL workflow can legitimately
wait beyond the 1800-second horizon. An unadmitted outbound case requires
`PROVED_SMALL_OUTSIDE_HORIZON`; its incoming dependency then remains
unavailable. Input mismatches do not qualify as scheduling refusals.

The one finite tool is `v3:tool:small-clamp:01`, 2.5 kg including its remaining
hardware allowance; the whole carried assembly is bounded by 3.44 kg. Tool
geometry has 27 closed components, with a component mass sum of
2.215982766518823 kg at the declared aluminium density of 2700 kg/m³. The
remaining allowance is 0.284017233481177 kg. This is a geometric mass bound,
not a force, friction, structural or manufacturer certificate.

| Source | SHA-256 |
| --- | --- |
| `frontend/public/models/v3/worker-base.glb` | `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` |
| `frontend/public/models/v3/small-carton-clamp-tool.glb` | `7ea46c6c8dee3bf443e0c22656c832665cb4820c39dc3a9c9b668fdd543e5aac` |
| `warehouseSmallClampManualTransfer.ts` | `8334fd798114ab36cb5ca5bff2ce84f2f51f6f6d0354a0c606a7c18e718054c3` |
| `warehouseSmallClampReceivingWorkflowRoute.ts` | `38da5cb2ca6c4902fbf1dffeeb9ae4f68db28afde8404fa2754aac36d20767d2` |
| `warehouseSmallClampReceivingTransfer.ts` | `77c0d17417fff5e129d2eac31827db20669090ec1f0350b0c65b9ce2c6199bcb` |

The original character mesh, body scale, mittens, rack and carton remain
unchanged. The engineering tool's thin jaws, empty telescopic insertion,
85 mm lift, 350 mm whole-HU extraction and adjustable handle provide the
new physical path. Its empty stow root is `[73, 0.92, 4.8]`, yaw π, on the
actual `V3_SPUR02_1` conveyor deck at PK02.

## Issued API

```ts
const outboundRoute = createWarehouseSmallClampWorkflowRoute(bundle, policy, {
  port_id: 'OUT_S_EXPRESS', // use the raw request; OUT_W_RETAIL is optional
});
const outbound = await createWarehouseSmallClampManualTransfer(
  scene, bundle, outboundRoute, { readSource, signal },
);
const receivingRoute = createWarehouseSmallClampReceivingWorkflowRoute(
  bundle, policy, { native_manual_dependency: outbound },
);
const receiving = await createWarehouseSmallClampReceivingTransfer(
  scene, bundle, receivingRoute, { readSource, signal },
);
```

The corresponding types are `WarehouseSmallClampWorkflowRoute`,
`WarehouseSmallClampManualTransfer`,
`WarehouseSmallClampReceivingWorkflowRoute` and
`WarehouseSmallClampReceivingTransfer`. Each has an `isWarehouse…` issuance
guard. Guards use private WeakSets; copied DTOs and copied tool-token objects
do not inherit admission.

Both native factories expose `request_id`, `handling_unit_id`,
`participant_actor_ids`, `duration_s`, `phases`, `phase_rows`, `leases`,
`tool_token`, `sample`, `apply`, `snapshot`, `reset` and `dispose`.
Both have `partial_native_case: false` and `supports_visual_completion: true`.
Receiving additionally exposes `actor_id: 'R02'`, `receipt_at_s`,
`stored_at_s`, `dependency.native_manual_case`, `terminal_buffer` and
`extra_materialization: null`.

`sample` is pure and uses local absolute seconds. `apply` mutates the actual
native scene and returns a diagnostic snapshot. Samples contain the same
whole HU identity, actor frames, tool frame and visibility/ownership state.
Native snapshots add actual world transforms, pad/bar gaps and actor counts.

## One tool and full recovery dependency

Outbound and receiving expose the identical opaque `tool_token`. A private
WeakMap binds it to the identical scene and actual tool root. At most one
receiving action can retain it. The shared controller is the only tool-pose
writer, and references retain the tool, native source sampler and template
until the final disposal.

Outbound follows P01 → PK02/K02 → the selected shipping employee → finite
outbound held-HU footprint → downstream boundary. The employee keeps the
empty tool, returns it to PK02 and recovers home; K02 also returns home.
Receiving readiness is this **full outbound end**, including tool stow and
participant recovery. Dispatch alone does not release the tool dependency.

Receiving acquires that recovered tool, carries it to the original finite
`IN_E_PARCEL` footprint and receives the unchanged whole incoming HU at an
explicit supplier boundary. Supplier animation is not represented. R02
carries the HU to the original outgoing slot
`v3:slot:SMALL_E:019:L1:B5`, reverses the checked native source trajectory,
releases the stored HU, returns the same empty tool to PK02 and returns home.
The target slot, orientation, payload and module mass are checked against the
tracked fixture. Actual insertion refuses if the outgoing source instance has
not physically been hidden.

For each absolute scene update:

1. Apply the outbound local time first. This deactivates the incoming overlay
   and restores R02 before any outgoing restoration.
2. Apply receiving after its admitted start. `receiving.apply(t > 0)` requires
   the outbound controller to be physically at its full end.
3. When receiving is inactive, `receiving.reset()` restores only its receiver
   and incoming HU. It stows the tool only while its own controller owns it.

The tool ledger contains one resource/token row. Select the receiving tool
frame after receiving starts; otherwise use the outbound frame. An outbound
sample at its full end remains the immutable historical stow frame while
receiving owns the actual physical tool.

Reverse seeks apply the same ordering. Disposing outbound before receiving
is supported: it releases its reference while the receiving holder retains
the actual tool and native resources. Final release restores the original
530 HU instance matrices and original actor parents.

All connector gaits start from the preceding actual native gait's final
heading. Their turns therefore consume native time and keep actor, tool and
cargo transforms continuous. Completed phase callbacks receive the exact
declared phase duration, avoiding a lost downstream handover caused by
floating point subtraction at cumulative boundaries.

## Duration and deadline accounting

| Variant | Outbound full recovery | Receiving full recovery | Earliest absolute full end from request time 120 s |
| --- | ---: | ---: | ---: |
| OUT_S_EXPRESS / S02 | 1268.5324263940768 s | 687.0816642786192 s | 2075.614090672696 s |
| Optional OUT_W_RETAIL / S01 | 1534.6433328791024 s | 687.0816642786192 s | 2341.7249971577216 s |

These are earliest ends before additional resource or crossflow waits.
Receiving's local receipt boundary is 301.57268043330697 s; actual storage is
386.1406417300791 s and full recovery is 687.0816642786192 s. The original
request deadlines remain unchanged. An explicitly longer comparison horizon
does not turn late work into on-time work.

## Portable reproduction

Install the repository's locked frontend dependencies once. From repository
root, run the tracked checker with a new output directory:

```powershell
node frontend/tools/check-warehouse-small-clamp-workflow-v3.mjs --out work/v3/small-clamp-recheck
```

This isolated checker verifies both engineering route variants. Its retail
case does not establish N1 scenario admission. The checker reads only tracked
fixture/layout/registry/profile/policy files,
public native assets and the current TypeScript dependency closure. It
compiles source and generic relative JSON imports into its own scratch
runtime. It does not read any saved `work/` input or previous runtime. The
output directory receives `checks.json`, `express-raw.json`, `retail-raw.json`
and the scratch runtime.

Both variants run 102 current outbound boundary/interior frames, 46 receiving
frames, eight outbound visibility/terminal controls and 70 phase boundaries
at ±1 μs. The checks cover issued guards, one token/one actual tool root,
whole-HU identity and visibility, original request/slot dependency, pure
sampling, native pad/bar contacts, actual cargo/tool frames, reverse seeks,
owner-safe reset and outbound-first disposal. They require restoration of
all original actor parents, instance matrices, native buffers and materials.
The recorded maximum active pad/bar gap is 19.5264 μm for express and
17.7965 μm for retail; actual cargo and tool frame errors are zero. Maximum
phase-boundary tool delta is 1.886 nm and actor delta 3.685 nm.
Terminal DTOs also match the actual released original actor roots: outbound
position and heading errors are zero for all participants in both variants;
the R02 terminal position error is below 4 × 10⁻¹⁹ m.

To reproduce the frozen tool in a **new temporary output**:

```powershell
node tools/blender/v3/build-small-carton-clamp-tool.mjs --output work/v3/small-clamp-rebuild/small-carton-clamp-tool.glb
```

The generator is an explicit Three.js/GLTFExporter utility; Blender itself
is not needed for this generator. It refuses the production path and existing
output files, writes a sibling `.geometry.json` component-mass report and
requires the generated GLB to match the frozen SHA-256. Its fresh run
reproduced all 54,712 bytes and the exact `7ea46…` hash. The shipped asset was
not regenerated or overwritten.

## Evidence and limits

The current portable receipt is
`docs/adaptive-v3/evidence/small-clamp-connected-workflow-native.json`.
Its full corrected matrices/frames are stored separately as
`small-clamp-connected-workflow-express-raw.json` and
`small-clamp-connected-workflow-retail-raw.json` in the same directory.
The exact original 1247.412426-second, 102-frame outbound report is retained
as `small-clamp-outbound-native-historical-1247s.json`. It is historical and
superseded: its snapshot-only checker did not detect the fixed-heading
connector jumps that the later epsilon check corrected. Its raw historical
`passed` field is not current continuity admission.

`small-clamp-original-receiving-native.json` retains the earlier focused
46-frame receiving/8-control evidence; the current portable receipt above
adds the complete corrected 102-frame outbound matrices for both variants.
`small-clamp-tool-generator-native.json` records exact temporary regeneration.

The practical native pad tolerance is 1 mm. Soft-cloth proxy tolerances and
the separate source/stow audits retain their stated scope. These checks do
not claim continuous global warehouse collision coverage, force/friction
certification or Source/LONG concurrency admission. The STD concurrency
certificate does not admit this different tool/crew trajectory.
