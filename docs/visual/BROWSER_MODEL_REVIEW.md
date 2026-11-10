# Browser model export review

Reviewed on 2026-11-07. All 21 family contact sheets were opened, including all 84 front/side/rear/quarter browser images, and compared with their selected reference and accepted Blender source render. No new visible GLB export defect was found.

Evidence: `assets/v2/qa-browser/<asset>-browser-reference.png` and `browser-contact-index.json`. The initial sheets were inspected before the final behavior/camera fixes. After the latest full run, all 84 PNG hashes were refreshed against the unchanged final GLBs; the already reviewed sheets and their original input hashes are preserved separately as `sheet_capture_evidence`. No renderer, browser session, or GPU test was launched by this reviewer. Pillow only assembled existing screenshots and corrected the QA footer.

Current capture gate: `work/v2-browser-results-final.json`, SHA-256 `904a2e98f4fc402380ce2c868b4a697e457f1de683c2d90365181daa994e18f6`, independently reads 30 expected tests, zero skipped/unexpected/flaky tests, zero global errors, duration 31.805 seconds. [BROWSER_QA.json](BROWSER_QA.json) records exit code zero and build fingerprint `f64986bcaaf5a99b2eb57c7a2a69583b1f5297a564ab529ebdf204361f1ec9c1`. This run uses `index-CwwCEUPq` / `largeWarehouse-SItJUNRu`: edge-zone focus now views inward from the open interior, correcting dock/stock occlusion reported by the video reviewer. The prior build's camera framing is historical; its model comparison remains valid because all 21 GLB hashes are unchanged. All 84 current browser PNG files are newer than their GLBs. The catalog checks that captures did not change during hashing. No repeat visual review of identical model geometry was needed.

The browser views are actual application screenshots at 1366 × 768. Contact sheets crop application chrome and enlarge the model for inspection; original PNG files remain intact and their SHA-256 values, crop rectangles, final GLB hashes, references and accepted source images are recorded in the index. Crops retain aspect ratio and do not retouch model pixels. Static images prove the visible export at these views; dimensions, world anchors and master instance counts are covered separately by `visual-checks.json`.

## Family observations

Every row below includes all four browser angles. “Accepted” means no new missing part, inverted surface, material substitution, clipping or deformation relative to the accepted source was visible in these captures.

| Family | Visible comparison | Result |
| --- | --- | --- |
| standing-worker | Continuous yellow vest front/back, sloping shoulders, helmet, face, pockets, hands and boots survive export. Browser shading is flatter than Blender's studio shading, with the same teal/yellow/skin separation. | Accepted |
| picker-worker | Bent elbows and forward hands retain their shape without losing sleeves or vest panels; face and rear silhouette match the source. The cart is a separate family. | Accepted |
| driver | Seated thigh/knee/boot profile and both forearms remain intact. Empty seat/steering context in this component stand is expected because those parts belong to the forklift. | Accepted |
| worker-low | Reduced faceted head, limbs and joints match the accepted far model; complete vest and reflective bands remain visible front/back. Its close stand deliberately exposes the coarser LOD. | Accepted |
| picking-cart | Handle, open upper basket, lower deck, corner safety pads and four caster assemblies remain distinct; matte dark steel and teal side panels match the source. No baked worker or cargo is expected. | Accepted |
| rack-high | Three real birch decks, feet/guards, bracing and the closed top perimeter remain visible. Narrow front and deeper side proportions match the source; no solid panel fills the frame. | Accepted |
| rack-low | Three decks, four posts, side X braces and repaired closed top ring remain present. Missing small guards/bolt detail is the intended LOD reduction. | Accepted |
| environment-shell | Broad unscaled floor, perimeter columns, window band and modular wall panels retain their arrangement; open cutaway sides and absent roof preserve floor visibility. Pale seams/yellow floor marks remain subtle in the brighter browser lighting. | Accepted |
| dock | Open door aperture, raised shutter slats, roller apron, black bumpers, yellow guards and side control box survive all views; side depth is preserved. | Accepted |
| conveyor-high | Belt, separated yellow rails, motor/gearbox, lower ties and feet remain present. End views show an open transport direction. | Accepted |
| conveyor-low | Plain belt/rails and four reduced supports match the source; absent motor/bolts/foot pads are deliberate far-model simplifications. | Accepted |
| conveyor-corner | Square L transport surface and its two open arms survive export. Yellow outer/corner guards, transfer insert, motor and support frame match the accepted revised corner. | Accepted |
| conveyor-diverter | Three open transport arms remain clear; guard corners, belt surface, motor and frame match the source. No extra rail closes the branch opening. | Accepted |
| order-tote | Open interior, thick rim, tapered walls, side handle aperture, front label and reinforcing ribs remain readable; interior surfaces are present rather than a closed lid. | Accepted |
| tote-low | Open top, tapered wall thickness and base remain intact. Removed handle/ribs/label are the intended far representation. | Accepted |
| sealed-parcel | Closed top, folded seams, centre tape and blank label remain distinct; no unintended open interior appears. | Accepted |
| forklift | Fork blades, nested mast/chain detail, seat/steering, overhead guard, tyres and rear lamps remain present. Yellow body, dark steel and rubber retain separate materials. | Accepted |
| packing-station | Both passive L transfer counters, inclined transition panels, support legs, base shelf, printer, tape tool, scanner and monitor remain present. The stand intentionally hides the work carton; runtime PACK reveals the separate WIP layer. | Accepted |
| buffer-pallet | Deck-board gaps, blocks, dark edge protection and safety corner plates remain visible. Empty deck is intentional. | Accepted |
| pallet | Separate wooden boards, blocks, bottom runners and forklift openings match the source; no buffer edge guards are expected on this transport pallet. | Accepted |
| crate | Lid thickness, seams, tape folds and recessed blank side label remain clear. The former label coplanarity problem does not recur in the side/quarter screenshots. | Accepted |

The browser's warmer, brighter lighting reduces the studio highlights and makes some pale labels/seams less contrasted. This changes the lighting appearance, while the inspected volume and material assignments agree with the accepted exports. No new geometry edit is requested from this review.

## Source reread after the event-index fix

Direct reads of the current source confirm the former repeated full-history scan is removed from the warehouse motion path:

- `warehouseMotion.ts` builds `pickedByOrder`, `actionById` and `firstActionByActor` once per compiled run identity. Per-frame tote contents use a binary time lookup in the order's picked-event list, capped at four symbols; route and initial-home checks use map lookups.
- `compileVisualRun` in `replay/core.ts` sorts events by time/phase/sequence before returning `compiled.run`. `createReplayController.getRun()` returns that stable object until `setRun`, so the ordered per-order lists and cache invalidation are consistent with the caller in `largeWarehouse.ts`.
- The current follow-order source clears following ID, selected ID and selection visibility when no visible top-level cargo remains. Seek/reset resolve the visible order cargo and restore camera position/bounds; new-run loading clears old follow state. This is a source-level verification, with the dispatch/seek regression test owned by the parent and props agent.

The index includes hashes of the three source files at catalog generation. No performance timing result is inferred from this source reread, and this static export review does not replace the owners' motion/contact and interaction tests.
