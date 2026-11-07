# V2 visual revision: equipment and personnel in the browser

2026-11-07. Bounded first-hand review: **9 families / 36 views**. The equipment
agent opened each final front, side, rear and quarter panel beside its selected
reference and accepted source render, then repeated this review after the precise
stand-bounds fix. This report covers only the nine rows below.
This is V2 evidence and does not certify the separate V3 brief.

Final capture run: **33/33 passed**, 18 core + 15 browser, 34.525405 seconds.
Raw report: `work/visual-polish/browser-results.json`, SHA-256
`e90444d16cc400a369ec0558801c1cf3c7c777dfe53a70baded7ae22b79d0feb`.
Production scripts: `index-DOPf_3RA.js` / `largeWarehouse-DhonVUbu.js`.
Build fingerprint: `76de7846b3408f74ac956a58b0e65c7a6bfdf89a845306ef0f0b54c52c64c951`.
All 84 model captures use High quality; original PNGs are retained unmodified.

| Family / four-view sheet | Actual browser observation and comparison |
|---|---|
| [Forklift](../../assets/v2/qa-browser/forklift-browser-reference.png) | Rounded yellow counterweight, connected wheel arches, formed cab sides, seat, steering console, mast and paired forks retain the revised source silhouette. Front/rear remain symmetric and the side shows supported steps. Charcoal steel and yellow remain distinct. Tyre tread is visibly smoother than the reference's chunky tread; this is an art difference, not a claim of exact reproduction. No missing part or floating join observed. |
| [Crate](../../assets/v2/qa-browser/crate-browser-reference.png) | Thin flap edge and folded tape read as cardboard packaging. The former raised lid and perimeter frame are absent. Paper label, barcode rules and small handling arrows survive export. The browser is lighter than the Workbench source, while the same form and panel edges remain. Front/rear lower edges are complete after the QA crop correction below. |
| [Packing station](../../assets/v2/qa-browser/packing-station-browser-reference.png) | Laminated worktop, moulded printer, monitor, scanner, tape roll, shelf bundle, transfer benches, braces and feet remain connected in all four views. Light wood and dark equipment are readable without a color substitution. The open work carton is intentionally absent from this static stand; PACK supplies that presentation shell at runtime. The added benches are the agreed layout adaptation beyond the reference table. |
| [Pallet](../../assets/v2/qa-browser/pallet-browser-reference.png) | Slat thickness, three runners, nine blocks, rounded cuts, small fasteners and real open fork pockets remain visible. Front/rear are naturally thin because this is a 140 mm pallet. Its deeper shipping-pallet construction is the agreed adaptation of the lower buffer-platform reference. No floating block or closed fork pocket observed. |
| [Standing worker](../../assets/v2/qa-browser/standing-worker-browser-reference.png) | Helmet/brim, continuous vest with reflective bands, shoulders, sleeves, hands, cargo pockets and boots form a coherent figure. Side/rear joins remain closed. The face and cloth folds are simpler and more stylized than the generated reference, while the teal/yellow palette and adult silhouette remain readable. |
| [Picker worker](../../assets/v2/qa-browser/picker-worker-browser-reference.png) | Same clothing construction, with bent arms and hands in the pushing pose. Front/side show connected shoulders/elbows; rear vest and legs have no missing faces. It is the posed person only, so the absence of a cart in this stand is intentional. Helmet and body render cleanly in the final browser panels. |
| [Driver](../../assets/v2/qa-browser/driver-browser-reference.png) | Seated hips/thighs, bent knees, boots, sleeves and steering-hand pose remain coherent from all sides. The stand contains the body without a duplicated chair or wheel; those are separate forklift parts when bound in the scene. This differs from the illustrated seated reference composition and is not a missing exported seat. |
| [Worker LOD](../../assets/v2/qa-browser/worker-low-browser-reference.png) | Deliberately angular head, hands, limbs and boots retain the same helmet, clothing colors, vest bands and overall standing silhouette. It visibly loses near-model facial/finger/fabric detail, as expected for the distant representation. No cap hole or inverted body face observed. |
| [Picking cart](../../assets/v2/qa-browser/picking-cart-browser-reference.png) | Hollow upper basket, connected rails, handle supports, lower shelf, yellow corner guards and four dimensional casters remain readable in every direction. Export is empty equipment; person/tote/cargo are separate runtime entities. Side/quarter show caster attachment and shelf depth without a floating rail or decorative box. |

**Defect found and closed during this review**

The QA collage originally cut the final lower pixels of crate front/rear. The full
raw PNGs showed an intact model and camera frame; the defect was in `model_crop`,
which scanned only above Y=540 and capped its crop at 550. The generator now scans
through row 554, ignores the side hint bands, and caps the final crop at 557 before
hint text begins at 558. This keeps the model's last row near 555 and avoids a UI
glyph leaking into wide side crops. All 21 sheets were regenerated without
`--reviewed`; the corrected crate sheet was reopened. No raw image was retouched.

The parent separately corrected the inflated AABB used for stand/selection framing.
The final 33-case run includes the precise parcel-bounds regression. These nine
families were reopened after that change; there is no remaining clipping or new
framing defect in their final sheets.

**Evidence boundary**

No new geometry or material-export defect was observed in these 36 reviewed views.
Reference images establish art direction; the listed differences are not concealed
as identical reproduction. Still images do not prove every moving contact or
inventory transition. Those have separate automated evidence in
[BROWSER_QA.json](BROWSER_QA.json), which also records current hashes, all 84 PNG
paths and aggregate review ownership. The storage agent's eleven families and the
parent's buffer-pallet review are separate contributions, not first-hand claims by
this reviewer.

The earlier 30-case raw report remains `work/v2-browser-results-final.json`; its
previous QA snapshot is `work/visual-polish/browser-QA-before-revision.json`.
Neither is relabelled as this visual revision. No GPU render, browser session,
production build or test run was launched by this reviewer for this browser review.
