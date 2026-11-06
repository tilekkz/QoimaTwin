# Final source review — visual integration

Initial read-only review, 2026-11-07, before runtime freeze; final disposition updated after the frozen build's 30/30 pass. Scope: conveyorLayout.ts, warehouseLabels.ts, warehouseMotion.ts, riggedModel.ts, largeWarehouse.ts and app/CalibrationV2.vue. No application code changed by this reviewer.

The parent supplied Tier 2 graph context; the new symbols were not yet tracked. Findings rely on direct reads and exact call paths, not on a graph absence claim. At the initial review, runtime tests and contact poses were still in progress. The final status below supersedes those timing statements while retaining the original findings. Backend ledger scope is not expanded.

## Final resolution and evidence

All five actionable source findings have verified corrections. The current [BROWSER_QA.json](BROWSER_QA.json) records **30/30 passed**, zero skipped/flaky/failed tests, against build hash `f64986bcaaf5a99b2eb57c7a2a69583b1f5297a564ab529ebdf204361f1ec9c1`. Its [raw report](../../work/v2-browser-results-final.json) SHA-256 is `904a2e98f4fc402380ce2c868b4a697e457f1de683c2d90365181daa994e18f6`, independently matched by this reviewer; duration is 31.805 seconds.

Current camera configuration is `index-CwwCEUPq` / `largeWarehouse-SItJUNRu`. The production focus direction for west/east edge zones now looks from the open interior, correcting the dock-beam/stock occlusion reported in the video review. This supersedes the earlier camera framing, while all model GLBs and the accepted 21-family comparison sheets are unchanged. The 30-test report and 84 capture hashes were refreshed for this build; this reviewer did not reopen unchanged sheets or claim a new video review. Current performance/video capture conditions belong to their owner reports.

The geometry/browser-export gate is separately closed in [BROWSER_MODEL_REVIEW.md](BROWSER_MODEL_REVIEW.md): all 21 families / 84 views were inspected and unchanged final GLB hashes matched the independent binary verifier. Runtime acceptance means the recorded cases below; it is not an assertion that every possible contact/lifecycle branch has a dedicated test. Current [PERFORMANCE.json](PERFORMANCE.json) measurements at 22:29:17 UTC use two 60-second Low windows after the camera fix: overview peaks 154 calls / 270,248 triangles, followed-hero peaks 191 calls / 418,632 triangles, p95 frame time 14ms for both. Earlier window figures are historical; High shadow-mode timing was not measured.

| Finding / follow-up | Final source disposition | Recorded runtime evidence / limit |
| --- | --- | --- |
| FR-01 — cargo bounds/follow | Closed: actual posed vertex bounds and attached visible cargo/cart/load unions feed selection; bounds update when cargo type changes. Order dispatch clears follow/selection. | Final order-follow test passes tote → parcel → pallet, seek camera continuity and clearing after dispatch. The paired driver/load test uses actual rendered roots. |
| FR-02 — PK hero selection | Closed: station transforms/model IDs are registered under PK IDs and resolve through the existing selection path. | Full suite passes; it has no separate PK hero-body click assertion, so that exact click is not represented as an isolated runtime test. |
| FR-03 — hidden cached rig inspection | Closed: inspectRig accepts visible rigs only, then inspectEntity falls back to current visible instances. | Final equipment test inspects actual visible hero driver/vehicle/load roots through travel/turn/seek. A separate hero-to-far diagnostic transition assertion is not claimed. |
| FR-04 — calibration namespace | Closed: loaded root metadata, expected eight anchors, three axes and model heights are validated before ready. | Final v2 calibration test passes actual axes, heights, belt top and three bin anchors. The incompatible calibration-GLB branch is source-guarded; the suite's wrong-Run-version test is a different input and is not counted as that GLB injection case. |
| FR-05 — casting light | Closed: the directional light explicitly casts shadows and High/Low controls retain their renderer gate. | Quality toggles pass in the final browser suite. Low performance is measured; no separate visual shadow-pixel assertion or High timing budget is inferred. |
| New-run follow state | Closed in source: loadRun/loadVisualDemo clear follow IDs, selection and follow initialization. | Wrong Run import preserves the active scene; returning to visual demo resets time in the final UI case. The exact second-run camera delta is not a separate test. |
| Per-frame full-history contents scan | Closed: per-run picked-event/action/first-action maps replace repeated history scans; compileVisualRun sorts events and getRun retains identity until setRun. | Absolute-clock/backward-seek cases pass. The Low performance report measures the whole frozen viewer rather than isolating this optimization. |
| Calibration diagnostic lifetime | Reload staleness addressed: the global diagnostic is cleared at mount before loading. After unmount it remains the last snapshot until another mount; no full unmount-clear claim is made. | Valid calibration lifecycle passes; no hot-unmount diagnostic assertion is recorded. This is a diagnostic-snapshot scope limit, not an open geometry/export gate. |
| Moving-limb raycast bounds | Closed in source: each pose updates actual surface bounding boxes/spheres in the vertex loop. | Full interaction suite passes; it does not contain a dedicated moving-finger/limb ray-hit assertion. |

No production change or new test was made for this documentation update. The original descriptions and suggested corrections below are historical records, not new pending requests.

## Source-fix verification record

- FR-02 closed at source level: station PK transforms/model IDs are now registered in positions, so the existing rig click path can resolve them.
- FR-03 closed at source level: inspectRig now returns only a visible rig; inspectEntity can fall back to the current instance.
- FR-01 closed at source level: CPU posing updates actual vertex bounds and per-surface bounding boxes/spheres; boundsFor unions attached visible cargo, carts and inbound load symbols; selection bounds update outside the reduced-motion camera guard. Driver focus uses the whole vehicle and its attached load.
- The moving-limb raycast bounds watch below is closed by the same per-pose bounding-box/sphere update. No runtime pass or timing result is inferred from these source fixes.
- FR-04 closed at source level: calibration now reads the actual calibration-v2 root metadata, checks its layout version, requires all eight measurement anchors/three axis endpoints and verifies the 1.7m/5.4m heights before reporting ready.
- FR-05 closed at source level: the intended directional light now sets castShadow=true. Low mode remains gated by renderer.shadowMap.enabled.

All five actionable findings below have source corrections verified by direct reread. Their final runtime evidence and its exact limits are recorded in the resolution table above; the earlier pre-freeze wording is not the current gate status.

## Original finding record (source fixes verified)

### FR-01 — cargo/order highlight is recentered as if it were a standing person (P2)

Source: largeWarehouse.ts, selectActor around line 213, followOrder around line 214, animate around lines 285–290.

selectActor creates cargo-specific bounds, but every following frame reuses the old size and centers the selection at followed.position + (0,0.9,0.2). For a tote, the initial Y range is position.y-0.02 through position.y+0.65; the animation loop changes its centre from position.y+0.315 to position.y+0.9, shifting the box upward by 0.585m. The highlight no longer encloses the tote. followOrder also swaps the followed ID at tote/parcel/pallet handoffs without rebuilding the bounds for the new cargo type, so the previous shape's size persists.

Reproduction after freeze: follow a visible tote/order, advance one frame, then advance through parcel and pallet handoffs. Check the highlight against actual cargo bounds.

Suggested correction: use one per-entity bounds helper both when selecting and when following. Handle bottom-centred tote/parcel/pallet and centred stock-crate origins explicitly; recompute the bounds when followingOrder switches cargo ID.

### FR-02 — animated near packing stations cannot be clicked through the hero path (P2)

Source: warehouseMotion.ts, station loop around lines 57–66; largeWarehouse.ts, onUp around line 236 and selectActor around line 213.

During near PACK, the station rig has entityId=PK01 and kind=pack. The non-instanced raycast path always calls selectActor(entityId). That function only proceeds if actorTransforms contains the ID. The station loop never adds PK01…PK06 to positions, so those station IDs are absent from actorTransforms. Clicking the animated station therefore does nothing, while clicking its static instanced representation falls through to ordinary selection.

Reproduction after freeze: place an active packer in hero distance, click the table body, then compare with the same table outside hero distance.

Suggested correction: route rig selection using its kind, or register station transforms and use a generic entity-selection helper. Preserve the pack ID rather than treating it as a worker ID.

### FR-03 — inspection can return a hidden cached rig instead of the visible instance (P2)

Source: warehouseMotion.ts, inspectRig around line 145; largeWarehouse.ts, inspectEntity around line 244.

Every update hides all cached rigs and only reactivates current heroes. inspectRig nevertheless returns rigs.get(id).inspect() without testing visibility. inspectEntity accepts that result before examining the visible instance batches. After a hero becomes far/instanced, diagnostics can report its old rig position and old joint pose although the canvas renders the updated instance elsewhere. This matters for contact and actual-position QA.

Reproduction after freeze: inspect a moving hero, move the camera out of hero range, advance time and inspect the same ID. Compare the returned root with the visible instance's matrix.

Suggested correction: return a rig inspection only when the rig group is currently visible; otherwise inspect the current visible instance. Expose the representation/visibility explicitly.

### FR-04 — calibration namespace is reported as a constant rather than read from the GLB (P2)

Source: app/CalibrationV2.vue, diagnostics assignment around line 28.

The diagnostic always reports layoutVersion=qoima-72x48-v2 and phase=ready after any successfully decoded GLB. It never reads the loaded calibration root's layout_version or checks required measurement nodes before reporting ready. A wrong-version or unrelated local GLB can therefore be labelled v2 by the diagnostic itself. The current artifact has passed independent binary checks, but this runtime field is not evidence of its actual namespace.

Suggested correction: read and validate the loaded root extras, require the known calibration anchor set, and distinguish successful GLB loading from successful metric calibration. Keep the actual measured positions/sizes in the diagnostic.

### FR-05 — configured high-quality shadow camera has no casting light (P2)

Source: largeWarehouse.ts, directional-light setup and setQuality. The scene enables renderer.shadowMap and mesh casting for high quality, but the reviewed version never sets light.castShadow=true. The installed Three.js Object3D constructor explicitly defaults castShadow to false; DirectionalLight does not override it. Consequently the configured shadow camera cannot produce dynamic shadows. The separate painted contact-shadow planes still render.

Suggested correction: explicitly enable casting on the intended directional light and keep low mode gated by renderer.shadowMap.enabled. Measure high mode again after enabling the real shadow pass.

## Original nonblocking follow-up observations

These observations describe the initial review state. Their current dispositions are in the final resolution table above.

- New-run loading: loadRun/loadVisualDemo replace replay state without resetting followInitialized/previousFollow, unlike seek/reset. Verify that loading a second run while following does not apply an old-run camera delta or retain an unrelated followingOrder.
- Per-frame contents cost: warehouseMotion scans run.events for each visible order tote every update. This is confirmed O(visible totes × full event count) work; no timing claim is made. Measure the intended long-run fixture after freeze and cache/order-index the picked-item lookup if needed.
- Calibration diagnostic lifetime: window.__QOIMA_CALIBRATION_V2__ is not cleared on unmount or at a new load. A hot-remount/error can leave the last diagnostic globally visible. Clear it or mark it non-ready during lifecycle transitions.
- Moving-limb raycast bounds were updated by the root after this finding; retain a runtime picking check after freeze.

## Checked paths without a new finding

- The canonical conveyor visual plan retains 179 IDs and opens nineteen junctions using trimmed half modules. Its current input was independently checked earlier as 127 full + 52 half cells, five corners and fourteen T branches. This review did not find a new counting/arm-selection error in the current fixed layout.
- Floor label atlas has eighteen labels and one shared texture/material/geometry, all owned by its dispose function. Its atlas rows and geometry indices are internally consistent.
- getParts excludes runtime_default_visible=false cargo fixtures. The WIP clone intentionally re-enables the single packing-carton root; the actual station GLB currently has only that one hidden fixture root.
- Hero CPU buffers and optional tint materials have explicit disposal; shared source materials are not disposed by each rig. Dynamic position/normal ranges are retained and freed by the owning rig.
- The prior late-loader cleanup guard and right-side rack/lot pi rotations are present in the reviewed source.

## Frozen-build gate disposition

- Order-follow, dispatch clearing, pause/seek/reset, actual driver/vehicle/load anchors, fork/pallet fit, cart-turn continuity, supported cargo origins/transfers, reduced motion, audio lifecycle and valid calibration are covered by the final 30/30 report.
- PK hero selection, visible-only rig inspection, moving-surface bounds and incompatible calibration metadata have verified source corrections. The resolution table explicitly distinguishes these fixes from cases without a dedicated runtime assertion.
- [MOTION_AND_INTEGRATION.md](MOTION_AND_INTEGRATION.md) records the synthetic replay and presentation boundaries. Low overview and followed-hero measurements exist in [PERFORMANCE.json](PERFORMANCE.json); those conditions do not establish a universal frame/triangle cap or a High shadow-mode timing result.
- Geometry and material-export acceptance is complete in [BROWSER_MODEL_REVIEW.md](BROWSER_MODEL_REVIEW.md), with final hashes and retained reviewed-sheet provenance in [browser-contact-index.json](../../assets/v2/qa-browser/browser-contact-index.json).


## Media and packaged launch closure

The final camera build was recorded again after visual inspection found dock-wall/stock occlusion. Five decoded MP4 control frames at8/24/44/66/84s were opened; the two peripheral forklift views now remain readable. The five separate action clips use visible1× replay speed. Main MP4 is89.966667s,1366×768,30fps,H.264/yuv420p; all recordings are muted. Exact probe data and hashes: [MEDIA_QA.json](MEDIA_QA.json).

The actual packaged START_VIEWER.ps1 was launched from the delivery directory. All58 viewer files match the tested production build byte-for-byte; full counts, driver stand and shipping follow were checked with zero page errors or external requests. [PACKAGE_LAUNCH_QA.json](PACKAGE_LAUNCH_QA.json) records the command, file hashes and captures. These checks do not extend the bounded backend/High-quality acceptance claims above.
