# Q01 reference / model / view matrix

Status: **MATRIX BUILT; CURRENT VISUAL REVIEW OPEN**. No new renders or acceptance.

77 explicit model/alias rows; 308 required four-view cells; 308 unreviewed. Binding counts: {"current-source-bound": 56, "missing": 34, "stale": 6, "unbound": 212}.

Family counts: {"cargo": 8, "containers": 5, "conveyors": 4, "environment": 6, "equipment": 4, "packing": 1, "runtime-presentations": 10, "storage": 5, "supporting-fixtures": 28, "workers": 6}.

The companion [JSON](evidence/Q01-model-matrix.json) contains full source/model/image SHA256, reference provenance, frame/evidence pointers, historical review assertions and input fingerprints. Current canonical stats live in assets/v3/blender. Alias rows without stats remain unresolved.

## Interpretation

- **graph**: No structural code graph tools exposed; exact scoped source/metadata fallback; no reindex.
- **selection**: Current canonical Blender stats/source/GLB first; manifest reference and task evidence next; all image candidates matched by hashes. Never latest filename selection.
- **binding**: current-source-bound means exact image hash plus an unambiguous current source or model path/hash in the same evidence document. It is a documentary association, not an independently repeated render or proof of model correctness. Mixed historical/current hashes remain unbound or stale. Missing hashes remain unbound.
- **review**: All current visual-review cells remain unreviewed. Historical assertions are quoted evidence only, including PASS/FIX scope and limitations; no new root visual review.
- **views**: Exact front/side/rear/quarter/three-quarter filenames only; quarter aliases three-quarter. Contact sheets/pose sequences/action frames are retained but never fill four static view cells. Runtime and native candidates remain separately typed.
- **scope**: Input-only models/references/evidence; no new render/browser/backend run, strength/retention/performance claim or full visual completion.
- **invariants**: Original 24 worker identities, 530 HUs, C02 units/masses/dimensions and 1:1 scale preserved; this inventory does not execute or certify those invariants.
- **corrections**: Inward rest palms; overhand top-down cart grip; four outward upper carton flaps with fixed walls. Historical acceptance does not waive current correction review.

## Coverage

F/S/R/Q = front/side/rear/three-quarter. C=current-source-bound, S=stale, U=unbound, M=missing. All are visually unreviewed; C is a hash-backed documentary association, never an acceptance verdict.

| Family / asset | Reference | Stats→GLB | F/S/R/Q | Historical task |
|---|---|---|---|---|
| supporting-fixtures / calibration | unresolved | current | U/U/U/U | see evidence index |
| conveyors / conveyor-diverter | R04 | current | U/U/U/U | see evidence index |
| conveyors / conveyor-kit | unresolved | current | U/U/U/U | P08 |
| conveyors / conveyor-straight | R04 | current | U/U/U/U | see evidence index |
| conveyors / conveyor-turn | R04 | current | U/U/U/U | see evidence index |
| environment / dock-module | R07 | current | C/C/C/C | P09.1 |
| workers / driver | R05 | missing | M/M/M/M | see evidence index |
| cargo / drum | M11_REF | current | U/U/U/U | M11 |
| supporting-fixtures / drum-forklift-fixture | M11_REF | current | U/U/U/U | see evidence index |
| environment / environment-markings-fixture | R07 | current | M/M/M/U | P09.4 |
| environment / environment-shell | R07 | current | C/C/C/C | P09.3 |
| storage / flex-bay | R13.5 | current | C/C/C/C | M05 |
| environment / floor-markings | R07 | current | M/M/M/U | P09.4 |
| equipment / forklift | M14.2-REACH | current | U/U/U/U | M14.9 |
| supporting-fixtures / forklift-body-wheels | M14.2-REACH | current | S/S/S/S | see evidence index |
| supporting-fixtures / forklift-cab-stage | M14.2-REACH | current | S/U/S/U | see evidence index |
| runtime-presentations / forklift-driver | R05 | current | U/U/U/U | P07 |
| supporting-fixtures / forklift-loaded-drum | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-loaded-fragile-crate | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-loaded-heavy-box | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-loaded-ibc | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-loaded-long-bundle | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-loaded-pallet-load | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-mast-stage | M14.2-REACH | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-pallet-high-fixture | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-pallet-low-fixture | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / forklift-pallet-travel-fixture | unresolved | current | U/U/U/U | see evidence index |
| runtime-presentations / forklift-pickup-cycle | M14.2-REACH | current | M/M/M/M | M14.8 |
| cargo / fragile-crate | M12_REF | current | U/U/U/U | M12 |
| supporting-fixtures / fragile-forklift-fixture | M12_REF | current | U/U/U/U | see evidence index |
| storage / heavy-bay | R13.3 | current | C/C/C/C | M03 |
| cargo / heavy-box | M06.3_REF | current | C/C/C/C | M06.3 |
| cargo / ibc | M09_REF | current | C/C/C/C | M09 |
| environment / large-gate | R07 | current | C/C/C/C | P09.2 |
| environment / large-gate-b2b | R07 | current | C/C/C/C | P09.2 |
| supporting-fixtures / layout-engineering | unresolved | current | U/U/U/U | see evidence index |
| cargo / long-bundle | M10_METAL_REF | current | U/U/U/U | M10 |
| equipment / long-cradle | M14_LONG_LOCK_REF | current | U/U/U/U | M14.6 |
| supporting-fixtures / long-cradle-loaded-fixture | unresolved | current | U/U/U/U | see evidence index |
| storage / long-rack | M04_TRANSFER_REF | current | U/U/U/U | M04 |
| supporting-fixtures / long-rack-loaded-fixture | M04_TRANSFER_REF | current | U/U/U/U | see evidence index |
| supporting-fixtures / long-rack-release-fixture | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / long-restraint-rig | unresolved | current | U/U/U/U | see evidence index |
| supporting-fixtures / long-transfer-interface-fixture | M04_TRANSFER_REF | current | U/U/U/U | see evidence index |
| runtime-presentations / manual-cart-walk | R11 | current | M/M/M/M | P03.4 |
| containers / order-tote | M07.1_REF | current | C/C/C/C | M07.1 |
| supporting-fixtures / packer-workcell-fixture | R04 | current | M/M/M/M | P04 |
| packing / packing-station | R04 | current | U/U/U/U | P08 |
| containers / pallet | R03 | missing | M/M/M/M | see evidence index |
| cargo / pallet-load | M08_REF | current | C/C/C/C | M08 |
| runtime-presentations / picker-cart-grip | R11 | current | U/U/U/U | P03.3 |
| runtime-presentations / picker-cart-walk | R11 | current | M/M/M/M | P03.4 |
| workers / picker-figure | R05 | current | U/U/U/U | see evidence index |
| supporting-fixtures / picker-pick-source-fixture | R13.1 | current | U/U/U/U | see evidence index |
| workers / picker-worker | R05 | missing | M/M/M/M | see evidence index |
| equipment / picking-cart | R11 | current | U/U/U/U | P03 |
| supporting-fixtures / picking-cart-tote-fixture | R11 | current | U/U/U/U | see evidence index |
| storage / rack-small | R13.1 | current | C/C/C/C | M01 |
| storage / rack-standard | R13.2 | current | C/C/C/C | M02 |
| supporting-fixtures / receiver-workcell-fixture | R04 | current | U/U/U/U | P05 |
| containers / sealed-parcel | M07.2_REF | current | U/U/U/U | M07.2 |
| supporting-fixtures / sealed-parcel-tote-fixture | M07.2_REF | current | U/U/U/U | see evidence index |
| supporting-fixtures / shipper-workcell-fixture | R04 | current | U/U/U/U | P06 |
| cargo / small-carton | M06.1_REF | current | C/C/C/C | M06.1 |
| containers / small-case-open-partial | M06.1_REF | current | U/U/U/U | see evidence index |
| supporting-fixtures / small-gripper-contact-fixture | P03_SMALL_GRIPPER_REF | current | U/U/U/U | see evidence index |
| equipment / small-package-gripper | P03_SMALL_GRIPPER_REF | current | U/U/U/U | see evidence index |
| containers / small-unit | M06.1_REF | current | U/U/U/U | see evidence index |
| cargo / standard-carton | M06.2_REF | current | C/C/C/C | M06.2 |
| workers / worker-base | R05 | current | U/U/U/U | P01 |
| workers / worker-manual | R05 | current | U/U/U/U | P03.5.3.3.1 |
| runtime-presentations / worker-role-F01 | R05 | current | U/U/U/U | P02 |
| runtime-presentations / worker-role-K01 | R05 | current | U/U/U/U | P02 |
| runtime-presentations / worker-role-P01 | R05 | current | U/U/U/U | P02 |
| runtime-presentations / worker-role-R01 | R05 | current | U/U/U/U | P02 |
| runtime-presentations / worker-role-S01 | R05 | current | U/U/U/U | P02 |
| workers / worker-small-pick | R05 | current | U/U/U/U | P03.5.3.3.1 |

## Per-model evidence

### calibration

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/calibration.blend` — 101880 bytes; SHA256 `a3693d12d9ea9cea4db1e775ee1d109b9089a9947a67547d47412e2a2e778333` (present).
- model: `frontend/public/models/v3/calibration.glb` — 14708 bytes; SHA256 `b2ceecef959d4cf42cb85510f35effeb09b7300ffc03457e76e09fc637d385b5` (present).
- stats: `assets/v3/blender/calibration.stats.json` — 9038 bytes; SHA256 `1775df91399b668953018b11ee131861cba7afa1683c858789c36cdbf83e1ad4` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/calibration/front.png`; `assets/v3/qa-browser/calibration/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/calibration/side.png`; `assets/v3/qa-browser/calibration/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/calibration/rear.png`; `assets/v3/qa-browser/calibration/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/calibration/three-quarter.png`; `assets/v3/qa-browser/calibration/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/calibration.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/calibration/browser-capture.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### conveyor-diverter

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/conveyor-diverter.blend` — 113348 bytes; SHA256 `372b14d2ac775c0a0930ed444607a1d0711fd4d16369273da985510e6aad14f4` (present).
- model: `frontend/public/models/v3/conveyor-diverter.glb` — 69444 bytes; SHA256 `d5bc76bafc75478c4569b5c20883e2b4bdfe9a132a26c24e9dbc63da14d44b26` (present).
- stats: `assets/v3/blender/conveyor-diverter.stats.json` — 13802 bytes; SHA256 `fe720f91c94b74fba05a16a96600c618ca6f92d76ba9f9fb39a0ff95df805b18` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/conveyor-diverter/front.png`; `assets/v3/qa-browser/conveyor-diverter/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/conveyor-diverter/side.png`; `assets/v3/qa-browser/conveyor-diverter/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/conveyor-diverter/rear.png`; `assets/v3/qa-browser/conveyor-diverter/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/conveyor-diverter/three-quarter.png`; `assets/v3/qa-browser/conveyor-diverter/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/conveyor-diverter.stats.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/conveyor-diverter/browser-capture.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### conveyor-kit

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/conveyor-kit.blend` — 230909 bytes; SHA256 `a5b13c9d851df75d95bed464bfdb6a66987a26a5b2a1d0159a3e0c83d2fc9f03` (present).
- model: `frontend/public/models/v3/conveyor-kit.glb` — 720968 bytes; SHA256 `20d724e3d56cfd6e273fd55ef16474aaf0fc6a47d7bf75e82df393216ba6f20a` (present).
- stats: `assets/v3/blender/conveyor-kit.stats.json` — 125422 bytes; SHA256 `e3b2642e6ca2ec2dd0116ac17347cfff4456e554fb2292b10153c24713a38da8` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/conveyor-kit/front.png`; `assets/v3/qa-browser/conveyor-kit/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/conveyor-kit/side.png`; `assets/v3/qa-browser/conveyor-kit/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/conveyor-kit/rear.png`; `assets/v3/qa-browser/conveyor-kit/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/conveyor-kit/three-quarter.png`; `assets/v3/qa-browser/conveyor-kit/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/conveyor-kit.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/conveyor-kit/browser-capture.json`; `docs/adaptive-v3/evidence/P08.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### conveyor-straight

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/conveyor-straight.blend` — 114218 bytes; SHA256 `8e478d7cab50631ef2513d80f44adf04fa1cc7782a569ca78d0a8bd469e6b042` (present).
- model: `frontend/public/models/v3/conveyor-straight.glb` — 92096 bytes; SHA256 `215b54e0375dc6e586d4a94734825e1e72f6288069153c72c8b4000652612d70` (present).
- stats: `assets/v3/blender/conveyor-straight.stats.json` — 15412 bytes; SHA256 `49c03125bf88b180efaa46f4848539e4810b97efc83fcf4259b7dc04fc1f9fc9` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/conveyor-straight/front.png`; `assets/v3/qa-browser/conveyor-straight/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/conveyor-straight/side.png`; `assets/v3/qa-browser/conveyor-straight/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/conveyor-straight/rear.png`; `assets/v3/qa-browser/conveyor-straight/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/conveyor-straight/three-quarter.png`; `assets/v3/qa-browser/conveyor-straight/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/conveyor-straight.stats.json`; `assets/v3/iterations/packer/P04.1/actual-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/conveyor-straight/browser-capture.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `docs/adaptive-v3/evidence/P04.1.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### conveyor-turn

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/conveyor-turn.blend` — 110495 bytes; SHA256 `613befaabeaa798f11100fddfc8a529a60efd2033385ed1f1e12def0143404f1` (present).
- model: `frontend/public/models/v3/conveyor-turn.glb` — 69764 bytes; SHA256 `bc2e5a89d5463cc90def87ec9795bb451847b1945e785229e5a2ce9ad55667de` (present).
- stats: `assets/v3/blender/conveyor-turn.stats.json` — 12157 bytes; SHA256 `c3c448ffc506d8e96b77ef9d3c1a1ca2e5f22e33e968826d177c559a2bca581d` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/conveyor-turn/front.png`; `assets/v3/qa-browser/conveyor-turn/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/conveyor-turn/side.png`; `assets/v3/qa-browser/conveyor-turn/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/conveyor-turn/rear.png`; `assets/v3/qa-browser/conveyor-turn/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/conveyor-turn/three-quarter.png`; `assets/v3/qa-browser/conveyor-turn/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/conveyor-turn.stats.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/conveyor-turn/browser-capture.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### dock-module

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/dock-module.blend` — 104364 bytes; SHA256 `e74fbb138133722434bdc2aad454807067257c5cc4a14583fcd1c01aed1a2342` (present).
- model: `frontend/public/models/v3/dock-module.glb` — 53896 bytes; SHA256 `964cf254728b6f70a916e5c4f0ac084e5b80ccb2cb356e47011a1652f7291b36` (present).
- stats: `assets/v3/blender/dock-module.stats.json` — 12818 bytes; SHA256 `7fd1d2ea6060263831c8991b16da0223c34aa6077263b4e13ebfccaabf58fe63` (present).
- Engineering qualification: Connected stepped U frame adapted to accepted .25 m wall band; no threshold/panel in clear opening.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/dock-module/P09.1/iteration-01/front.png`; `assets/v3/previews/dock-module/front.png`; `assets/v3/qa-browser/dock-module/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/dock-module/P09.1/iteration-01/side.png`; `assets/v3/previews/dock-module/side.png`; `assets/v3/qa-browser/dock-module/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/dock-module/P09.1/iteration-01/rear.png`; `assets/v3/previews/dock-module/rear.png`; `assets/v3/qa-browser/dock-module/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/dock-module/P09.1/iteration-01/three-quarter.png`; `assets/v3/previews/dock-module/three-quarter.png`; `assets/v3/qa-browser/dock-module/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/dock-module.stats.json`; `assets/v3/iterations/dock-module/P09.1/actual-glb-checks.json`; `assets/v3/iterations/dock-module/P09.1/iteration-01.actual-source-checks.json`; `assets/v3/iterations/dock-module/P09.1/iteration-01.source.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/dock-module/provenance.json`; `assets/v3/qa-browser/dock-module/browser-capture.json`; `assets/v3/specs/environment-shell.dimensions.json`; `assets/v3/specs/large-gate.dimensions.json`; `docs/adaptive-v3/evidence/P09.1.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### driver

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/driver.blend` — None bytes; SHA256 `None` (missing).
- model: `frontend/public/models/v3/driver.glb` — None bytes; SHA256 `None` (missing).
- stats: `assets/v3/blender/driver.stats.json` — None bytes; SHA256 `None` (missing).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: missing explicit evidence association

### drum

Reference: M11_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/drum.blend` — 107230 bytes; SHA256 `26ed8d5169bba308dd2c5c184ca9d0df0a03f287d7d12aa492f680c01dc25035` (present).
- model: `frontend/public/models/v3/drum.glb` — 100596 bytes; SHA256 `8a9c315306b2aa7ef6534f2491b0f307dd027ce90820c480a29a99912904ed24` (present).
- stats: `assets/v3/blender/drum.stats.json` — 8834 bytes; SHA256 `7a78eaf49a7261601c2f03c817c361472022b5e10d5b96cfba27056d041937ff` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/drum/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/drum/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/drum/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/drum/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/drum.stats.json`; `assets/v3/iterations/drum/M11-01/mesh-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/drum/browser-capture.json`; `assets/v3/qa-browser/drum/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M11.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### drum-forklift-fixture

Reference: M11_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/drum-forklift-fixture.blend` — 171361 bytes; SHA256 `7d402a01bc55314132d617c7331b6efad87601b07a7bc746a358f914347fd0ed` (present).
- model: `frontend/public/models/v3/drum-forklift-fixture.glb` — 511560 bytes; SHA256 `c681eb8c93be8cf4e076645be0c3270fef215fb98e8cf81678cfadbf7d3c79dc` (present).
- stats: `assets/v3/blender/drum-forklift-fixture.stats.json` — 48822 bytes; SHA256 `042a010b271374b6b2d3cc0e3dfcbfb626699c78d0ac3a6e9f433fb74b0c8ea6` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/drum-forklift-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/drum-forklift-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/drum-forklift-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/drum-forklift-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/drum-forklift-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/drum-forklift-fixture/browser-capture.json`; `assets/v3/qa-browser/drum-forklift-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M11.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### environment-markings-fixture

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/environment-markings-fixture.blend` — 574432 bytes; SHA256 `28d1c3bbb51ee614248f2de9e84a3f53232534f3e0fb388896d2cd27e1ab23e1` (present).
- model: `frontend/public/models/v3/environment-markings-fixture.glb` — 2563348 bytes; SHA256 `b50d93e84391b1c5ce7099cb0dacc78e8829bd8379eda817c8638f0768236cc2` (present).
- stats: `assets/v3/blender/environment-markings-fixture.stats.json` — 333659 bytes; SHA256 `aa84bd6137d2ee7df85899667a9e8770de91fc59e9dc6f72a3d2affa5082f70f` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/environment-markings-fixture.stats.json`; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/browser-capture.json`; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/browser-lifecycle.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/environment-markings-fixture/actual-glb-geometry.json`; `docs/adaptive-v3/evidence/P09.4.json`; `docs/adaptive-v3/evidence/P09.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### environment-shell

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/environment-shell.blend` — 281006 bytes; SHA256 `9b0a1c7e744623ca88e5975b0fd8b71ad9134d50585ead1fbe231fdd0de36d68` (present).
- model: `frontend/public/models/v3/environment-shell.glb` — 987460 bytes; SHA256 `2580e0988d5d25d07dd90a9ffe9452130f555ccb0954d3ee07db0018fa796f70` (present).
- stats: `assets/v3/blender/environment-shell.stats.json` — 156701 bytes; SHA256 `50ce0ae6ddb7649c8c94158130dc0d4dcbdb22a1661195bad1490504b66a4ff7` (present).
- Engineering qualification: Accepted cutaway walls/returns, columns and six apertures; architectural exceptions/precision budget remain qualified in P09.3.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/environment-shell/P09.3/iteration-01/front.png`; `assets/v3/previews/environment-shell/front.png`; `assets/v3/qa-browser/environment-shell/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/environment-shell/P09.3/iteration-01/side.png`; `assets/v3/previews/environment-shell/side.png`; `assets/v3/qa-browser/environment-shell/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/environment-shell/P09.3/iteration-01/rear.png`; `assets/v3/previews/environment-shell/rear.png`; `assets/v3/qa-browser/environment-shell/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/environment-shell/P09.3/iteration-01/three-quarter.png`; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/quarter.png`; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/quarter.png`; `assets/v3/iterations/environment-shell/P09.4/port-close/quarter.png`; `assets/v3/previews/environment-shell/three-quarter.png`; `assets/v3/qa-browser/environment-shell/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/environment-shell.stats.json`; `assets/v3/iterations/environment-shell/P09.3/actual-glb-checks.json`; `assets/v3/iterations/environment-shell/P09.3/actual-route-checks.json`; `assets/v3/iterations/environment-shell/P09.3/actual-source-checks.json`; `assets/v3/iterations/environment-shell/P09.3/glb-geometry-components.json`; `assets/v3/iterations/environment-shell/P09.3/glb-route-checks.json`; `assets/v3/iterations/environment-shell/P09.3/iteration-01.render.json`; `assets/v3/iterations/environment-shell/P09.3/iteration-01.source.json`; `assets/v3/iterations/environment-shell/P09.3/plan-route-preflight.json`; `assets/v3/iterations/environment-shell/P09.3/source-geometry.json`; `assets/v3/iterations/environment-shell/P09.3/source-mesh-qa.json`; `assets/v3/iterations/environment-shell/P09.4/actual-floor-markings.json`; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/browser-capture.json`; `assets/v3/iterations/environment-shell/P09.4/browser/environment-markings-fixture/browser-lifecycle.json`; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/browser-capture.json`; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/browser-lifecycle.json`; `assets/v3/iterations/environment-shell/P09.4/port-close/browser-capture.json`; `assets/v3/iterations/environment-shell/P09.4/port-close/browser-lifecycle.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/environment-shell/provenance.json`; `assets/v3/qa-browser/environment-shell/browser-capture.json`; `assets/v3/specs/floor-markings.geometry.json`; `docs/adaptive-v3/evidence/P09.3.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### flex-bay

Reference: R13.5. Current review: **unreviewed**.

- source: `assets/v3/blender/flex-bay.blend` — 105321 bytes; SHA256 `35539fda2f2a26121e7276b87c9a7cd4099f1fda65b004b073463022c11b897c` (present).
- model: `frontend/public/models/v3/flex-bay.glb` — 47820 bytes; SHA256 `3dc964a3a823dd786aaa97d2f20bd0fb0d9ec3ee81432253af8734d68c44da9a` (present).
- stats: `assets/v3/blender/flex-bay.stats.json` — 8487 bytes; SHA256 `8b9c122962e3f7b6be4368b99fd2128fea2e02438609b950c03e2c287072fa42` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/flex-bay/initial/views/front.png`; `assets/v3/previews/flex-bay/front.png`; `assets/v3/qa-browser/flex-bay/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/flex-bay/initial/views/side.png`; `assets/v3/previews/flex-bay/side.png`; `assets/v3/qa-browser/flex-bay/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/flex-bay/initial/views/rear.png`; `assets/v3/previews/flex-bay/rear.png`; `assets/v3/qa-browser/flex-bay/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/flex-bay/initial/views/three-quarter.png`; `assets/v3/previews/flex-bay/three-quarter.png`; `assets/v3/qa-browser/flex-bay/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/flex-bay.stats.json`; `assets/v3/iterations/flex-bay/candidate/binary-checks.json`; `assets/v3/iterations/flex-bay/candidate/dimension-plan.json`; `assets/v3/iterations/flex-bay/candidate/geometry-checks.json`; `assets/v3/iterations/flex-bay/candidate/source-metrics.json`; `assets/v3/iterations/flex-bay/initial/dimension-plan.json`; `assets/v3/iterations/flex-bay/initial/geometry-checks.json`; `assets/v3/iterations/flex-bay/initial/source-metrics.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/flex-bay/provenance.json`; `assets/v3/qa-browser/flex-bay/browser-capture.json`; `docs/adaptive-v3/evidence/M05.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### floor-markings

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/floor-markings.blend` — 379864 bytes; SHA256 `eb8ba1600b72aba66409a40d0d906a1fd5b0e5236cf8badecbd0c043143f3459` (present).
- model: `frontend/public/models/v3/floor-markings.glb` — 1574008 bytes; SHA256 `721d49153a60840ffdf5dbcbd47b3a38f1c5ab7eac729d29058687641fe1c25e` (present).
- stats: `assets/v3/blender/floor-markings.stats.json` — 176545 bytes; SHA256 `ea5f24035a2e5c362e85a88643bafc7d321abc5d0a3ad05b08e65ebeca7c65b4` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/floor-markings.stats.json`; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/browser-capture.json`; `assets/v3/iterations/environment-shell/P09.4/browser/floor-markings/browser-lifecycle.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/floor-markings/actual-glb-geometry.json`; `docs/adaptive-v3/evidence/P09.4.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift

Reference: M14.2-REACH. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift.blend` — 160105 bytes; SHA256 `e8933df70439ae82c719d80b835fa8cdfb08b97ba50362ab97c1cea24cb754c8` (present).
- model: `frontend/public/models/v3/forklift.glb` — 434992 bytes; SHA256 `937816125a8c1522148e4928b34257096bc22dcb4a359201a08b80d78b1ee156` (present).
- stats: `assets/v3/blender/forklift.stats.json` — 41450 bytes; SHA256 `6d4cfee4087b9b425ac5338ed04d73e9cffc97066335d016fc8d6ab7ac916755` (present).
- Engineering qualification: M14.2-REACH and final M14.9 evidence govern current vehicle, not latest stage filename. Historical axle/cab/mast stages are separate models.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/iterations/forklift/M14.2/iteration-01/front.png`; `assets/v3/iterations/forklift/M14.2/iteration-02/front.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/front.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/cab-previews/front.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/front.png`; `assets/v3/iterations/forklift/M14.3/iteration-01/front.png`; `assets/v3/iterations/forklift/M14.3/iteration-02/front.png`; `assets/v3/iterations/forklift/M14.3/iteration-03/front.png`; `assets/v3/iterations/forklift/M14.3/with-driver-01/front.png`; `assets/v3/iterations/forklift/M14.3/with-driver-02/front.png`; `assets/v3/iterations/forklift/M14.3/with-driver-03/front.png`; `assets/v3/qa-browser/forklift/front.png`
- side: **unbound / unreviewed**; `assets/v3/iterations/forklift/M14.2/iteration-01/side.png`; `assets/v3/iterations/forklift/M14.2/iteration-02/side.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/side.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/cab-previews/side.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/side.png`; `assets/v3/iterations/forklift/M14.3/iteration-01/side.png`; `assets/v3/iterations/forklift/M14.3/iteration-02/side.png`; `assets/v3/iterations/forklift/M14.3/iteration-03/side.png`; `assets/v3/iterations/forklift/M14.3/with-driver-01/side.png`; `assets/v3/iterations/forklift/M14.3/with-driver-02/side.png`; `assets/v3/iterations/forklift/M14.3/with-driver-03/side.png`; `assets/v3/qa-browser/forklift/side.png`
- rear: **unbound / unreviewed**; `assets/v3/iterations/forklift/M14.2/iteration-01/rear.png`; `assets/v3/iterations/forklift/M14.2/iteration-02/rear.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/rear.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/cab-previews/rear.png`; `assets/v3/iterations/forklift/M14.3/iteration-01/rear.png`; `assets/v3/iterations/forklift/M14.3/iteration-02/rear.png`; `assets/v3/iterations/forklift/M14.3/iteration-03/rear.png`; `assets/v3/iterations/forklift/M14.3/with-driver-01/rear.png`; `assets/v3/iterations/forklift/M14.3/with-driver-02/rear.png`; `assets/v3/iterations/forklift/M14.3/with-driver-03/rear.png`; `assets/v3/qa-browser/forklift/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/forklift/M14.2/iteration-01/three-quarter.png`; `assets/v3/iterations/forklift/M14.2/iteration-02/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/cab-previews/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/paired-after/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/iteration-01/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/iteration-02/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/iteration-03/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/with-driver-01/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/with-driver-02/three-quarter.png`; `assets/v3/iterations/forklift/M14.3/with-driver-03/three-quarter.png`; `assets/v3/qa-browser/forklift/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift.stats.json`; `assets/v3/iterations/forklift/M14.1/C08-before-physical-correction.json`; `assets/v3/iterations/forklift/M14.1/actual-blueprint-checks.json`; `assets/v3/iterations/forklift/M14.2/actual-glb-checks.json`; `assets/v3/iterations/forklift/M14.2/actual-source-checks.json`; `assets/v3/iterations/forklift/M14.2/front-axle-repair/before/forklift-body-wheels.stats.json`; `assets/v3/iterations/forklift/M14.2/front-axle-repair/declared-plan.json`; `assets/v3/iterations/forklift/M14.3/actual-cab-checks.json`; `assets/v3/iterations/forklift/M14.3/actual-glb-checks.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/actual-repair-checks.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/actual-repair-glb-checks.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/render-provenance.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.2/M14.2.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.2/forklift-body-wheels.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/M14.3.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/forklift-cab-stage.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/render-provenance.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/paired-after/render-provenance.json`; `assets/v3/iterations/forklift/M14.3/iteration-01-checks.json`; `assets/v3/iterations/forklift/M14.4/actual-glb-checks.json`; `assets/v3/iterations/forklift/M14.4/actual-mast-checks.json`; `assets/v3/iterations/forklift/M14.6.1/actual-glb-checks.json`; `assets/v3/iterations/forklift/M14.6.1/actual-mast-checks.json`; `assets/v3/iterations/forklift/M14.6.1/actual-native-contacts.json`; `assets/v3/iterations/forklift/M14.6.3/actual-loaded-native-checks.json`; `assets/v3/iterations/forklift/M14.8/actual-pickup-continuous-checks.json`; `assets/v3/iterations/forklift/M14.8/pre-driver-browser-action-checks.json`; `assets/v3/iterations/forklift/M14.8/pre-driver-browser-lifecycle.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/qa-browser/forklift/browser-capture.json`; `assets/v3/qa-browser/forklift/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M14.9.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### forklift-body-wheels

Reference: M14.2-REACH. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-body-wheels.blend` — 122738 bytes; SHA256 `047c84bbc27ea5ff73e160ddfd1d51155ef6962b4c7335b471ebb48c05d18e19` (present).
- model: `frontend/public/models/v3/forklift-body-wheels.glb` — 192688 bytes; SHA256 `27b373611a8878024dd949ee13995991943201d6e390969b495cafebf4786c1b` (present).
- stats: `assets/v3/blender/forklift-body-wheels.stats.json` — 20772 bytes; SHA256 `d8b70438c4bfd4a65e10bfb43c35ea2f5847a5a6d98e162538702332a3cc9a34` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **stale / unreviewed**; `assets/v3/previews/forklift-body-wheels/front.png`; `assets/v3/qa-browser/forklift-body-wheels/front.png`
- side: **stale / unreviewed**; `assets/v3/previews/forklift-body-wheels/side.png`; `assets/v3/qa-browser/forklift-body-wheels/side.png`
- rear: **stale / unreviewed**; `assets/v3/previews/forklift-body-wheels/rear.png`; `assets/v3/qa-browser/forklift-body-wheels/rear.png`
- three-quarter: **stale / unreviewed**; `assets/v3/previews/forklift-body-wheels/three-quarter.png`; `assets/v3/qa-browser/forklift-body-wheels/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-body-wheels.stats.json`; `assets/v3/iterations/forklift/M14.2/actual-source-checks.json`; `assets/v3/iterations/forklift/M14.2/front-axle-repair/before/forklift-body-wheels.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.2/M14.2.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-body-wheels/browser-capture.json`; `assets/v3/qa-browser/forklift-body-wheels/browser-lifecycle.json`; `assets/v3/specs/forklift-mast-stage.json`; `docs/adaptive-v3/evidence/M14.2.json`; `docs/adaptive-v3/evidence/M14.9.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-cab-stage

Reference: M14.2-REACH. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-cab-stage.blend` — 138571 bytes; SHA256 `1ac874cb188c84b455d74aee75d7f22ed323e92eb092ae6e3c01f33e4145e080` (present).
- model: `frontend/public/models/v3/forklift-cab-stage.glb` — 285172 bytes; SHA256 `117dce493fd8bcf26a4d09c6d9558b19870628abe79153579830d1dd80729e68` (present).
- stats: `assets/v3/blender/forklift-cab-stage.stats.json` — 28823 bytes; SHA256 `fac5f13f63b3863fb0ff04b978b4847679ca9291e34405e575966fc0c3e6b6e5` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **stale / unreviewed**; `assets/v3/previews/forklift-cab-stage/front.png`; `assets/v3/previews/forklift-cab-stage/with-driver/front.png`; `assets/v3/qa-browser/forklift-cab-stage/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/forklift-cab-stage/side.png`; `assets/v3/previews/forklift-cab-stage/with-driver/side.png`; `assets/v3/qa-browser/forklift-cab-stage/side.png`
- rear: **stale / unreviewed**; `assets/v3/previews/forklift-cab-stage/rear.png`; `assets/v3/previews/forklift-cab-stage/with-driver/rear.png`; `assets/v3/qa-browser/forklift-cab-stage/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/forklift-cab-stage/three-quarter.png`; `assets/v3/previews/forklift-cab-stage/with-driver/three-quarter.png`; `assets/v3/qa-browser/forklift-cab-stage/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-cab-stage.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/after/render-provenance.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/M14.3.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/forklift-cab-stage.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/forklift-cab-stage/render-provenance.json`; `assets/v3/qa-browser/forklift-cab-stage/browser-capture.json`; `assets/v3/qa-browser/forklift-cab-stage/browser-lifecycle.json`; `assets/v3/specs/forklift-mast-stage.json`; `docs/adaptive-v3/evidence/M14.3.json`; `docs/adaptive-v3/evidence/M14.9.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-driver

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-driver/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-driver/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-driver/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-driver/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/qa-browser/forklift-driver/browser-capture.json`; `assets/v3/qa-browser/forklift-driver/browser-lifecycle.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P07.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### forklift-loaded-drum

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-drum.blend` — 166898 bytes; SHA256 `223a24da152c850466bded6312b9bb5c0f4ebef52bb5a73bb9e94d5ac81c0156` (present).
- model: `frontend/public/models/v3/forklift-loaded-drum.glb` — 535256 bytes; SHA256 `0242b40898cde6e7e2d26e7ff8c756c4bdf1bd94a9e18e60f63fdd3e4b9e4dc0` (present).
- stats: `assets/v3/blender/forklift-loaded-drum.stats.json` — 49035 bytes; SHA256 `e26271b9636407d23677abaa3566cfa5a1d74b9d9073dc93d467781ebc1c261f` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-drum/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-drum/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-drum/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-drum/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-drum.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-drum/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-drum/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-drum/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-loaded-fragile-crate

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-fragile-crate.blend` — 191226 bytes; SHA256 `55db3977ab8df4833bf2bb09b68c2c88c9275f8ca3e362fb5d7d40935c07e9bf` (present).
- model: `frontend/public/models/v3/forklift-loaded-fragile-crate.glb` — 596408 bytes; SHA256 `ce1d748b59f60d27d00f12d4e87f7c934aac9dcee5edfec37799c79a9f8ee10e` (present).
- stats: `assets/v3/blender/forklift-loaded-fragile-crate.stats.json` — 67398 bytes; SHA256 `56d92a47add4884c4e9c5d83c0d5ecdb4b1d5318b981ec194d549addfcb48125` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-fragile-crate/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-fragile-crate/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-fragile-crate/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-fragile-crate/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-fragile-crate.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-fragile-crate/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-fragile-crate/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-fragile-crate/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-loaded-heavy-box

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-heavy-box.blend` — 182845 bytes; SHA256 `4a6681b4a06df381319302ca6fcb2db222a92176ac66226d21eea34effa299a4` (present).
- model: `frontend/public/models/v3/forklift-loaded-heavy-box.glb` — 563168 bytes; SHA256 `664f32a2e25b322fa2337819c94ce4943b023057a8f9e4f9f86b6b0f7c54a1d5` (present).
- stats: `assets/v3/blender/forklift-loaded-heavy-box.stats.json` — 63225 bytes; SHA256 `bd38dd1cfb89ed81662b877a2f45a89e14e1dbd0ebd291d0af25dd690c7eefd3` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-heavy-box/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-heavy-box/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-heavy-box/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-heavy-box/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-heavy-box.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-heavy-box/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-heavy-box/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-heavy-box/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-loaded-ibc

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-ibc.blend` — 189612 bytes; SHA256 `3fda9273973a72e10c47d7b29e14e6dfc2b184074286f6d00f48786c3a11dab7` (present).
- model: `frontend/public/models/v3/forklift-loaded-ibc.glb` — 626992 bytes; SHA256 `8389c32d0f16708c0263b6750c767d6e248ab2409e06aca5cde21fc30c58cc5d` (present).
- stats: `assets/v3/blender/forklift-loaded-ibc.stats.json` — 62989 bytes; SHA256 `3cfebcba4961dc04ba51f2c2b7ddc3225fb68334bb790371302b645a4e6db3c8` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-ibc/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-ibc/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-ibc/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-ibc/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-ibc.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-ibc/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-ibc/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-ibc/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-loaded-long-bundle

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-long-bundle.blend` — 245544 bytes; SHA256 `80df91f7a8c7ebf9d958121a168beedf15135576e3e00e3a627d27463155d036` (present).
- model: `frontend/public/models/v3/forklift-loaded-long-bundle.glb` — 1016536 bytes; SHA256 `f7f320796cb0b85c45f52cb06e4cf617043e70c686516944fe2fc7f0582b1c60` (present).
- stats: `assets/v3/blender/forklift-loaded-long-bundle.stats.json` — 85712 bytes; SHA256 `97de02a29f4a3856d233190a212b5e8a6929caa15d06aae15b3ecdec0b872c3f` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-long-bundle/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-long-bundle/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-long-bundle/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-long-bundle/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-long-bundle.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-long-bundle/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-long-bundle/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-long-bundle/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-loaded-pallet-load

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-loaded-pallet-load.blend` — 209146 bytes; SHA256 `3fe2d7c102333c3ca2ee5c38d5236bcb7ac0dbde1189c1a9f8c07613141b40d0` (present).
- model: `frontend/public/models/v3/forklift-loaded-pallet-load.glb` — 770472 bytes; SHA256 `a67f306b496c0e2b687288c8874ac1de2a940c704bb00d1f711314ef1f7daccc` (present).
- stats: `assets/v3/blender/forklift-loaded-pallet-load.stats.json` — 75622 bytes; SHA256 `20b6b265df112907f543492f6712592712e766f5eaa2d20fe114b8b2ffe19ab7` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-pallet-load/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-pallet-load/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-pallet-load/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-loaded-pallet-load/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-loaded-pallet-load.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-loaded-pallet-load/actual-glb-geometry.json`; `assets/v3/qa-browser/forklift-loaded-pallet-load/browser-capture.json`; `assets/v3/qa-browser/forklift-loaded-pallet-load/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-mast-stage

Reference: M14.2-REACH. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-mast-stage.blend` — 156401 bytes; SHA256 `3525d0926e21c859a9a0873da2b071b1eae6d9ddca71262a920e8a81dbe7c2a6` (present).
- model: `frontend/public/models/v3/forklift-mast-stage.glb` — 411556 bytes; SHA256 `ef6e58f8131c4e51881a7c1d648bb6ebd79492683b19d09ba5389c48c97e7121` (present).
- stats: `assets/v3/blender/forklift-mast-stage.stats.json` — 41505 bytes; SHA256 `1b1e3fd38a1ff246994d8a0176ba34fd3803dbce3243abf9a4d97cf7f72c23d9` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-mast-stage/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-mast-stage/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-mast-stage/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-mast-stage/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-mast-stage.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-mast-stage/browser-capture.json`; `assets/v3/qa-browser/forklift-mast-stage/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M14.4.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-pallet-high-fixture

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-pallet-high-fixture.blend` — 249116 bytes; SHA256 `30c4eeec6985c6f9d0de7ef74c41e60840cd0dcc1bc8e549d1bfe34c94c349f1` (present).
- model: `frontend/public/models/v3/forklift-pallet-high-fixture.glb` — 816520 bytes; SHA256 `9a11ea0e7e1db462d5bfe1c8a37976279370f02222cdfa26681655ccfcde41c9` (present).
- stats: `assets/v3/blender/forklift-pallet-high-fixture.stats.json` — 83005 bytes; SHA256 `869ffac3839ed4622397ca3ea90aa0d49a1985fec54d7474291fc40021227546` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-high-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-high-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-high-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-high-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-pallet-high-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-pallet-high-fixture/browser-capture.json`; `assets/v3/qa-browser/forklift-pallet-high-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-pallet-low-fixture

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-pallet-low-fixture.blend` — 233807 bytes; SHA256 `b018b8a0d31d22fea9fa9f41d4ee8ce4537657816fadeee9c061bcff8ab53488` (present).
- model: `frontend/public/models/v3/forklift-pallet-low-fixture.glb` — 818836 bytes; SHA256 `b172dc6dd245208a49fdddebccd6ff5d64cc3771c4e0259dabdd633adbd2808a` (present).
- stats: `assets/v3/blender/forklift-pallet-low-fixture.stats.json` — 83405 bytes; SHA256 `368426021d3217035f1dafb8de90974c436211d4c36d10d4c184492964d88282` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-low-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-low-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-low-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-low-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-pallet-low-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-pallet-low-fixture/browser-capture.json`; `assets/v3/qa-browser/forklift-pallet-low-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-pallet-travel-fixture

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift-pallet-travel-fixture.blend` — 239862 bytes; SHA256 `25b810a461fd56cb5e2c4b0f7db5fe3db6549d65ec2c0b7fdcb69f636c680798` (present).
- model: `frontend/public/models/v3/forklift-pallet-travel-fixture.glb` — 818384 bytes; SHA256 `4615da2d497ca3d6f4a7c130e2bb5490a50616bc97ad9f7526aeda49ee766eb4` (present).
- stats: `assets/v3/blender/forklift-pallet-travel-fixture.stats.json` — 83161 bytes; SHA256 `fd9badb9382f7978322b7630768acf80adc50d2c538835423039e19b7df4503b` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-travel-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-travel-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-travel-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/forklift-pallet-travel-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/forklift-pallet-travel-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/forklift-pallet-travel-fixture/browser-capture.json`; `assets/v3/qa-browser/forklift-pallet-travel-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### forklift-pickup-cycle

Reference: M14.2-REACH. Current review: **unreviewed**.

- source: `assets/v3/blender/forklift.blend` — 160105 bytes; SHA256 `e8933df70439ae82c719d80b835fa8cdfb08b97ba50362ab97c1cea24cb754c8` (present).
- model: `frontend/public/models/v3/forklift.glb` — 434992 bytes; SHA256 `937816125a8c1522148e4928b34257096bc22dcb4a359201a08b80d78b1ee156` (present).
- stats: `assets/v3/blender/forklift.stats.json` — 41450 bytes; SHA256 `6d4cfee4087b9b425ac5338ed04d73e9cffc97066335d016fc8d6ab7ac916755` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: `assets/v3/blender/forklift.stats.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/qa-browser/forklift-pickup-cycle/browser-action-checks.json`; `assets/v3/qa-browser/forklift-pickup-cycle/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M14.8.json`; `docs/adaptive-v3/evidence/M14.9.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### fragile-crate

Reference: M12_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/fragile-crate.blend` — 130618 bytes; SHA256 `488941ab093cd1162210bc9f2d1764608a89091634c4bc493863e421d9efe87d` (present).
- model: `frontend/public/models/v3/fragile-crate.glb` — 161352 bytes; SHA256 `acb07b7587c5e32be886e9ee998bed5f918b5ff7bbd064021cabeb3264c204b1` (present).
- stats: `assets/v3/blender/fragile-crate.stats.json` — 27098 bytes; SHA256 `431320da446a2d053c3ecc3108d0879d94baf6265d397c19543d1f4211e6cacd` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-crate/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-crate/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-crate/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-crate/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/fragile-crate.stats.json`; `assets/v3/iterations/fragile-crate/M12-01/mesh-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/fragile-crate/browser-capture.json`; `assets/v3/qa-browser/fragile-crate/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M12.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### fragile-forklift-fixture

Reference: M12_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/fragile-forklift-fixture.blend` — 194972 bytes; SHA256 `b4d079d8485b40bbb8b3b3f1c20069e1bde49a731bc9e7d24c4f475bc5ae232c` (present).
- model: `frontend/public/models/v3/fragile-forklift-fixture.glb` — 572500 bytes; SHA256 `de770ea037e701775c797fad319112f382f86533a403646e7ba4d4f6ea00d473` (present).
- stats: `assets/v3/blender/fragile-forklift-fixture.stats.json` — 66986 bytes; SHA256 `1abc072dacd85c2eac7d81248fb2344540943a8d02abbce54a1f917cb2877c17` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-forklift-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-forklift-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-forklift-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/fragile-forklift-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/fragile-forklift-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/fragile-forklift-fixture/browser-capture.json`; `assets/v3/qa-browser/fragile-forklift-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M12.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### heavy-bay

Reference: R13.3. Current review: **unreviewed**.

- source: `assets/v3/blender/heavy-bay.blend` — 104661 bytes; SHA256 `7aa14004cd92dfdec5ec9ee514110dab80ff4957492b059e92331443090169d5` (present).
- model: `frontend/public/models/v3/heavy-bay.glb` — 47860 bytes; SHA256 `dcc28aaeb9c924569de7699265a3bb08941b6c27faaf4fc8541c5a66b15838e9` (present).
- stats: `assets/v3/blender/heavy-bay.stats.json` — 9028 bytes; SHA256 `216f57aa8a89e67437190813cd2a8c22de3d66657dd77e511c2e7b6bc457f230` (present).
- Engineering qualification: C08 functional open fork lanes/support patches override continuous raster deck; narrow-HU/support limitations remain. Petrol ribs/charcoal runners supersede earlier tan material mismatch.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-bay/initial/views/front.png`; `assets/v3/iterations/heavy-bay/material-final/views/front.png`; `assets/v3/previews/heavy-bay/front.png`; `assets/v3/qa-browser/heavy-bay/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-bay/initial/views/side.png`; `assets/v3/iterations/heavy-bay/material-final/views/side.png`; `assets/v3/previews/heavy-bay/side.png`; `assets/v3/qa-browser/heavy-bay/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-bay/initial/views/rear.png`; `assets/v3/iterations/heavy-bay/material-final/views/rear.png`; `assets/v3/previews/heavy-bay/rear.png`; `assets/v3/qa-browser/heavy-bay/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-bay/initial/views/three-quarter.png`; `assets/v3/iterations/heavy-bay/material-final/views/three-quarter.png`; `assets/v3/previews/heavy-bay/three-quarter.png`; `assets/v3/qa-browser/heavy-bay/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/heavy-bay.stats.json`; `assets/v3/iterations/heavy-bay/c08-v01-baseline/M03.json`; `assets/v3/iterations/heavy-bay/c08-v01-baseline/heavy-bay.dimensions.json`; `assets/v3/iterations/heavy-bay/c08-v01-baseline/heavy-bay.stats.json`; `assets/v3/iterations/heavy-bay/c08-v01-baseline/provenance.json`; `assets/v3/iterations/heavy-bay/c08-v02/M03.json`; `assets/v3/iterations/heavy-bay/c08-v02/binary-checks.json`; `assets/v3/iterations/heavy-bay/c08-v02/dimension-plan.json`; `assets/v3/iterations/heavy-bay/c08-v02/geometry-checks.json`; `assets/v3/iterations/heavy-bay/c08-v02/heavy-bay.stats.json`; `assets/v3/iterations/heavy-bay/c08-v02/metadata-equivalence.json`; `assets/v3/iterations/heavy-bay/c08-v02/provenance.json`; `assets/v3/iterations/heavy-bay/c08-v02/source-metrics.json`; `assets/v3/iterations/heavy-bay/candidate/binary-checks.json`; `assets/v3/iterations/heavy-bay/candidate/dimension-plan.json`; `assets/v3/iterations/heavy-bay/candidate/geometry-checks.json`; `assets/v3/iterations/heavy-bay/candidate/source-metrics.json`; `assets/v3/iterations/heavy-bay/initial/dimension-plan.json`; `assets/v3/iterations/heavy-bay/initial/geometry-checks.json`; `assets/v3/iterations/heavy-bay/initial/source-metrics.json`; `assets/v3/iterations/heavy-bay/material-final/BIN-material-equivalence.json`; `assets/v3/iterations/heavy-bay/material-final/binary-checks.json`; `assets/v3/iterations/heavy-bay/material-final/dimension-plan.json`; `assets/v3/iterations/heavy-bay/material-final/geometry-checks.json`; `assets/v3/iterations/heavy-bay/material-final/source-material-equivalence.json`; `assets/v3/iterations/heavy-bay/material-final/source-metrics.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/heavy-bay/provenance.json`; `assets/v3/qa-browser/heavy-bay/browser-capture.json`; `docs/adaptive-v3/evidence/M03.json`; `docs/adaptive-v3/evidence/M08.json`; `docs/adaptive-v3/evidence/M09.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### heavy-box

Reference: M06.3_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/heavy-box.blend` — 120757 bytes; SHA256 `cef395dc17d202477e4bd46dfe9d762bbd5ed65e6f10a14c80fade1a20b56e19` (present).
- model: `frontend/public/models/v3/heavy-box.glb` — 127900 bytes; SHA256 `3464429a21139139556026f3bb7ff0ca515844780a8348cbf54ed58ef1a301a5` (present).
- stats: `assets/v3/blender/heavy-box.stats.json` — 23142 bytes; SHA256 `f5921a0067a474ef6a63f3f821edb41c57965387098f6c6529b197da2e1f6436` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-box/M06.3-01/front.png`; `assets/v3/iterations/heavy-box/M06.3-02/front.png`; `assets/v3/previews/heavy-box/front.png`; `assets/v3/qa-browser/heavy-box/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-box/M06.3-01/side.png`; `assets/v3/iterations/heavy-box/M06.3-02/side.png`; `assets/v3/previews/heavy-box/side.png`; `assets/v3/qa-browser/heavy-box/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-box/M06.3-01/rear.png`; `assets/v3/iterations/heavy-box/M06.3-02/rear.png`; `assets/v3/previews/heavy-box/rear.png`; `assets/v3/qa-browser/heavy-box/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/heavy-box/M06.3-01/three-quarter.png`; `assets/v3/iterations/heavy-box/M06.3-02/three-quarter.png`; `assets/v3/previews/heavy-box/three-quarter.png`; `assets/v3/qa-browser/heavy-box/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/heavy-box.stats.json`; `assets/v3/iterations/heavy-box/M06.3-01/heavy-box.dimensions.json`; `assets/v3/iterations/heavy-box/M06.3-01/heavy-box.geometry.json`; `assets/v3/iterations/heavy-box/M06.3-01/heavy-box.stats.json`; `assets/v3/iterations/heavy-box/M06.3-01/mesh-checks.json`; `assets/v3/iterations/heavy-box/M06.3-01/render-report.json`; `assets/v3/iterations/heavy-box/M06.3-01/saved-source-checks.json`; `assets/v3/iterations/heavy-box/M06.3-02/M06.3-evidence.json`; `assets/v3/iterations/heavy-box/M06.3-02/heavy-box.dimensions.json`; `assets/v3/iterations/heavy-box/M06.3-02/heavy-box.geometry.json`; `assets/v3/iterations/heavy-box/M06.3-02/heavy-box.stats.json`; `assets/v3/iterations/heavy-box/M06.3-02/mesh-checks.json`; `assets/v3/iterations/heavy-box/M06.3-02/render-report.json`; `assets/v3/iterations/heavy-box/M06.3-02/saved-source-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/heavy-box/browser-capture.json`; `docs/adaptive-v3/evidence/M06.3.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### ibc

Reference: M09_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/ibc.blend` — 131221 bytes; SHA256 `85c197fcb560cf6a2821781781de29db52a5a9a93c0a16bfaf78bc88c2da75dd` (present).
- model: `frontend/public/models/v3/ibc.glb` — 191516 bytes; SHA256 `25ea85ca946f8afa6e032dd9462318bc5d656627b94ea19bf0c84fcda87dc63a` (present).
- stats: `assets/v3/blender/ibc.stats.json` — 22849 bytes; SHA256 `be3de75be0df75bc933f45eff967b7e851824754e0c2c25c26aa226a4fb3e435` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/ibc/initial/views/front.png`; `assets/v3/iterations/ibc/polished/views/front.png`; `assets/v3/previews/ibc/front.png`; `assets/v3/qa-browser/ibc/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/ibc/initial/views/side.png`; `assets/v3/iterations/ibc/polished/views/side.png`; `assets/v3/previews/ibc/side.png`; `assets/v3/qa-browser/ibc/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/ibc/initial/views/rear.png`; `assets/v3/iterations/ibc/polished/views/rear.png`; `assets/v3/previews/ibc/rear.png`; `assets/v3/qa-browser/ibc/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/ibc/initial/views/three-quarter.png`; `assets/v3/iterations/ibc/polished/views/three-quarter.png`; `assets/v3/previews/ibc/three-quarter.png`; `assets/v3/qa-browser/ibc/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/ibc.stats.json`; `assets/v3/iterations/ibc/candidate/dimension-plan.json`; `assets/v3/iterations/ibc/candidate/geometry-checks.json`; `assets/v3/iterations/ibc/candidate/ibc.stats.json`; `assets/v3/iterations/ibc/candidate/source-metrics.json`; `assets/v3/iterations/ibc/initial/dimension-plan.json`; `assets/v3/iterations/ibc/initial/source-metrics.json`; `assets/v3/iterations/ibc/polished/dimension-plan.json`; `assets/v3/iterations/ibc/polished/geometry-checks.json`; `assets/v3/iterations/ibc/polished/source-metrics.json`; `assets/v3/iterations/ibc/refined/dimension-plan.json`; `assets/v3/iterations/ibc/refined/source-metrics.json`; `assets/v3/iterations/ibc/stem-clean/binary-checks.json`; `assets/v3/iterations/ibc/stem-clean/dimension-plan.json`; `assets/v3/iterations/ibc/stem-clean/geometry-checks.json`; `assets/v3/iterations/ibc/stem-clean/source-metrics.json`; `assets/v3/iterations/ibc/stem-clean/source-preservation.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/previews/ibc/provenance.json`; `assets/v3/qa-browser/ibc/browser-capture.json`; `docs/adaptive-v3/evidence/M09.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### large-gate

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/large-gate.blend` — 104456 bytes; SHA256 `7aca285f38e239ba24fda7136f428c08a67b411a192c93a930b75c3debc22ba2` (present).
- model: `frontend/public/models/v3/large-gate.glb` — 53980 bytes; SHA256 `9ba0769f4fadd6f89e95deef8d04cd4b851070febb458f91a25ccdbdd6e6fb14` (present).
- stats: `assets/v3/blender/large-gate.stats.json` — 14739 bytes; SHA256 `338ca8664ed5672e275c1a2ea7c0d52ba62f1465627ab081fdc0e8cb88eb4639` (present).
- Engineering qualification: Accepted .25 m wall band and clear passage govern frame dimensions; no scale stretching.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate/P09.2/iteration-01/front.png`; `assets/v3/previews/large-gate/front.png`; `assets/v3/qa-browser/large-gate/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate/P09.2/iteration-01/side.png`; `assets/v3/previews/large-gate/side.png`; `assets/v3/qa-browser/large-gate/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate/P09.2/iteration-01/rear.png`; `assets/v3/previews/large-gate/rear.png`; `assets/v3/qa-browser/large-gate/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate/P09.2/iteration-01/three-quarter.png`; `assets/v3/previews/large-gate/three-quarter.png`; `assets/v3/qa-browser/large-gate/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/large-gate.stats.json`; `assets/v3/iterations/large-gate/P09.2/actual-glb-checks.json`; `assets/v3/iterations/large-gate/P09.2/iteration-01.actual-source-checks.json`; `assets/v3/iterations/large-gate/P09.2/iteration-01.source.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/large-gate/provenance.json`; `assets/v3/qa-browser/large-gate/browser-capture.json`; `assets/v3/specs/environment-shell.dimensions.json`; `docs/adaptive-v3/evidence/P09.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### large-gate-b2b

Reference: R07. Current review: **unreviewed**.

- source: `assets/v3/blender/large-gate-b2b.blend` — 104482 bytes; SHA256 `d724673b58a9f5d37041e8cd8f5a026f4b6d68552c11d6a64720b165ffdf365c` (present).
- model: `frontend/public/models/v3/large-gate-b2b.glb` — 54024 bytes; SHA256 `d5cd6818e16ce47e7011351fc221b0b959c997b4724da93d9139bfa087327d0f` (present).
- stats: `assets/v3/blender/large-gate-b2b.stats.json` — 15019 bytes; SHA256 `4309a09e0338967fed4e66f565c50bfe44903e68da0145ab91f88c806a5744ff` (present).
- Engineering qualification: Separate gate variant; accepted .25 m wall band and B2B clear passage govern geometry.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01/front.png`; `assets/v3/previews/large-gate-b2b/front.png`; `assets/v3/qa-browser/large-gate-b2b/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01/side.png`; `assets/v3/previews/large-gate-b2b/side.png`; `assets/v3/qa-browser/large-gate-b2b/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01/rear.png`; `assets/v3/previews/large-gate-b2b/rear.png`; `assets/v3/qa-browser/large-gate-b2b/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01/three-quarter.png`; `assets/v3/previews/large-gate-b2b/three-quarter.png`; `assets/v3/qa-browser/large-gate-b2b/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/large-gate-b2b.stats.json`; `assets/v3/iterations/large-gate-b2b/P09.2/actual-glb-checks.json`; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01.actual-source-checks.json`; `assets/v3/iterations/large-gate-b2b/P09.2/iteration-01.source.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/large-gate-b2b/provenance.json`; `assets/v3/qa-browser/large-gate-b2b/browser-capture.json`; `assets/v3/specs/environment-shell.dimensions.json`; `docs/adaptive-v3/evidence/P09.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### layout-engineering

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/layout-engineering.blend` — 1418522 bytes; SHA256 `78f5aae3da682ce878b3b967b67cb96f8d0a23168ebd7ad9d08028b16d860019` (present).
- model: `frontend/public/models/v3/layout-engineering.glb` — 1003940 bytes; SHA256 `022126b86b6089bb48dac984bd77eb71c41f676fcc4a86e1c47c4ed54c1eed3f` (present).
- stats: `assets/v3/blender/layout-engineering.stats.json` — 1640789 bytes; SHA256 `3ccc1d24bfd950018b0cd35d664fd547e1b74c2ccb81c17de13ef537a84eaeee` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/previews/layout-engineering/front.png`; `assets/v3/qa-browser/layout-engineering/front.png`
- side: **unbound / unreviewed**; `assets/v3/previews/layout-engineering/side.png`; `assets/v3/qa-browser/layout-engineering/side.png`
- rear: **unbound / unreviewed**; `assets/v3/previews/layout-engineering/rear.png`; `assets/v3/qa-browser/layout-engineering/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/previews/layout-engineering/three-quarter.png`; `assets/v3/qa-browser/layout-engineering/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/layout-engineering.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/layout-engineering/binary-check.json`; `assets/v3/previews/layout-engineering/render-report.json`; `assets/v3/qa-browser/layout-engineering/browser-capture.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-bundle

Reference: M10_METAL_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/long-bundle.blend` — 122599 bytes; SHA256 `6dc1dfbfb5b710f944cf24de9130bbe6d272a558f3a2dc81a7dd58da5f96d66f` (present).
- model: `frontend/public/models/v3/long-bundle.glb` — 211896 bytes; SHA256 `8e2659783485decda0f21ee20e68a32c5e7faf1cc1d346989bfca822e8907d7b` (present).
- stats: `assets/v3/blender/long-bundle.stats.json` — 23175 bytes; SHA256 `97608cb93b76d8735e935b4e814b0e4dafaa303733ce14ba72c8ac71e6cb1368` (present).
- Engineering qualification: M10_METAL_REF is the bound metal bundle concept; original wood-like concept is historical.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-bundle/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-bundle/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-bundle/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-bundle/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-bundle.stats.json`; `assets/v3/iterations/long-bundle/M10-01/mesh-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/long-bundle/browser-capture.json`; `assets/v3/qa-browser/long-bundle/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M10.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### long-cradle

Reference: M14_LONG_LOCK_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/long-cradle.blend` — 132895 bytes; SHA256 `d16d9d77ed133de1d94dbf31684c690b52d4ff35c29fc9c0d7288a07856501e0` (present).
- model: `frontend/public/models/v3/long-cradle.glb` — 234472 bytes; SHA256 `5fc1251b9408ad0b942f413412e04b60ef90ad36b57564365ba8e7e27d93c8ed` (present).
- stats: `assets/v3/blender/long-cradle.stats.json` — 8884 bytes; SHA256 `45704f460bce2d2915f2ac16834bee9aeaf8c9c7a2d8c83ebe5aeda6a5c1d62e` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-cradle.stats.json`; `assets/v3/iterations/long-cradle/M14.6.2/actual-mesh-and-contact-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/long-cradle/actual-glb-geometry.json`; `assets/v3/qa-browser/long-cradle/browser-capture.json`; `assets/v3/qa-browser/long-cradle/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M14.6.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3-support-kit-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-cradle-loaded-fixture

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/long-cradle-loaded-fixture.blend` — 178331 bytes; SHA256 `ebf62760ea998db4f531219b8409232089ea12a6511c0285ac273eea1851ccb1` (present).
- model: `frontend/public/models/v3/long-cradle-loaded-fixture.glb` — 581620 bytes; SHA256 `737db9a931626b8554db15c8c1f71cc3dd5ce4628b301976aea26a6cc7497758` (present).
- stats: `assets/v3/blender/long-cradle-loaded-fixture.stats.json` — 45862 bytes; SHA256 `2602f5da06b62d1b0c733161bb7e3c0e2ce7324dfc02f163f81bbf54129ae3d2` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle-loaded-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle-loaded-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle-loaded-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-cradle-loaded-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-cradle-loaded-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-cradle-loaded-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/long-cradle-loaded-fixture/browser-capture.json`; `assets/v3/qa-browser/long-cradle-loaded-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-rack

Reference: M04_TRANSFER_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/long-rack.blend` — 106546 bytes; SHA256 `b82687763560277c71be4842dc94fcc88865e1e31ce57d9463a73cb29eff3ccc` (present).
- model: `frontend/public/models/v3/long-rack.glb` — 56364 bytes; SHA256 `cb11977f459880bb1a55cf81e37b63491205454be024faa7ab080434a39621db` (present).
- stats: `assets/v3/blender/long-rack.stats.json` — 11018 bytes; SHA256 `4c70236149241ec545ac93422e2ed40be1a9418ff9197ddb80328dc346d938cc` (present).
- Engineering qualification: M04_TRANSFER_REF supersedes original R13.4 topology; paired rack/transfer supports are engineering refinements, not shrink-to-fit.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-rack.stats.json`; `assets/v3/iterations/long-rack/M04-01/mesh-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-rack/browser-capture.json`; `assets/v3/qa-browser/long-rack/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M04.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### long-rack-loaded-fixture

Reference: M04_TRANSFER_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/long-rack-loaded-fixture.blend` — 143671 bytes; SHA256 `f071c279b6bec64c8586b31afd8d14b17206ed3eb85d895c75dfeb335b09465b` (present).
- model: `frontend/public/models/v3/long-rack-loaded-fixture.glb` — 292916 bytes; SHA256 `acd48afda1b0af4b071da421864d31f711a498279e558dd5eb4c388d306cf0ef` (present).
- stats: `assets/v3/blender/long-rack-loaded-fixture.stats.json` — 36655 bytes; SHA256 `8c8753c1aa17eb053a43a459ad226c693ec9e66a854c09f5dc14ae271c40cb97` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-loaded-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-loaded-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-loaded-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-loaded-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-rack-loaded-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-rack-loaded-fixture/browser-capture.json`; `assets/v3/qa-browser/long-rack-loaded-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-rack-release-fixture

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/long-rack-release-fixture.blend` — 239783 bytes; SHA256 `870e6319c154c064e8b7609110abc5fbf2472a6f213b4b476a4111b4aeffbabf` (present).
- model: `frontend/public/models/v3/long-rack-release-fixture.glb` — 937856 bytes; SHA256 `346e88692e2d7230f008d49c4a929bba9515f018c8a61e178cc64b9a58e011ca` (present).
- stats: `assets/v3/blender/long-rack-release-fixture.stats.json` — 80784 bytes; SHA256 `3f02cbddab8cd75a2e194fd3f3c3f12e06fdeae16b97ca048fb74ec5b33b6c52` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-release-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-release-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-release-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-rack-release-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-rack-release-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-rack-release-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/long-rack-release-fixture/browser-capture.json`; `assets/v3/qa-browser/long-rack-release-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-restraint-rig

Reference: unresolved; no independent concept binding established. Current review: **unreviewed**.

- source: `assets/v3/blender/long-restraint-rig.blend` — 115288 bytes; SHA256 `5806f1d1d03f3447641e1179bdc9911aa46463afdea7e355d148c51719e2fd6e` (present).
- model: `frontend/public/models/v3/long-restraint-rig.glb` — 134992 bytes; SHA256 `49f997146d9fe09b9caba276eb1db30124f71c59a8aa559df67b18dc1c1486d8` (present).
- stats: `assets/v3/blender/long-restraint-rig.stats.json` — 16709 bytes; SHA256 `bca8a452ece578a6fc97764afaeb08766011c8a61975b5331e343e8586016bc5` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-restraint-rig/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-restraint-rig/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-restraint-rig/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-restraint-rig/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-restraint-rig.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-restraint-rig/actual-glb-geometry.json`; `assets/v3/qa-browser/long-restraint-rig/browser-capture.json`; `assets/v3/qa-browser/long-restraint-rig/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3-support-kit-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### long-transfer-interface-fixture

Reference: M04_TRANSFER_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/long-transfer-interface-fixture.blend` — 114010 bytes; SHA256 `f7d270526a39c468fe74c40154e7364f12c6f8d29082972da7c0ae33bc10dc6e` (present).
- model: `frontend/public/models/v3/long-transfer-interface-fixture.glb` — 81448 bytes; SHA256 `af51f9659f380a8d31d6eb3ec9187e839c9bc228a9266a54032b26f5b7e59d04` (present).
- stats: `assets/v3/blender/long-transfer-interface-fixture.stats.json` — 15119 bytes; SHA256 `c6ee2581683090396f129069f739e3050d9b93bff8ca3004b14121c2a0c26afe` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/long-transfer-interface-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/long-transfer-interface-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/long-transfer-interface-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/long-transfer-interface-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/long-transfer-interface-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/long-transfer-interface-fixture/browser-capture.json`; `assets/v3/qa-browser/long-transfer-interface-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### manual-cart-walk

Reference: R11. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-manual.blend` — 149924 bytes; SHA256 `cbaf236121536ff75b918ece4de89601556977ac7091f79bc4d12b0ba48a0423` (present).
- model: `frontend/public/models/v3/worker-manual.glb` — 192732 bytes; SHA256 `dbf74a8d2aa4f7bb60cca547b90a4e973d9691038aee614f51eb4269d8d18875` (present).
- stats: `assets/v3/blender/worker-manual.stats.json` — 43700 bytes; SHA256 `3968ebeb177a39f5f234488418ebb5e4e65e899bc773db405d9cda534d318f5c` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: `assets/v3/blender/worker-manual.stats.json`; `assets/v3/iterations/packer/P04.1/actual-workcell.json`; `assets/v3/iterations/packer/P04.1/front-tail-R-native.json`; `assets/v3/iterations/packer/P04.1/hand-interface.json`; `assets/v3/iterations/packer/P04.1/table-L-native.json`; `assets/v3/iterations/packer/P04.2/actual-native-checks.json`; `assets/v3/iterations/packer/P04.2/actual-runtime-checks.json`; `assets/v3/iterations/packer/P04.2/runtime-native-poses.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.1/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.2/browser-preview/browser-checks.json`; `assets/v3/iterations/receiver/P05.2/native-contact-search.json`; `assets/v3/iterations/receiver/P05.2/native-path-checks.json`; `assets/v3/iterations/receiver/P05.2/native-rejections.json`; `assets/v3/iterations/receiver/P05.2/rear-layout-probe.json`; `assets/v3/iterations/receiver/P05.2/runtime-native-poses.json`; `assets/v3/iterations/receiver/P05.2/upper-status-block-rejected-native-contact-search.json`; `assets/v3/iterations/receiver/P05.3/browser/browser-checks.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/shipper/P06.2/browser-preview/browser-checks.json`; `assets/v3/iterations/shipper/P06.2/native-path-checks.json`; `assets/v3/iterations/shipper/P06.2/native-rejections.json`; `assets/v3/iterations/shipper/P06.2/runtime-native-poses.json`; `assets/v3/iterations/shipper/P06.3/browser/browser-checks.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-carry-pose.json`; `assets/v3/iterations/warehouse/W04.3/carry-candidate-browser/review-capture.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-runtime-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/qa-browser/manual-cart-walk/browser-checks.json`; `assets/v3/specs/receiver-workcell.dimensions.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/P03.4.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P04.1.json`; `docs/adaptive-v3/evidence/P04.2.json`; `docs/adaptive-v3/evidence/P05.1.json`; `docs/adaptive-v3/evidence/P05.2.json`; `docs/adaptive-v3/evidence/P05.3.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/P06.2.json`; `docs/adaptive-v3/evidence/P06.3.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3-support-kit-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### order-tote

Reference: M07.1_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/order-tote.blend` — 122190 bytes; SHA256 `d3304052abed4f67a9581a4a97b3715fdf1400ebb4e17b6a87d16dbc7b012319` (present).
- model: `frontend/public/models/v3/order-tote.glb` — 150256 bytes; SHA256 `4ae6a88d1cd99f0a2343d77e849c508b0f4fdd3d80e0d1b0ae9187e4e7c2f4d3` (present).
- stats: `assets/v3/blender/order-tote.stats.json` — 26801 bytes; SHA256 `f5960515f31b05365a2a3f569b43a668332b7e6a1a3150115a256fcbb2099f05` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/order-tote/M07.1-01/front.png`; `assets/v3/previews/order-tote/front.png`; `assets/v3/qa-browser/order-tote/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/order-tote/M07.1-01/side.png`; `assets/v3/previews/order-tote/side.png`; `assets/v3/qa-browser/order-tote/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/order-tote/M07.1-01/rear.png`; `assets/v3/previews/order-tote/rear.png`; `assets/v3/qa-browser/order-tote/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/order-tote/M07.1-01/three-quarter.png`; `assets/v3/previews/order-tote/three-quarter.png`; `assets/v3/qa-browser/order-tote/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/order-tote.stats.json`; `assets/v3/iterations/order-tote/M07.1-01/M07.1-evidence.json`; `assets/v3/iterations/order-tote/M07.1-01/order-tote.dimensions.json`; `assets/v3/iterations/order-tote/M07.1-01/order-tote.geometry.json`; `assets/v3/iterations/order-tote/M07.1-01/order-tote.stats.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/sealed-parcel/M07.2-01/mesh-checks.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/qa-browser/order-tote/browser-capture.json`; `assets/v3/qa-browser/order-tote/browser-lifecycle.json`; `assets/v3/specs/sealed-parcel.dimensions.json`; `assets/v3/specs/sealed-parcel.geometry.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/M07.1.json`; `docs/adaptive-v3/evidence/M07.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### packer-workcell-fixture

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/packer-workcell-fixture.blend` — 206552 bytes; SHA256 `b0b1fac1ea032a0aa574ee7781a9bc8ed6af8be4f2936f6560d7a7da84939604` (present).
- model: `frontend/public/models/v3/packer-workcell-fixture.glb` — 389932 bytes; SHA256 `a378a056a09776b4b833befcce5cb36916ccd3a7dfd07c2050744cc41a339b5a` (present).
- stats: `assets/v3/blender/packer-workcell-fixture.stats.json` — 60508 bytes; SHA256 `7d95f15a035a635f2ddac0500684ce64cf1dd80e31044bbe154fc2e882c9edb5` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: `assets/v3/blender/packer-workcell-fixture.stats.json`; `assets/v3/iterations/packer/P04.1/front-tail-R-native.json`; `assets/v3/iterations/packer/P04.1/table-L-native.json`; `assets/v3/iterations/packer/P04.2/actual-native-checks.json`; `assets/v3/iterations/packer/P04.2/actual-runtime-checks.json`; `assets/v3/iterations/packer/P04.2/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/packer-workcell-fixture/actual-glb-geometry.json`; `docs/adaptive-v3/evidence/P04.2.json`; `docs/adaptive-v3/evidence/P04.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### packing-station

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/packing-station.blend` — 128521 bytes; SHA256 `39bd08428259e1bc062cb7621480ea76be3f3a25368429d29144994c493bf5ef` (present).
- model: `frontend/public/models/v3/packing-station.glb` — 155352 bytes; SHA256 `1eb7d31499634468ff2d835055f03e54eeb04bdb3a1ffaaa076591376d7ca304` (present).
- stats: `assets/v3/blender/packing-station.stats.json` — 26767 bytes; SHA256 `d5d602f6385190a88d7de389c0d9ea35689946afe7319ca0d01623e67af557b2` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/iterations/packing-station/P08.2/initial/views/front.png`; `assets/v3/iterations/packing-station/P08.2/views/front.png`; `assets/v3/iterations/packing-station/P08.3/initial/views/front.png`; `assets/v3/iterations/packing-station/P08.3/views/front.png`; `assets/v3/iterations/packing-station/P08.4/views/front.png`; `assets/v3/previews/packing-station/front.png`; `assets/v3/qa-browser/packing-station/front.png`
- side: **unbound / unreviewed**; `assets/v3/iterations/packing-station/P08.2/initial/views/side.png`; `assets/v3/iterations/packing-station/P08.2/views/side.png`; `assets/v3/iterations/packing-station/P08.3/initial/views/side.png`; `assets/v3/iterations/packing-station/P08.3/views/side.png`; `assets/v3/iterations/packing-station/P08.4/views/side.png`; `assets/v3/previews/packing-station/side.png`; `assets/v3/qa-browser/packing-station/side.png`
- rear: **unbound / unreviewed**; `assets/v3/iterations/packing-station/P08.2/initial/views/rear.png`; `assets/v3/iterations/packing-station/P08.2/views/rear.png`; `assets/v3/iterations/packing-station/P08.3/initial/views/rear.png`; `assets/v3/iterations/packing-station/P08.3/views/rear.png`; `assets/v3/iterations/packing-station/P08.4/views/rear.png`; `assets/v3/previews/packing-station/rear.png`; `assets/v3/qa-browser/packing-station/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/packing-station/P08.2/initial/views/three-quarter.png`; `assets/v3/iterations/packing-station/P08.2/views/three-quarter.png`; `assets/v3/iterations/packing-station/P08.3/initial/views/three-quarter.png`; `assets/v3/iterations/packing-station/P08.3/views/three-quarter.png`; `assets/v3/iterations/packing-station/P08.4/views/three-quarter.png`; `assets/v3/previews/packing-station/three-quarter.png`; `assets/v3/qa-browser/packing-station/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/packing-station.stats.json`; `assets/v3/iterations/packer/P04.1/actual-workcell.json`; `assets/v3/iterations/packing-station/P08.2/geometry-checks.json`; `assets/v3/iterations/packing-station/P08.2/initial/source-metrics.json`; `assets/v3/iterations/packing-station/P08.2/source-metrics.json`; `assets/v3/iterations/packing-station/P08.3/geometry-checks.json`; `assets/v3/iterations/packing-station/P08.3/initial/source-metrics.json`; `assets/v3/iterations/packing-station/P08.3/source-metrics.json`; `assets/v3/iterations/packing-station/P08.4/device-measurements.json`; `assets/v3/iterations/packing-station/P08.4/pair-checks.json`; `assets/v3/iterations/packing-station/P08.4/source-metrics.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.1/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/packing-station/geometry-signatures.json`; `assets/v3/previews/packing-station/provenance.json`; `assets/v3/qa-browser/packing-station/browser-capture.json`; `assets/v3/specs/receiver-workcell.dimensions.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `docs/adaptive-v3/evidence/P04.1.json`; `docs/adaptive-v3/evidence/P05.1.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/P08.2.json`; `docs/adaptive-v3/evidence/P08.3.json`; `docs/adaptive-v3/evidence/P08.4.json`; `docs/adaptive-v3/evidence/P08.6.json`; `docs/adaptive-v3/evidence/P08.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### pallet

Reference: R03. Current review: **unreviewed**.

- source: `assets/v3/blender/pallet.blend` — None bytes; SHA256 `None` (missing).
- model: `frontend/public/models/v3/pallet.glb` — None bytes; SHA256 `None` (missing).
- stats: `assets/v3/blender/pallet.stats.json` — None bytes; SHA256 `None` (missing).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: missing explicit evidence association

### pallet-load

Reference: M08_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/pallet-load.blend` — 147866 bytes; SHA256 `9fad6db44929a7c33b21ac740c2b606b9ea083c333344a2d453e8abdfd86a6de` (present).
- model: `frontend/public/models/v3/pallet-load.glb` — 334892 bytes; SHA256 `4fa2fda74115016160ad9a4b8ee68ff178cc8a653159dc4f5266d99af7dd5c34` (present).
- stats: `assets/v3/blender/pallet-load.stats.json` — 35085 bytes; SHA256 `65e9482f0c4f1e2aac954cfc5ec7ee6ae5462c3fcf88905d3990d3012aeb73ab` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/pallet-load/initial/views/front.png`; `assets/v3/iterations/pallet-load/polished/views/front.png`; `assets/v3/previews/pallet-load/front.png`; `assets/v3/qa-browser/pallet-load/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/pallet-load/initial/views/side.png`; `assets/v3/iterations/pallet-load/polished/views/side.png`; `assets/v3/previews/pallet-load/side.png`; `assets/v3/qa-browser/pallet-load/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/pallet-load/initial/views/rear.png`; `assets/v3/iterations/pallet-load/polished/views/rear.png`; `assets/v3/previews/pallet-load/rear.png`; `assets/v3/qa-browser/pallet-load/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/pallet-load/initial/views/three-quarter.png`; `assets/v3/iterations/pallet-load/polished/views/three-quarter.png`; `assets/v3/previews/pallet-load/three-quarter.png`; `assets/v3/qa-browser/pallet-load/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/pallet-load.stats.json`; `assets/v3/iterations/pallet-load/candidate/binary-checks.json`; `assets/v3/iterations/pallet-load/candidate/dimension-plan.json`; `assets/v3/iterations/pallet-load/candidate/geometry-checks.json`; `assets/v3/iterations/pallet-load/candidate/source-metrics.json`; `assets/v3/iterations/pallet-load/candidate/source-preservation.json`; `assets/v3/iterations/pallet-load/initial/dimension-plan.json`; `assets/v3/iterations/pallet-load/initial/source-metrics.json`; `assets/v3/iterations/pallet-load/polished/dimension-plan.json`; `assets/v3/iterations/pallet-load/polished/geometry-checks.json`; `assets/v3/iterations/pallet-load/polished/source-metrics.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.1/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/previews/pallet-load/provenance.json`; `assets/v3/qa-browser/pallet-load/browser-capture.json`; `assets/v3/specs/receiver-workcell.dimensions.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `docs/adaptive-v3/evidence/M08.json`; `docs/adaptive-v3/evidence/P05.1.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### picker-cart-grip

Reference: R11. Current review: **unreviewed**.

- source: `assets/v3/blender/picker-figure.blend` — 145414 bytes; SHA256 `a1a04feca54fc457dea37e8ce04371eb75cf7bf0a52f4716287a2c2ca00284f8` (present).
- model: `frontend/public/models/v3/picker-figure.glb` — 183664 bytes; SHA256 `141eb4ded73ae4db903945de082d4fe5ae63f6c45a97e1e1bacd98d0653294d7` (present).
- stats: `assets/v3/blender/picker-figure.stats.json` — 38311 bytes; SHA256 `1d8b5978ec2b5e30ddbd08119cf7eb015749947f1582f4347bcd620e24089aac` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/picker-cart-grip/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/picker-cart-grip/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/picker-cart-grip/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/picker-cart-grip/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/picker-figure.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/picker-cart-grip/browser-capture.json`; `assets/v3/qa-browser/picker-cart-grip/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P03.3.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### picker-cart-walk

Reference: R11. Current review: **unreviewed**.

- source: `assets/v3/blender/picker-figure.blend` — 145414 bytes; SHA256 `a1a04feca54fc457dea37e8ce04371eb75cf7bf0a52f4716287a2c2ca00284f8` (present).
- model: `frontend/public/models/v3/picker-figure.glb` — 183664 bytes; SHA256 `141eb4ded73ae4db903945de082d4fe5ae63f6c45a97e1e1bacd98d0653294d7` (present).
- stats: `assets/v3/blender/picker-figure.stats.json` — 38311 bytes; SHA256 `1d8b5978ec2b5e30ddbd08119cf7eb015749947f1582f4347bcd620e24089aac` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: `assets/v3/blender/picker-figure.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/picker-cart-walk/browser-checks.json`; `docs/adaptive-v3/evidence/P03.4.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### picker-figure

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/picker-figure.blend` — 145414 bytes; SHA256 `a1a04feca54fc457dea37e8ce04371eb75cf7bf0a52f4716287a2c2ca00284f8` (present).
- model: `frontend/public/models/v3/picker-figure.glb` — 183664 bytes; SHA256 `141eb4ded73ae4db903945de082d4fe5ae63f6c45a97e1e1bacd98d0653294d7` (present).
- stats: `assets/v3/blender/picker-figure.stats.json` — 38311 bytes; SHA256 `1d8b5978ec2b5e30ddbd08119cf7eb015749947f1582f4347bcd620e24089aac` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/picker-figure/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/picker-figure/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/picker-figure/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/picker-figure/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/picker-figure.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/picker-figure/actual-glb-geometry.json`; `assets/v3/qa-browser/picker-figure/browser-capture.json`; `assets/v3/qa-browser/picker-figure/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### picker-pick-source-fixture

Reference: R13.1. Current review: **unreviewed**.

- source: `assets/v3/blender/picker-pick-source-fixture.blend` — 248347 bytes; SHA256 `2f0f95608f3d8732bda732128a32a1d8476374bbab331ecd92d108a7dc5a365d` (present).
- model: `frontend/public/models/v3/picker-pick-source-fixture.glb` — 752024 bytes; SHA256 `a02ea15b92d0280904fe0c2574b9d3248f7b0ec6bf6783bfc8289d13f480afe1` (present).
- stats: `assets/v3/blender/picker-pick-source-fixture.stats.json` — 121929 bytes; SHA256 `c30e814efb573825e3829088e12ebbb6d1ec73217db05fb7c94edcbb3ff9df48` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/picker-pick-source-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/picker-pick-source-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/picker-pick-source-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/quarter.png`; `assets/v3/qa-browser/picker-pick-source-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/picker-pick-source-fixture.stats.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/browser-capture.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/browser-lifecycle.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-path-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-rejections.json`; `assets/v3/iterations/worker-base/P03.5.3.3/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/first-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/fixed-torso-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/second-upright-rejected-native-plan.json`; `assets/v3/qa-browser/picker-pick-source-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/picker-pick-source-fixture/browser-capture.json`; `assets/v3/qa-browser/picker-pick-source-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P03.5.3.3.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### picker-worker

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/picker-worker.blend` — None bytes; SHA256 `None` (missing).
- model: `frontend/public/models/v3/picker-worker.glb` — None bytes; SHA256 `None` (missing).
- stats: `assets/v3/blender/picker-worker.stats.json` — None bytes; SHA256 `None` (missing).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **missing / unreviewed**; no explicit static-view candidate
- side: **missing / unreviewed**; no explicit static-view candidate
- rear: **missing / unreviewed**; no explicit static-view candidate
- three-quarter: **missing / unreviewed**; no explicit static-view candidate
- Native/runtime/task evidence: missing explicit evidence association

### picking-cart

Reference: R11. Current review: **unreviewed**.

- source: `assets/v3/blender/picking-cart.blend` — 133720 bytes; SHA256 `b58ae3fcd083df91d9240a860d20b623c2b0f64b80e71273eb990e19dc9f4919` (present).
- model: `frontend/public/models/v3/picking-cart.glb` — 279332 bytes; SHA256 `2176262c2022370019bdcd042dc1b36482cc5985fd0403fe1f62923498462a51` (present).
- stats: `assets/v3/blender/picking-cart.stats.json` — 35860 bytes; SHA256 `4cb66c318196bfeb9561c29311745ffe3053e3b4ea51b13d2c991f0e1fda1a55` (present).
- Engineering qualification: Current requested grip is overhand, top-down. Historical push/action captures alone do not establish the current correction or a four-view sheet.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart/front.png`
- side: **unbound / unreviewed**; `assets/v3/iterations/picking-cart/FIX01.2/browser/side.png`; `assets/v3/qa-browser/picking-cart/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/picking-cart/FIX01.2/browser/quarter.png`; `assets/v3/qa-browser/picking-cart/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/picking-cart.stats.json`; `assets/v3/iterations/picking-cart/FIX01.2/browser/browser-capture.json`; `assets/v3/iterations/picking-cart/FIX01.2/browser/browser-lifecycle.json`; `assets/v3/iterations/picking-cart/P03.2/actual-cart-checks.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.3/actual-runtime-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/qa-browser/picking-cart/actual-glb-geometry.json`; `assets/v3/qa-browser/picking-cart/browser-capture.json`; `assets/v3/qa-browser/picking-cart/browser-lifecycle.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/P03.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### picking-cart-tote-fixture

Reference: R11. Current review: **unreviewed**.

- source: `assets/v3/blender/picking-cart-tote-fixture.blend` — 161013 bytes; SHA256 `8940e356e1c0b82a5b890c083e5f8b1f57162294ccc93f5c25436763652003b8` (present).
- model: `frontend/public/models/v3/picking-cart-tote-fixture.glb` — 429140 bytes; SHA256 `d04225956f8ddfa5391bc32cb3e481a4906499c68983d2294b032679308dbc1c` (present).
- stats: `assets/v3/blender/picking-cart-tote-fixture.stats.json` — 61410 bytes; SHA256 `96de9598561306c4cfbc030ef4de8057bf78113eb892f29ec2bf3f9aa724bebe` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart-tote-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart-tote-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart-tote-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/picking-cart-tote-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/picking-cart-tote-fixture.stats.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-runtime-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json`; `assets/v3/qa-browser/picking-cart-tote-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/picking-cart-tote-fixture/browser-capture.json`; `assets/v3/qa-browser/picking-cart-tote-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3-support-kit-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### rack-small

Reference: R13.1. Current review: **unreviewed**.

- source: `assets/v3/blender/rack-small.blend` — 131044 bytes; SHA256 `14134f2e17526cfbf40780d76f459a3b11dc50acfaf19856c167039eb69c21ab` (present).
- model: `frontend/public/models/v3/rack-small.glb` — 164172 bytes; SHA256 `c7e80d1c799fd51ff25592b72defdd48724775934cd12f41f1a901ce130da4e7` (present).
- stats: `assets/v3/blender/rack-small.stats.json` — 26233 bytes; SHA256 `10f2c5c4417f343e47190d3f7e2502e9f08c558733972fdec9662e3fc50e3958` (present).
- Engineering qualification: Shallow front bins/rear strip and exact C04 metrics override raster proportions; see M01 approved_engineering_adaptations.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-small/initial/views/front.png`; `assets/v3/iterations/rack-small/refined-01/views/front.png`; `assets/v3/previews/rack-small/front.png`; `assets/v3/qa-browser/rack-small/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-small/initial/views/side.png`; `assets/v3/iterations/rack-small/refined-01/views/side.png`; `assets/v3/previews/rack-small/side.png`; `assets/v3/qa-browser/rack-small/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-small/initial/views/rear.png`; `assets/v3/iterations/rack-small/refined-01/views/rear.png`; `assets/v3/previews/rack-small/rear.png`; `assets/v3/qa-browser/rack-small/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-small/initial/views/three-quarter.png`; `assets/v3/iterations/rack-small/refined-01/views/three-quarter.png`; `assets/v3/previews/rack-small/three-quarter.png`; `assets/v3/qa-browser/rack-small/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/rack-small.stats.json`; `assets/v3/iterations/rack-small/candidate/binary-checks.json`; `assets/v3/iterations/rack-small/candidate/dimension-plan.json`; `assets/v3/iterations/rack-small/candidate/geometry-checks.json`; `assets/v3/iterations/rack-small/candidate/source-metrics.json`; `assets/v3/iterations/rack-small/initial/dimension-plan.json`; `assets/v3/iterations/rack-small/initial/source-metrics.json`; `assets/v3/iterations/rack-small/refined-01/dimension-plan.json`; `assets/v3/iterations/rack-small/refined-01/geometry-checks.json`; `assets/v3/iterations/rack-small/refined-01/source-metrics.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/previews/rack-small/provenance.json`; `assets/v3/qa-browser/rack-small/browser-capture.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/M01.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### rack-standard

Reference: R13.2. Current review: **unreviewed**.

- source: `assets/v3/blender/rack-standard.blend` — 137887 bytes; SHA256 `7fbf27a39e0e03c4628114cda7eedc7ec806d7cee05557dc8895993c721b0456` (present).
- model: `frontend/public/models/v3/rack-standard.glb` — 287448 bytes; SHA256 `5917721fd91de2dd755ec9929284ded8ceee5285366111f48145c8aa097ca866` (present).
- stats: `assets/v3/blender/rack-standard.stats.json` — 44966 bytes; SHA256 `4e2c4625645c8dc9514583167a39ce0a7f7790a9714b480042640782369effcc` (present).
- Engineering qualification: Accepted open-top ground fork lanes/ribs replace the closed concept deck; columns stay within .07 m envelopes. C08 metadata refresh is distinct from original geometry review.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-standard/M02-01/front.png`; `assets/v3/iterations/rack-standard/M02-02/front.png`; `assets/v3/previews/rack-standard/front.png`; `assets/v3/qa-browser/rack-standard/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-standard/M02-01/side.png`; `assets/v3/iterations/rack-standard/M02-02/side.png`; `assets/v3/previews/rack-standard/side.png`; `assets/v3/qa-browser/rack-standard/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-standard/M02-01/rear.png`; `assets/v3/iterations/rack-standard/M02-02/rear.png`; `assets/v3/previews/rack-standard/rear.png`; `assets/v3/qa-browser/rack-standard/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/rack-standard/M02-01/three-quarter.png`; `assets/v3/iterations/rack-standard/M02-02/three-quarter.png`; `assets/v3/previews/rack-standard/three-quarter.png`; `assets/v3/qa-browser/rack-standard/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/rack-standard.stats.json`; `assets/v3/iterations/rack-standard/M02-01/mesh-checks.json`; `assets/v3/iterations/rack-standard/M02-01/rack-standard.dimensions.json`; `assets/v3/iterations/rack-standard/M02-01/rack-standard.stats.json`; `assets/v3/iterations/rack-standard/M02-01/render-report.json`; `assets/v3/iterations/rack-standard/M02-02/mesh-checks.json`; `assets/v3/iterations/rack-standard/M02-02/rack-standard.dimensions.json`; `assets/v3/iterations/rack-standard/M02-02/rack-standard.stats.json`; `assets/v3/iterations/rack-standard/M02-02/render-report.json`; `assets/v3/iterations/rack-standard/M02-02/source-export-checks.json`; `assets/v3/iterations/rack-standard/M02-03-C08-v02/M02-evidence.json`; `assets/v3/iterations/rack-standard/M02-03-C08-v02/binding-refresh.json`; `assets/v3/iterations/rack-standard/M02-03-C08-v02/prior-evidence-with-root-review.json`; `assets/v3/iterations/rack-standard/M02-03-C08-v02/rack-standard.dimensions.json`; `assets/v3/iterations/rack-standard/M02-03-C08-v02/rack-standard.stats.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/rack-standard/browser-capture.json`; `docs/adaptive-v3/evidence/M02.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### receiver-workcell-fixture

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/receiver-workcell-fixture.blend` — 192304 bytes; SHA256 `9dfa64a4468b11568d80703decdd5f83acd9e218a655a1fb1618103f97faf614` (present).
- model: `frontend/public/models/v3/receiver-workcell-fixture.glb` — 492484 bytes; SHA256 `5eb51073d5c456f71ccc64c4bc231eadbf6761c6da89a96c4c87900dac1de54b` (present).
- stats: `assets/v3/blender/receiver-workcell-fixture.stats.json` — 61377 bytes; SHA256 `6d3f7a56c5d78f34b01f244a7387c0e4e4ebc7ca08a7819f2991f5d58f1b52f4` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/receiver-workcell-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/receiver-workcell-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/receiver-workcell-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/receiver-workcell-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/receiver-workcell-fixture.stats.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/receiver-workcell-fixture.stats.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/receiver-workcell-fixture.stats.json`; `assets/v3/iterations/receiver/P05.2/browser-preview/browser-checks.json`; `assets/v3/iterations/receiver/P05.2/native-contact-search.json`; `assets/v3/iterations/receiver/P05.2/native-path-checks.json`; `assets/v3/iterations/receiver/P05.2/native-rejections.json`; `assets/v3/iterations/receiver/P05.2/rear-layout-probe.json`; `assets/v3/iterations/receiver/P05.2/runtime-native-poses.json`; `assets/v3/iterations/receiver/P05.2/upper-status-block-rejected-native-contact-search.json`; `assets/v3/iterations/receiver/P05.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/receiver-workcell-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/receiver-workcell-fixture/browser-capture.json`; `assets/v3/qa-browser/receiver-workcell-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P05.2.json`; `docs/adaptive-v3/evidence/P05.3.json`; `docs/adaptive-v3/evidence/P05.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### sealed-parcel

Reference: M07.2_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/sealed-parcel.blend` — 120347 bytes; SHA256 `76ec815f554e6276c6273075702c1deee0f3e541bdd277daa52e4352f6162411` (present).
- model: `frontend/public/models/v3/sealed-parcel.glb` — 59692 bytes; SHA256 `885c238ff3a9533e7bfb5d25e8a157cc278758962a9565f95ec6895be236b8b7` (present).
- stats: `assets/v3/blender/sealed-parcel.stats.json` — 6465 bytes; SHA256 `f867351142cbeaac1c109f5538866f07fbe101e814ad4421eebd8d1fc9185725` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/sealed-parcel.stats.json`; `assets/v3/iterations/packer/P04.1/actual-workcell.json`; `assets/v3/iterations/sealed-parcel/M07.2-01/mesh-checks.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/sealed-parcel/browser-capture.json`; `assets/v3/qa-browser/sealed-parcel/browser-lifecycle.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `docs/adaptive-v3/evidence/M07.2.json`; `docs/adaptive-v3/evidence/P04.1.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### sealed-parcel-tote-fixture

Reference: M07.2_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/sealed-parcel-tote-fixture.blend` — 165664 bytes; SHA256 `e99153ca8ecc059fec4db31db7490251230c21592742f8a6f5577f0da5130056` (present).
- model: `frontend/public/models/v3/sealed-parcel-tote-fixture.glb` — 259772 bytes; SHA256 `9d9551835c170b1c0fc93f1028b4a5937046597b6a8c72db98b1745ddf3157ec` (present).
- stats: `assets/v3/blender/sealed-parcel-tote-fixture.stats.json` — 41011 bytes; SHA256 `f868f048eda469a5ab46144d4d6778c99fdf3f4de663268ca6b5409f1a6db658` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel-tote-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel-tote-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel-tote-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/sealed-parcel-tote-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/sealed-parcel-tote-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/sealed-parcel-tote-fixture/browser-capture.json`; `assets/v3/qa-browser/sealed-parcel-tote-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/M07.2.json`; `docs/adaptive-v3/evidence/M07.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### shipper-workcell-fixture

Reference: R04. Current review: **unreviewed**.

- source: `assets/v3/blender/shipper-workcell-fixture.blend` — 245420 bytes; SHA256 `879b998d6731d97abf1b80b1dcd7e07e7e5e19f3f62657ea3cb224107a006144` (present).
- model: `frontend/public/models/v3/shipper-workcell-fixture.glb` — 643440 bytes; SHA256 `c80ff7569413d6402f27dfc8c6d53b99d69ecb635a59bb551fcac470c4256ffe` (present).
- stats: `assets/v3/blender/shipper-workcell-fixture.stats.json` — 80411 bytes; SHA256 `7541d986d56d663fbea3ea2817a8bbf49e6a3fd92c16ef5fe6542dbeb331a60c` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/shipper-workcell-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/shipper-workcell-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/shipper-workcell-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/shipper-workcell-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/shipper-workcell-fixture.stats.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell-fixture.stats.json`; `assets/v3/iterations/shipper/P06.2/browser-preview/browser-checks.json`; `assets/v3/iterations/shipper/P06.2/native-path-checks.json`; `assets/v3/iterations/shipper/P06.2/native-rejections.json`; `assets/v3/iterations/shipper/P06.2/runtime-native-poses.json`; `assets/v3/iterations/shipper/P06.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/shipper-workcell-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/shipper-workcell-fixture/browser-capture.json`; `assets/v3/qa-browser/shipper-workcell-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P06.2.json`; `docs/adaptive-v3/evidence/P06.3.json`; `docs/adaptive-v3/evidence/P06.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### small-carton

Reference: M06.1_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/small-carton.blend` — 107114 bytes; SHA256 `209470b224993bb314f0d9adf175b2f97c8d0ba8642512f59594bfe942324996` (present).
- model: `frontend/public/models/v3/small-carton.glb` — 49300 bytes; SHA256 `10ae707579214c6ef87bf1897a04c35c59c913ca6093d5e511f8515c9354f317` (present).
- stats: `assets/v3/blender/small-carton.stats.json` — 10799 bytes; SHA256 `897d902ce762fc33c41e3a8a3d3dd698211d1ae5dac00304ebfff51d5f1c3e68` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/small-carton/M06.1-01/front.png`; `assets/v3/previews/small-carton/front.png`; `assets/v3/qa-browser/small-carton/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/small-carton/M06.1-01/side.png`; `assets/v3/previews/small-carton/side.png`; `assets/v3/qa-browser/small-carton/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/small-carton/M06.1-01/rear.png`; `assets/v3/previews/small-carton/rear.png`; `assets/v3/qa-browser/small-carton/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/quarter.png`; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/quarter.png`; `assets/v3/iterations/small-carton/M06.1-01/three-quarter.png`; `assets/v3/previews/small-carton/three-quarter.png`; `assets/v3/qa-browser/small-carton/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/small-carton.stats.json`; `assets/v3/iterations/sealed-parcel/M07.2-01/mesh-checks.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/browser-capture.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/picker-pick-source-fixture/browser-lifecycle.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/browser-capture.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/browser-lifecycle.json`; `assets/v3/iterations/small-carton/M06.1-01/mesh-checks.json`; `assets/v3/iterations/small-carton/M06.1-01/render-report.json`; `assets/v3/iterations/small-carton/M06.1-01/saved-source-checks.json`; `assets/v3/iterations/small-carton/M06.1-01/small-carton.dimensions.json`; `assets/v3/iterations/small-carton/M06.1-01/small-carton.stats.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-carry-pose.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/iterations/warehouse/W04.3/carry-candidate-browser/review-capture.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/qa-browser/small-carton/browser-capture.json`; `assets/v3/specs/sealed-parcel.dimensions.json`; `assets/v3/specs/sealed-parcel.geometry.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/M06.1.json`; `docs/adaptive-v3/evidence/M07.2.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### small-case-open-partial

Reference: M06.1_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/small-case-open-partial.blend` — 129255 bytes; SHA256 `ae2d189abcd3a87f3924752ae35df874aae89f722d5fbf025d0b88144e62c681` (present).
- model: `frontend/public/models/v3/small-case-open-partial.glb` — 159304 bytes; SHA256 `6c0159b4d68b6ee6258b3c85e7084e8b3967654ccf1381a0333dd6662ab11e7f` (present).
- stats: `assets/v3/blender/small-case-open-partial.stats.json` — 38381 bytes; SHA256 `2cfb06dbcdd91ee3940afb7e83684717b8afa3f574829b4275d6e7ec7c78318f` (present).
- Engineering qualification: Current requested opening has four outward upper carton flaps and fixed walls; current geometry/action must be reviewed against that correction.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/small-case-open-partial/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/small-case-open-partial/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/small-case-open-partial/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/quarter.png`; `assets/v3/qa-browser/small-case-open-partial/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/small-case-open-partial.stats.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/browser-capture.json`; `assets/v3/iterations/small-carton/FIX01.3/browser/small-case-open-partial/browser-lifecycle.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/small-case-open-partial/actual-glb-geometry.json`; `assets/v3/qa-browser/small-case-open-partial/browser-capture.json`; `assets/v3/qa-browser/small-case-open-partial/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### small-gripper-contact-fixture

Reference: P03_SMALL_GRIPPER_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/small-gripper-contact-fixture.blend` — 417951 bytes; SHA256 `b2a7f43d7f7c4d9cfdffa255ade077c48d89e6b2bd672ead15b05b60b2e89dff` (present).
- model: `frontend/public/models/v3/small-gripper-contact-fixture.glb` — 1371564 bytes; SHA256 `29b6e6f829c97c2086881a7a47cab2a4d8caa10749149665b315c5641a9fcde2` (present).
- stats: `assets/v3/blender/small-gripper-contact-fixture.stats.json` — 204295 bytes; SHA256 `f3aed4b334cb3350a97b269d4b373b1496c07f2445b6041f371af5c2d41f9a16` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/small-gripper-contact-fixture/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/small-gripper-contact-fixture/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/small-gripper-contact-fixture/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/small-gripper-contact-fixture/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/small-gripper-contact-fixture.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/small-gripper-contact-fixture/actual-glb-geometry.json`; `assets/v3/qa-browser/small-gripper-contact-fixture/browser-capture.json`; `assets/v3/qa-browser/small-gripper-contact-fixture/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### small-package-gripper

Reference: P03_SMALL_GRIPPER_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/small-package-gripper.blend` — 189609 bytes; SHA256 `c81e8974e145a3afd4617b5998ccfb8e70d25d4625228ba64aca51927bc4dc16` (present).
- model: `frontend/public/models/v3/small-package-gripper.glb` — 423112 bytes; SHA256 `4019fdc6d407c1d836f2b73ad258436acc2c2943e7c1b88b924ca47e0f99ec49` (present).
- stats: `assets/v3/blender/small-package-gripper.stats.json` — 41898 bytes; SHA256 `20c54f7f8c1930610cc26847426823cbd3c3f34663f85e4bb54c2372daa5c696` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/small-package-gripper/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/small-package-gripper/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/small-package-gripper/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/small-package-gripper/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/small-package-gripper.stats.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/clearance-calibration.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/contact-macro/browser-capture.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/contact-macro/browser-lifecycle.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/contact-orbit/browser-capture.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/contact-orbit/browser-lifecycle.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/geometry-states.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-mechanism-profiles.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/runtime-checks.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/saved-native-recheck.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/shared-stand-regression.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-path-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-rejections.json`; `assets/v3/iterations/worker-base/P03.5.3.3/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/first-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/fixed-torso-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/second-upright-rejected-native-plan.json`; `assets/v3/qa-browser/small-package-gripper/actual-glb-geometry.json`; `assets/v3/qa-browser/small-package-gripper/browser-capture.json`; `assets/v3/qa-browser/small-package-gripper/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P03.5.3.2.json`; `docs/adaptive-v3/evidence/P03.5.3.3.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### small-unit

Reference: M06.1_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/small-unit.blend` — 93206 bytes; SHA256 `89ddd86615a81896549de3b873d252c835f1bb7ed3f1ea52fbcc27f1a06183f2` (present).
- model: `frontend/public/models/v3/small-unit.glb` — 20276 bytes; SHA256 `592867e3bc0dd4281197738e667850bc26a960373bd8eba8801fb6887fb8ad79` (present).
- stats: `assets/v3/blender/small-unit.stats.json` — 6045 bytes; SHA256 `92ab1d87541875c0921b987d445c6a6c9f2ca9fe5dc537e88160f1e529d51735` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/small-unit/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/small-unit/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/small-unit/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/small-unit/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/small-unit.stats.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/qa-browser/small-unit/actual-glb-geometry.json`; `assets/v3/qa-browser/small-unit/browser-capture.json`; `assets/v3/qa-browser/small-unit/browser-lifecycle.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### standard-carton

Reference: M06.2_REF. Current review: **unreviewed**.

- source: `assets/v3/blender/standard-carton.blend` — 107183 bytes; SHA256 `7631ec8aad2fde4e60bf1ac0c09f81065977692484366eee3d5123238b84d0d5` (present).
- model: `frontend/public/models/v3/standard-carton.glb` — 50416 bytes; SHA256 `eaeb8b62e0451c28dd2468df0a8f6f904f6cd1bf67b6f8c3147a18b38a115721` (present).
- stats: `assets/v3/blender/standard-carton.stats.json` — 10850 bytes; SHA256 `dc13450c449bd66fb812268730ca1001941f59edf67fba32deda7761275b2c70` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **current-source-bound / unreviewed**; `assets/v3/iterations/standard-carton/M06.2-01/front.png`; `assets/v3/previews/standard-carton/front.png`; `assets/v3/qa-browser/standard-carton/front.png`
- side: **current-source-bound / unreviewed**; `assets/v3/iterations/standard-carton/M06.2-01/side.png`; `assets/v3/previews/standard-carton/side.png`; `assets/v3/qa-browser/standard-carton/side.png`
- rear: **current-source-bound / unreviewed**; `assets/v3/iterations/standard-carton/M06.2-01/rear.png`; `assets/v3/previews/standard-carton/rear.png`; `assets/v3/qa-browser/standard-carton/rear.png`
- three-quarter: **current-source-bound / unreviewed**; `assets/v3/iterations/standard-carton/M06.2-01/three-quarter.png`; `assets/v3/previews/standard-carton/three-quarter.png`; `assets/v3/qa-browser/standard-carton/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/standard-carton.stats.json`; `assets/v3/iterations/standard-carton/M06.2-01/M06.2-evidence.json`; `assets/v3/iterations/standard-carton/M06.2-01/mesh-checks.json`; `assets/v3/iterations/standard-carton/M06.2-01/render-report.json`; `assets/v3/iterations/standard-carton/M06.2-01/saved-source-checks.json`; `assets/v3/iterations/standard-carton/M06.2-01/standard-carton.dimensions.json`; `assets/v3/iterations/standard-carton/M06.2-01/standard-carton.stats.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-support-interfaces.json`; `assets/v3/qa-browser/standard-carton/browser-capture.json`; `assets/v3/qa-browser/standard-carton/failure.json`; `docs/adaptive-v3/evidence/M06.2.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-base

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Original base identity retained. Current requested rest palms face inward; historical neutral/pose acceptance does not establish this correction in current runtime.
- Warehouse binding: current; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/iterations/worker-base/P01.2/iteration-01/front.png`; `assets/v3/iterations/worker-base/P01.2/iteration-02/front.png`; `assets/v3/iterations/worker-base/P01.3/bent-arm/front.png`; `assets/v3/iterations/worker-base/P01.3/bent-knee/front.png`; `assets/v3/iterations/worker-base/P01.3/neutral/front.png`; `assets/v3/iterations/worker-base/P01.3/waist-bend/front.png`; `assets/v3/iterations/worker-base/P01.4/iteration-01/front.png`; `assets/v3/iterations/worker-base/P01.4/iteration-02/front.png`; `assets/v3/previews/worker-base/front.png`; `assets/v3/qa-browser/worker-base/front.png`
- side: **unbound / unreviewed**; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-base/side.png`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/side.png`; `assets/v3/iterations/worker-base/P01.2/iteration-01/side.png`; `assets/v3/iterations/worker-base/P01.2/iteration-02/side.png`; `assets/v3/iterations/worker-base/P01.3/bent-arm/side.png`; `assets/v3/iterations/worker-base/P01.3/bent-knee/side.png`; `assets/v3/iterations/worker-base/P01.3/neutral/side.png`; `assets/v3/iterations/worker-base/P01.3/waist-bend/side.png`; `assets/v3/iterations/worker-base/P01.4/iteration-01/side.png`; `assets/v3/iterations/worker-base/P01.4/iteration-02/side.png`; `assets/v3/iterations/worker-base/P03.5.1.1/browser/side.png`; `assets/v3/previews/worker-base/side.png`; `assets/v3/qa-browser/worker-base/side.png`
- rear: **unbound / unreviewed**; `assets/v3/iterations/worker-base/P01.2/iteration-01/rear.png`; `assets/v3/iterations/worker-base/P01.2/iteration-02/rear.png`; `assets/v3/iterations/worker-base/P01.3/bent-arm/rear.png`; `assets/v3/iterations/worker-base/P01.3/bent-knee/rear.png`; `assets/v3/iterations/worker-base/P01.3/neutral/rear.png`; `assets/v3/iterations/worker-base/P01.3/waist-bend/rear.png`; `assets/v3/iterations/worker-base/P01.4/iteration-01/rear.png`; `assets/v3/iterations/worker-base/P01.4/iteration-02/rear.png`; `assets/v3/previews/worker-base/rear.png`; `assets/v3/qa-browser/worker-base/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-base/quarter.png`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/quarter.png`; `assets/v3/iterations/worker-base/P01.2/iteration-01/three-quarter.png`; `assets/v3/iterations/worker-base/P01.2/iteration-02/three-quarter.png`; `assets/v3/iterations/worker-base/P01.3/bent-arm/three-quarter.png`; `assets/v3/iterations/worker-base/P01.3/bent-knee/three-quarter.png`; `assets/v3/iterations/worker-base/P01.3/neutral/three-quarter.png`; `assets/v3/iterations/worker-base/P01.3/waist-bend/three-quarter.png`; `assets/v3/iterations/worker-base/P01.4/iteration-01/three-quarter.png`; `assets/v3/iterations/worker-base/P01.4/iteration-02/three-quarter.png`; `assets/v3/iterations/worker-base/P03.5.1.1/browser/quarter.png`; `assets/v3/previews/worker-base/three-quarter.png`; `assets/v3/qa-browser/worker-base/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/FIX01.1/actual-neutral-palms.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-base/browser-capture.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-base/browser-lifecycle.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/browser-capture.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/browser-lifecycle.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.render.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.render.json`; `assets/v3/iterations/worker-base/P01.3/actual-mesh-checks.json`; `assets/v3/iterations/worker-base/P01.3/bent-arm.render.json`; `assets/v3/iterations/worker-base/P01.3/bent-knee.render.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.3/neutral.render.json`; `assets/v3/iterations/worker-base/P01.3/waist-bend.render.json`; `assets/v3/iterations/worker-base/P01.4/actual-detail-checks.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.render.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.actual-detail-checks.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.render.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1.1/actual-native-reach-controls.json`; `assets/v3/iterations/worker-base/P03.5.1.1/browser/browser-capture.json`; `assets/v3/iterations/worker-base/P03.5.1.1/browser/browser-lifecycle.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-runtime-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P03.5.3.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-path-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-rejections.json`; `assets/v3/iterations/worker-base/P03.5.3.3/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3.3/shared-stand-regression.json`; `assets/v3/iterations/worker-base/P03.5.3.3/thumb-transition-probe.json`; `assets/v3/iterations/worker-base/P03.5.3.3/visual-review.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-fixed-reach-probe/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-fixed-reach-probe/native-feasibility-body5-headminus0p6.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-fixed-reach-probe/native-feasibility-body5.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/clear-candidate-body7.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/clear-candidate.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/native-feasibility-body7.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/native-feasibility.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-reach-probe/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-reach-probe/clear-candidate-body5.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-reach-probe/clear-candidate.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-reach-probe/native-feasibility-body5.json`; `assets/v3/iterations/worker-base/P03.5.3/gripper-reach-probe/native-feasibility.json`; `assets/v3/iterations/worker-base/P03.5.3/pole-probe/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/pole-probe/native-feasibility.json`; `assets/v3/iterations/worker-base/P03.5.3/reach-probe/native-pick-feasibility.json`; `assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-clear-bodies.json`; `assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-search-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/side-pole-probe/bodies.json`; `assets/v3/iterations/worker-base/P03.5.3/side-pole-probe/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/side-pole-probe/native-feasibility.json`; `assets/v3/iterations/worker-base/P03.5.3/thumb-fold-probe/native-thumb-fold.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-body-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-body-reach/clear-deposit.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-body-reach/native-deposit-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-body-reach/positive-twist-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-body-reach/query.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/first-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/fixed-torso-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/fixed-torso-rejected-query.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/query.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/second-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-reach/clear-deposit.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-reach/native-deposit-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-reach/positive-twist-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-reach/query.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-bodies/bodies.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-pick-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-pick-reach/clear-candidate-body21.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-pick-reach/native-feasibility-body21.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-raised-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-raised-reach/clear-candidate-body21.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-raised-reach/native-feasibility-body21.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-fine-raised-reach/rejected-C-mouth-body21.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-predeposit-reach/candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-predeposit-reach/clear-deposit.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-predeposit-reach/native-deposit-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-predeposit-reach/positive-twist-candidates.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-predeposit-reach/query.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-base/P07/actual-runtime-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/qa-browser/worker-base/actual-glb-geometry.json`; `assets/v3/qa-browser/worker-base/browser-capture.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-manual

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-manual.blend` — 149924 bytes; SHA256 `cbaf236121536ff75b918ece4de89601556977ac7091f79bc4d12b0ba48a0423` (present).
- model: `frontend/public/models/v3/worker-manual.glb` — 192732 bytes; SHA256 `dbf74a8d2aa4f7bb60cca547b90a4e973d9691038aee614f51eb4269d8d18875` (present).
- stats: `assets/v3/blender/worker-manual.stats.json` — 43700 bytes; SHA256 `3968ebeb177a39f5f234488418ebb5e4e65e899bc773db405d9cda534d318f5c` (present).
- Engineering qualification: Additive articulated derivative preserves original body identity; current requested rest palms face inward. Historical thumb/rig checks are bounded fixtures.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-manual/front.png`
- side: **unbound / unreviewed**; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/side.png`; `assets/v3/qa-browser/worker-manual/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-manual/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/quarter.png`; `assets/v3/qa-browser/worker-manual/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-manual.stats.json`; `assets/v3/iterations/packer/P04.1/actual-workcell.json`; `assets/v3/iterations/packer/P04.1/front-tail-R-native.json`; `assets/v3/iterations/packer/P04.1/hand-interface.json`; `assets/v3/iterations/packer/P04.1/table-L-native.json`; `assets/v3/iterations/packer/P04.2/actual-native-checks.json`; `assets/v3/iterations/packer/P04.2/actual-runtime-checks.json`; `assets/v3/iterations/packer/P04.2/runtime-native-poses.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/initial-front-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.1/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/P05.1.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/native-workcell.json`; `assets/v3/iterations/receiver/P05.1/side-facing-terminal/receiver-workcell.dimensions.json`; `assets/v3/iterations/receiver/P05.2/browser-preview/browser-checks.json`; `assets/v3/iterations/receiver/P05.2/native-contact-search.json`; `assets/v3/iterations/receiver/P05.2/native-path-checks.json`; `assets/v3/iterations/receiver/P05.2/native-rejections.json`; `assets/v3/iterations/receiver/P05.2/rear-layout-probe.json`; `assets/v3/iterations/receiver/P05.2/runtime-native-poses.json`; `assets/v3/iterations/receiver/P05.2/upper-status-block-rejected-native-contact-search.json`; `assets/v3/iterations/receiver/P05.3/browser/browser-checks.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/P06.1.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/native-workcell.json`; `assets/v3/iterations/shipper/P06.1/initial-short-service/shipper-workcell.dimensions.json`; `assets/v3/iterations/shipper/P06.1/native-workcell.json`; `assets/v3/iterations/shipper/P06.2/browser-preview/browser-checks.json`; `assets/v3/iterations/shipper/P06.2/native-path-checks.json`; `assets/v3/iterations/shipper/P06.2/native-rejections.json`; `assets/v3/iterations/shipper/P06.2/runtime-native-poses.json`; `assets/v3/iterations/shipper/P06.3/browser/browser-checks.json`; `assets/v3/iterations/small-carton/P03.5.2/actual-small-pick-source-checks.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/candidate-carry-pose.json`; `assets/v3/iterations/warehouse/W04.3/carry-candidate-browser/review-capture.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/browser-capture.json`; `assets/v3/iterations/worker-base/FIX01.1/browser/worker-manual/browser-lifecycle.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-native-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/actual-runtime-walk-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/qa-browser/worker-manual/actual-glb-geometry.json`; `assets/v3/qa-browser/worker-manual/browser-capture.json`; `assets/v3/qa-browser/worker-manual/browser-lifecycle.json`; `assets/v3/specs/receiver-workcell.dimensions.json`; `assets/v3/specs/shipper-workcell.dimensions.json`; `assets/v3/specs/small-pick-source.geometry.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P04.1.json`; `docs/adaptive-v3/evidence/P04.2.json`; `docs/adaptive-v3/evidence/P05.1.json`; `docs/adaptive-v3/evidence/P05.2.json`; `docs/adaptive-v3/evidence/P05.3.json`; `docs/adaptive-v3/evidence/P06.1.json`; `docs/adaptive-v3/evidence/P06.2.json`; `docs/adaptive-v3/evidence/P06.3.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-holder-state-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3-support-kit-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

### worker-role-F01

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/F01-front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/F01-side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/F01-rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/F01-quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P02.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-role-K01

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/K01-front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/K01-side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/K01-rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/K01-quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P02.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-role-P01

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/P01-front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/P01-side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/P01-rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/P01-quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P02.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-role-R01

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/R01-front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/R01-side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/R01-rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/R01-quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P02.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-role-S01

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-base.blend` — 141044 bytes; SHA256 `23950616b324a8520b364427396bde8c4bcba337b182b5d4fd14e7253dc2fcb5` (present).
- model: `frontend/public/models/v3/worker-base.glb` — 183028 bytes; SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` (present).
- stats: `assets/v3/blender/worker-base.stats.json` — 38301 bytes; SHA256 `c9c6d294b85f296e3d1486ab95d14c9d806936f63ea89cf8fa73c1e6af6fb32f` (present).
- Engineering qualification: Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/S01-front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/S01-side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/S01-rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-roles/S01-quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-base.stats.json`; `assets/v3/iterations/forklift/M14.3/front-axle-repair/before/M14.3/forklift-cab-stage.json`; `assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-native-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/actual-runtime-walk-checks.json`; `assets/v3/iterations/picking-cart/P03.4/runtime-native-poses.json`; `assets/v3/iterations/warehouse/W02.2/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W02.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-after-pool-origin.json`; `assets/v3/iterations/warehouse/W04.2/browser/precision-probe-before-policy.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/carry-native/native-checks.json`; `assets/v3/iterations/worker-base/P01.2/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.2/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P01.3/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-01.numeric.json`; `assets/v3/iterations/worker-base/P01.4/iteration-02.numeric.json`; `assets/v3/iterations/worker-base/P03.1/actual-picker-figure-checks.json`; `assets/v3/iterations/worker-base/P03.5.1/actual-manual-rig-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3.1/native-thumb-rig.json`; `assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/previews/worker-base/provenance.json`; `assets/v3/specs/forklift-cab-stage.json`; `assets/v3/specs/forklift.dimensions.json`; `assets/v3/specs/worker-rig-qa.json`; `assets/v3/specs/worker-roles.json`; `docs/adaptive-v3/evidence/P01.2.json`; `docs/adaptive-v3/evidence/P01.3.json`; `docs/adaptive-v3/evidence/P01.4.json`; `docs/adaptive-v3/evidence/P01.5.json`; `docs/adaptive-v3/evidence/P01.6.json`; `docs/adaptive-v3/evidence/P01.7.json`; `docs/adaptive-v3/evidence/P01.json`; `docs/adaptive-v3/evidence/P02.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.2.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json`; `docs/adaptive-v3/evidence/W04.3-scene-clearance-historical-defect.json`; `docs/adaptive-v3/evidence/W04.3.json`; `frontend/src/adaptive-v3/warehouseAssetBindings.json`

### worker-small-pick

Reference: R05. Current review: **unreviewed**.

- source: `assets/v3/blender/worker-small-pick.blend` — 149429 bytes; SHA256 `1bb90d350a1690e11944142e8f5df1cfa18abe54861a007a79bc4be3830a2e80` (present).
- model: `frontend/public/models/v3/worker-small-pick.glb` — 193540 bytes; SHA256 `195035d778ba1ed279bb49341441a101b7983a4c14c88ab960ab3af8d13c19c0` (present).
- stats: `assets/v3/blender/worker-small-pick.stats.json` — 44184 bytes; SHA256 `4242b6496c4b9aa669167d47046e6c3921179f4f50313cb0803070fcee275d4f` (present).
- Engineering qualification: See exact task/spec assertions; no geometry judgement inferred from filenames or source renders.
- Warehouse binding: absent; historical acceptance is separate from source binding.
- front: **unbound / unreviewed**; `assets/v3/qa-browser/worker-small-pick/front.png`
- side: **unbound / unreviewed**; `assets/v3/qa-browser/worker-small-pick/side.png`
- rear: **unbound / unreviewed**; `assets/v3/qa-browser/worker-small-pick/rear.png`
- three-quarter: **unbound / unreviewed**; `assets/v3/qa-browser/worker-small-pick/quarter.png`
- Native/runtime/task evidence: `assets/v3/blender/worker-small-pick.stats.json`; `assets/v3/iterations/small-package-gripper/P03.5.3.2/native-contacts.json`; `assets/v3/iterations/warehouse/W04.3/browser-preview/browser-checks.json`; `assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/browser/browser-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-path-checks.json`; `assets/v3/iterations/worker-base/P03.5.3.3/native-rejections.json`; `assets/v3/iterations/worker-base/P03.5.3.3/runtime-native-poses.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/first-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/fixed-torso-rejected-native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/native-plan.json`; `assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach/second-upright-rejected-native-plan.json`; `assets/v3/iterations/worker-registry/P10.1/registry-checks.json`; `assets/v3/qa-browser/worker-small-pick/actual-glb-geometry.json`; `assets/v3/qa-browser/worker-small-pick/browser-capture.json`; `assets/v3/qa-browser/worker-small-pick/browser-lifecycle.json`; `docs/adaptive-v3/evidence/P03.5.3.3.1.json`; `docs/adaptive-v3/evidence/P03.5.3.3.json`; `docs/adaptive-v3/evidence/P10.1.json`; `docs/adaptive-v3/evidence/W04.3-browser-checks.json`; `docs/adaptive-v3/evidence/W04.3-browser-preview-checks.json`; `docs/adaptive-v3/evidence/W04.3.json`

## Reproduce

```powershell
.venv/Scripts/python.exe tools/visual/v3/build_reference_render_matrix.py
.venv/Scripts/python.exe tools/visual/v3/build_reference_render_matrix.py --check-only
```

Normal mode writes only this Markdown and its companion JSON. Check-only recomputes bytes without writes and fails on input/artifact drift. Stable paths/order/LF; no volatile build timestamp. Concurrent source/evidence changes can legitimately require regeneration. Root selects and visually reviews the current candidates; contact-sheet presence and historical PASS do not close Q01.
