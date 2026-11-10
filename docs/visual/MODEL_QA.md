# Model QA — v2

Reviewed 2026-11-07 against the ART_ANIMATION_QA brief. The geometry gate is closed for all 21 reusable families, calibration and the master. The browser export gate is also closed: all 21 families / 84 views were inspected against their references and accepted source renders in [BROWSER_MODEL_REVIEW.md](BROWSER_MODEL_REVIEW.md), with final hashes in [browser-contact-index.json](../../assets/v2/qa-browser/browser-contact-index.json).

The runtime gate is separate. The frozen build passed 30/30 tests in [BROWSER_QA.json](BROWSER_QA.json), including paired driver/vehicle/load anchors, fork/pallet compatibility, cargo lifecycle, cart turns, pause/seek/reset and calibration. Two 60-second Low performance measurements are recorded in [PERFORMANCE.json](PERFORMANCE.json). Those reports define the tested conditions; static model acceptance alone does not prove every motion/contact phase or a universal performance cap. The historical observations below are retained with their final dispositions.

## Evidence and method

- Source/style board: [style-board.png](../../assets/v2/qa/style-board.png).
- Reference/render contact sheets: [assets/v2/qa](../../assets/v2/qa/).
- Exact source reference paths and SHA-256 hashes of the four reviewed PNGs: [contact-index.json](../../assets/v2/qa/contact-index.json).
- Final catalogue: [asset-manifest.json](../../assets/v2/asset-manifest.json), covering 23 GLBs / 21 reusable families, actual world bounds, origins, forward axes, anchors, pivots, materials, LOD, editable sources and model/builder/reference hashes. Main-view preload is 3,235,060 bytes (3.235 MB), excluding calibration and static master.
- All twenty-one available families were opened as reference + front/side/rear/three-quarter sheets, including the corrected 900px camera framing: 84 actual model images. Contact sheets use the actual render files without repainting or compositing replacement geometry.
- Neutral Workbench renders show shape and construction. Their dark steel/concrete response is not the final browser lighting/material decision.
- Independent binary checks: [visual-checks.json](../../assets/v2/visual-checks.json). The final pass covers 23 GLBs: 21 families, calibration and master, recording each actual GLB hash. Final browser catalog hashes match this report.
- Canonical validator: 2,266 checks passed in the copied work/v2-spec-validation tree. [canonical-spec-checks.json](../../assets/v2/canonical-spec-checks.json) records the copy execution and unchanged original verification_report.json hash. These are prepared contract/schema/arithmetic checks, not runtime simulation acceptance.
- The final all-family render sweep has 84 PNGs newer than their final GLBs. All 21 contact-index model hashes match the 23-file passing binary report and final manifest. The seven re-exported cart/logistics families were reopened after this sweep; no new visible defect was found.
- Current runtime evidence: [BROWSER_QA.json](BROWSER_QA.json) and its [raw 30-test report](../../work/v2-browser-results-final.json), SHA-256 `904a2e98f4fc402380ce2c868b4a697e457f1de683c2d90365181daa994e18f6`, duration 31.805 seconds, build fingerprint `f64986bcaaf5a99b2eb57c7a2a69583b1f5297a564ab529ebdf204361f1ec9c1`. All 30 passed, with zero skipped, unexpected or flaky tests. Current camera bundles are `index-CwwCEUPq` / `largeWarehouse-SItJUNRu`; edge-zone focus now looks inward from the open interior. The prior framing is historical, while accepted model geometry is unchanged. All 84 current browser capture hashes were refreshed without reopening the reviewed sheets, which retain their original input provenance.

## Four-view comparison

All four source renders and all four exported-GLB browser views were opened for every family and compared with the listed reference. No near-personnel art defect or browser export defect remains open. The table records model/export acceptance; paired motion and interaction coverage is stated separately below and in the runtime report.

| Family | Reference | Visible construction and comparison | Current gate |
|---|---|---|---|
| rack-high | v2/tall-rack-reference.png | Four dimensional posts/feet, three thick supported decks, rear/end bracing, open top tie ring, guard feet and blank level labels. Exact 5.4m tall proportions follow v2 rather than old 2.6m sheet. | Geometry + browser export passed |
| rack-low | same tall rack sheet | Same height and three deck masses; four feet/posts, structural rear X, closed top perimeter now visible in three-quarter. Two aisle-side guards retained. | Geometry + browser export passed; top-ring defect closed |
| environment-shell | v2/large-environment-reference.png | Full 72x48 slab, 8m peripheral columns/rear clerestory/corrugation, low side parapets and sparse upper side glazing. Cutaway is intentionally more open than concept, keeping operating floor visible. | Geometry + browser export passed |
| dock | same environment sheet | Door frame has depth, raised slats leave clear opening, connected roller bed, bumpers, guard feet and control box. Side/rear remain coherent. Dock close-up is derived from the approved architectural language; source sheet has less close detail than rack/person refs. | Geometry + browser export passed |
| standing-worker | v2/standing-worker.png | Final 01:57 four views show grounded 1.7m figure, softened head/chin, continuous sloped sleeve shoulders and a clean vest shell/V-neck. No former torso/vest intersection. | Geometry + browser export passed |
| picker-worker | same standing sheet; cart sheet for contact context | Same corrected anatomy/vest, elbows bent toward a separate cart. Contact is not proven by a standalone pose. | Geometry + browser export passed; runtime scope below |
| worker-low | same standing sheet | Height, full helmet/vest color masses and limbs survive the 884-triangle proxy. The missing-upper-vest regression is closed. Hands/cloth remain deliberately coarse. | Geometry + browser export passed; far LOD only |
| driver | v2/driver.png | Final softened face/shoulder/vest construction is coherent in all four seated views. Local negative Y is intentional beneath seat origin. Actual mounted feet match the 0.54m footwell. | Geometry + browser export passed; paired runtime cases passed |
| picking-cart | picker-cart-reference.png | Four connected caster assemblies, rigid frame, bottom tray, open top basket and dimensional handle. Empty cart is correct; reference cargo is not baked into a reusable asset. | Geometry + browser export passed; cart/tote/turn cases passed |
| conveyor-high | v2/conveyor.png | Thick belt bed, yellow guides, connected four-leg support, braces, feet and drive casing. Coarser bolt/roller detail than sheet is controlled; not a flat plane. | Geometry + browser export passed; final line cases passed |
| conveyor-low | same conveyor sheet | Belt, guide color masses and simple supports preserve full module footprint. Drive/feet detail removed at distance. | Geometry + browser export passed; far LOD only |
| conveyor-corner | same conveyor sheet; variant uses common construction language | Revised 804-triangle square-L has a coherent deck and two adjacent open arms matching the canonical orthogonal path. Final four views supersede the initial curved-deck comparison. | Geometry + browser export passed; revised open L accepted |
| conveyor-diverter | same conveyor sheet | Coherent open branch lip, belt bed and frame; no obstruction across branch opening. This is a fixed branch shape, not evidence of an animated pusher mechanism. | Geometry + browser export passed; fixed open branch |
| order-tote | v2/order-tote.png | Hollow interior has visible bottom/thickness/rim; side grip is an actual opening. Ribs, feet and blank label read in all views. Rectangular grip differs from rounded reference but construction is coherent. | Geometry + browser export passed |
| tote-low | same tote sheet | Open interior and broad color mass retained at 28 triangles. Thin walls and no handle/ribs are a distance-only compromise. | Geometry + browser export passed; far LOD only |
| sealed-parcel | v2/sealed-parcel.png | Closed dimensional carton, continuous tape over top/front/back, blank label and small seam/bevel highlights. No busy barcode or photoreal noise. | Geometry + browser export passed |
| forklift | forklift.png | Coherent counterweight, four tyre/wheel assemblies, connected cage, detailed mast/carriage and two parallel lowered blades. Side and rear retain volume. Driver is correctly not baked into the reusable vehicle. | Geometry + browser export passed; paired anchor and fork-fit cases passed |
| packing-station | packing-station-reference.png | Final 4,132-triangle model adds two supported passive L counters/ramp joins, keeping the worker's centre clear. The printer is rotated on the left and monitor is rear-centred. All four final views remain coherent. Eight transfer anchors and 54 actual-triangle cargo-footprint support samples pass. No new transport cells were added. | Geometry + browser export passed; transfer support checked |
| buffer-pallet | buffer-pallet.png | Low supported deck, planked top, guard corners and visible access gaps. The 0.075m support top follows the temporary buffer contract. | Geometry + browser export passed |
| pallet | buffer-pallet.png as construction/material language | Distinct transport pallet: top/bottom deck, nine support blocks and actual fork channels. Taller 0.14m support is intentional, not a scaled buffer. | Geometry + browser export passed; actual fork-surface fit checked |
| crate | crate-reference.png | Centered stock carton retains seams, lower folded rim, wrapping tape and complete blank label. Side and quarter show no former coplanar label breakup. | Geometry + browser export passed |


## Closed geometric defects

| ID | Observation | Change and evidence |
|---|---|---|
| RACK-01 | First low-rack three-quarter view showed two disconnected top U frames, losing the near-rack silhouette. | Replaced two rear guard boxes with two longitudinal top ties. Revised four views show a closed top ring at the same 300 triangles/two materials. |
| CRATE-V1-01 | Earlier centered carton label and border shared an exterior plane, creating a half-dark flickering label. | Separated exterior faces by 0.0002m; revised side/three-quarter show a complete clean label. The v2 crate reuses this corrected construction and passed final source and browser four-view review. |
| MASTER-01 | A receiving decor pallet at Z34 would overlap the west Z36 dock roller corner. | Moved only the tagged, empty STATIC_DECOR pallet to Z30. Canonical stock, actors and service coordinates were not changed. |
| PACK-TRANSFER-01 | Cargo transfers from branch to table and table to outfeed lacked physical support. | Added passive supported L counters with a 0.85–0.9m surface transition. Final four-view review passed; 54 clipped-triangle footprint samples over the two paths have at most 0.0107m height difference on the slope/rollers. The 179 logical transport cells are unchanged. |

## Art correction history and contact disposition

The 01:50 polish improved face/chin shading and reduced pointed joints but introduced a shirt/vest intersection. That intermediate version was rejected. The final 01:57 export was reopened with its reference and all four views for standing, picker, driver and far worker: continuous vest, clean front V-neck/rear top and unified shoulder slopes close the concrete defects. Cart construction remains accepted. Master/calibration were rebuilt after this visual acceptance.

| ID | Family | Concrete visible issue | Final disposition / evidence |
|---|---|---|---|
| PEOPLE-01 | standing/picker/driver near | Original shoulder wedges and projecting knee/elbow patches. | Closed: unified sloped shoulders and softened joint contours in final four-view comparison. |
| PEOPLE-02 | same near family | Original thick vest and hard skin/chin facets. | Closed: thinner coherent vest, softer head/skin normals; final front/side/rear/quarter opened. |
| PEOPLE-03 | intermediate near and far vest | Shirt intersected the upper vest, producing a jagged boundary and hiding the far chest. | Closed: final continuous outer vest has a clean V-neck and rear edge; no intersection in all four views. |
| CONTACT-01 | picker + cart | Standalone worker pose does not prove palms meet the real cart handle. | Model/export gate closed. Final runtime cases pass tote-on-basket support, parked cart heading and continuous cart turns at PICK/TRAVEL boundaries and waypoints; see [BROWSER_QA.json](BROWSER_QA.json). These cases do not imply finger-level contact at every pose. |
| CONTACT-02 | driver + forklift | Standalone hands are near knees. Seat/steering/footwell must align with articulated vehicle. | Closed for the sampled paired runtime cases: actual driver-seat and carried-pallet anchors within 0.002m, both hands within 0.07m of steering targets through travel/turns, reverse/seek and continuous lift cases passed. Two existing drivers/two vehicles remain in the registry. See [BROWSER_QA.json](BROWSER_QA.json) and [paired capture](../../frontend/test-results/v2-runtime/forklift-carry-contact.png). |

Earlier runtime follow-up reported by the root measured actual F02 driver/vehicle anchor agreement within approximately 1.8e-6m. The final paired browser tests now provide the sampled motion evidence described above, separately from this owner's binary rest-pose inspection. The final suite also verifies that the pallet remains grounded until fork contact and then lifts continuously; these are no longer pending model acceptance items.

## Independent master and calibration checks

Line integration revision: the original 179 full straight modules put rail geometry across corner/T cargo paths. The final Python master preserves 179 logical cell IDs while using 127 full + 52 half visual straights, plus 19 actual open junctions (five corners, fourteen T branches). All 358 canonical logical endpoint anchors stay at original coordinates; physical module ports are trimmed. The independent validator checks both sets and derives the junction's expected outward arms from segment endpoint distances. This final re-export passed all those checks.

The final large-warehouse master has 267,140 instance triangles and a 4,155,432-byte GLB, including all six revised packing stations. Its linked meshes are preserved. The independent verifier traversed the actual selected GLB scene and found exactly 288 visible rack roots, 864 logical slots/qualified bin anchors, 600 visible lot symbols, 24 visible actor bodies, two vehicles, six packing stations, 179 visible conveyor cells and 19 visible junction modules. It compared actual lot bindings, business actor roots, slot world anchors, trimmed visual ports and canonical logical endpoints with JSON. Declared counts were compared with this traversal rather than accepted as proof.

The 72x48 floor remains exact. Dock frames extend 0.23m outside the building at the wall openings; this explains the master's total X bounds of approximately -0.23..72.23m. The slab top is Y0 and its lower surface Y-0.2.

Calibration includes actual one-metre X/Y/Z ruler meshes, a 1.7m standing worker at X2, a 5.4m rack at X4 with three anchors, and a conveyor at X6 with belt top Y0.9. The final browser calibration case passed actual namespace, metre axes, heights, belt-top and all three bin-anchor checks: [BROWSER_QA.json](BROWSER_QA.json), [calibration capture](../../frontend/test-results/v2-runtime/calibration-v2.png).

Rest-pose paired numeric inspection used actual exported driver/forklift vertices. Seat binding is (0,0.99,-0.65); mounted foot minimum Y0.540000 matches footwell Y0.540000. Wrist pivots are approximately (+/-0.115,1.139,-0.298). Steering grip targets (+/-0.11,1.13,-0.27) lie inside the actual hand geometry bounds. This supports coherent metric placement but does not replace browser contact/action evidence.

The static master is a review/design assembly. Its thousands of mesh nodes are not a claim of an optimized runtime renderer. The application separately uses spatial instancing/LOD and a CPU-updated rigid hero rig; animation is not supplied by the old v1 master.

## Read-only frontend review findings

No frontend files were changed by this QA owner.

The later WIP/follow/visibility audit and its final resolution table are recorded in [FINAL_REVIEW.md](FINAL_REVIEW.md). All five actionable source findings have verified corrections. The final 30-test report records the runtime cases actually exercised; Low performance measurements are recorded separately, without claiming a measured High shadow-mode budget.

| ID | Source observation | Consequence / requested fix | Status |
|---|---|---|---|
| FRONT-01 | Initial largeWarehouse.ts built all racks with zero yaw. | Right-side racks and their crate labels need pi yaw so open/label faces point into the aisle. | Closed in source: both _R rack and lot transforms now receive pi, verified read-only |
| FRONT-02 | Initial warehouseMotion.ts forced cartYaw=0 during pick. | A reverse-arriving picker would jump the cart by 1.24m. | Closed for tested transitions: actor.cartYaw and the final continuous heading correction pass PICK/TRAVEL-boundary and waypoint cases in [BROWSER_QA.json](BROWSER_QA.json) |
| FRONT-03 | IDLE home spreading offsets disappear immediately on TRAVEL. | Up to roughly 0.77m visual jump at first departure. Blend the cosmetic offset to zero over initial motion. | Historical presentation-offset limitation, outside the geometry gate. Current offsets are documented in [MOTION_AND_INTEGRATION.md](MOTION_AND_INTEGRATION.md); the final suite proves canonical routes/cart-turn continuity, not a smooth cosmetic home-offset departure |
| FRONT-04 | Promise.all loader callbacks could settle after disposal on an earlier load failure. | Late geometry/material resources could be added after cleanup. | Closed in source: late result geometry/materials are disposed if viewer/host is closed |
| FRONT-05 | Every logical metre was drawn as a full straight with continuous side rails, including canonical corner/T endpoints. | Use nineteen open square-L/T decks and shorten adjacent straight meshes by 0.5m while retaining all 179 logical cells and canonical endpoints. | Closed: master geometry/port checks, revised four-view browser exports, 179 rendered cell IDs and the scripted cargo hold/resume cases passed; see [visual-checks.json](../../assets/v2/visual-checks.json) and [BROWSER_QA.json](BROWSER_QA.json) |

## Final gate disposition and limits

- Geometry: closed for 21 families plus calibration/master, with actual binary geometry and source four-view evidence.
- Browser exports: closed for all 21 families / 84 actual views; [BROWSER_MODEL_REVIEW.md](BROWSER_MODEL_REVIEW.md) records the visual comparison and [browser-contact-index.json](../../assets/v2/qa-browser/browser-contact-index.json) records final GLB/PNG hashes.
- Runtime: the recorded 30/30 suite passed actual registry/counts, supported cargo origins/transfers, paired driver/vehicle/load anchors, continuous cart/lift behavior, pause/seek/reset, order following, reduced motion, audio lifecycle and calibration. Scope remains the cases in [BROWSER_QA.json](BROWSER_QA.json), not exhaustive contact at every motion phase or backend simulation acceptance.
- Performance: the current [PERFORMANCE.json](PERFORMANCE.json), captured 2026-11-06 at 22:29:17 UTC after the camera fix, records two 60-second Low windows. Overview peaks are 154 calls / 270,248 triangles; followed-hero peaks are 191 calls / 418,632 triangles, with p95 frame time 14ms in both windows. Earlier camera/window values are historical. These measured conditions do not imply a universal 180-call/350k cap or a High shadow-mode timing result.
