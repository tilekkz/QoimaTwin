# M02 — STANDARD rack, executor VERIFY

The isolated `rack-standard` source and GLB follow the actually opened R13.2 four-view reference and accepted C04/L09 metre dimensions. Root browser inspection and Khronos validation remain pending; this document does not grant operational admission.

## Construction and exact interfaces

Outer XYZ is **2.80 × 3.85 × 1.40 m**, floor-centre origin, front +Z. Six charcoal stepped posts, contained petrol collars, two bays, three tan storage decks, an open top tie and six rear diagonal braces form one connected construction. Shafts are .05 m and collars/boots .07 m, inside the accepted .07 post envelopes. They therefore look slimmer than the raster; reference pixels do not override those dimensions. Bevels remove material only. No cargo, stock or extra addresses are exported.

The ground deck is an explicitly approved engineering adaptation: nominal Y .10–.20 comprises a .02 bottom web and ribs with four .12-wide open-top channels centred X −1.10/−.30/.30/1.10. The front/rear beam tops are .12. A .08 × .07 fork at Y .13–.20 has .02 side air and .01 bottom air, without a closing front rail. The unchanged rigid FRAGILE HU rests on the ribs at Y .20 and bridges the channels. No extra pallet, raised HU base or substituted engagement pose is assumed. Upper decks remain closed. C04's 188 blocked reserve addresses and all handling restrictions are unchanged.

| Anchor | Runtime XYZ m |
|---|---|
| `anchor_bin_L1_B1` / `B2` | (−.70 / +.70, .20, .10) |
| `anchor_bin_L2_B1` / `B2` | (−.70 / +.70, 1.40, .10) |
| `anchor_bin_L3_B1` / `B2` | (−.70 / +.70, 2.60, .10) |

Each usable envelope is 1.25 × 1.05 × 1.10: left/right X [−1.325,−.075] / [.075,1.325], Z [−.45,.65], Y [support,support+1.05]. HU bottom remains the support plane, with zero bottom gap; C04 allocates the vertical clearance budget above it. Payload metadata is an inherited synthetic constraint, not structural certification.

## Actual saved/exported checks

- Final measured XYZ: **2.800000429 × 3.850000381 × 1.400000095 m**; minimum Y 0. Root Blender matrix is identity.
- **108** positive-volume, closed, manifold convex solids with outward faces; **218** evaluated BVH contact links connect every part to a floor boot. Six usable boxes have no intersecting evaluated triangles or enclosing solids.
- All four blade prisms clear the evaluated geometry; **36** full-depth insertion rays are unblocked. Thirty upward support hits span both edge ribs and the centre ribs beneath the two ground FRAGILE footprints; their actual contact hull contains the declared symmetric CoG projection. This is a contact witness, not a load/stability calculation.
- A separate read-only audit reopened both saved `.blend` iterations: the evaluated triangle-position signature is identical (`e31e437c…77f3d01e`), with all 108 editable meshes/bevels retained. **54** additional upward rays hit all six support planes at their exact heights. Upper retrieval remains unapproved.
- Three saved-source Principled material factors match actual GLB PBR factors within 1e−6: charcoal `#293D46`, petrol `#2E7376`, warm tan `#C99A60`, roughness .85, metallic 0. Seventeen part assignments changed in iteration02 to make the upper beam/deck faces tan; geometry and anchors did not change.
- Final GLB: **4,752 triangles, 3 material batches, 287,448 bytes**, SHA-256 `99193696ca202581c8a800385cc00494e572ebdde852ce7c506b7d9de85f651a`.

## Actual visual review and saved iterations

Opened R02 and approved R13.2 raster, then iteration01 sheet and final iteration02 **front, side, rear and quarter PNGs individually**. Front/rear preserve all six mirrored rear diagonals and the two-bay silhouette. Side shows connected depth ties and whole feet. Quarter shows closed upper panels, joined collars/rails, open ground channels and no loose trim. The first iteration's upper petrol beam faces differed from R13.2; final tan faces resolve that mismatch. No new missing part, visible backface or floating support was observed in these four final source views. Runtime lighting/material appearance still needs independent root review.

Artifacts: `assets/v3/previews/rack-standard/{front,side,rear,three-quarter,four-views}.png`; frozen source/GLB/stats/builder/views and mesh/source-export/render reports in `assets/v3/iterations/rack-standard/M02-01/` and `M02-02/`. Editable canonical source is `assets/v3/blender/rack-standard.blend`; runtime export is `frontend/public/models/v3/rack-standard.glb`. Exact inputs/outputs and hashes are in `docs/adaptive-v3/evidence/M02.json` and `assets/v3/specs/rack-standard.dimensions.json`.

Reproduce with background Blender `--threads 2 --python tools/blender/v3/build_rack_standard.py`; read-only source/material audit adds `-- --audit-source`. The queued neutral renderer is `tools/blender/v3/render_asset.py -- rack-standard --size 1000`. No live Blender or browser session was used by this executor.

Graph Tier2: project `qoima-twin`, generation 2026-11-07T13:18:32Z. One bounded coverage call recorded missing new builder and changed/untracked material inputs with no recorded parse gap; current exact sources and actual raster/files were used instead. No index refresh or exhaustive graph claim.

## Metadata maintenance — accepted C08 v0.2 binding

Root subsequently accepted M02-02 after actual source4/browser4 inspection and Khronos 0 errors/0 warnings; that review remains unchanged in `evidence/M02.json`. The earlier executor-stage pending statements above are historical. This maintenance revision changes the **current source binding only**, from historical C08 `691b597e…9873fe1` to accepted v0.2.0 **`22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4`**.

Current GLB SHA-256: **`5917721fd91de2dd755ec9929284ded8ceee5285366111f48145c8aa097ca866`**; saved source: `7fbf27a39e0e03c4628114cda7eedc7ec806d7cee05557dc8895993c721b0456`; dimension spec: `96e724d0f3bf33dbe68908d04146d02ee9eec610d98b7e0edaee61bb6afdf216`. Source/GLB still measure 2.800000429 × 3.850000381 × 1.400000095 m with 4,752 triangles and six identical anchors.

Actual saved-source evaluated triangles, all 108 material assignments, PBR factors, anchors and root matrix equal the reviewed baseline. **GLB BIN is byte-identical**, 277,344 bytes, SHA-256 `05de8e6f6122b9c4aeabc4eb0c36f7bcae0b78254e1b5e1e8ae79ba9c15c17ce`. Parsed glTF JSON differs only at root `extras.source_bindings_json`. No geometry/palette/anchor was edited, and no new render was performed. Prior four source/browser views therefore retain their exact geometry/material subject; no fresh screenshot is claimed.

Ground support .20, blade .08×.07, 1.10 blade length and local open lanes remain unchanged. C08 now declares .70 direct/.75 LONG travel fork tops and a stopped-only +.40 reach sequence; those vehicle actions need their own M14.8 physical proof and are not new M02 admission. Frozen M02-02 is untouched. New source/GLB/spec/stats/builder and `binding-refresh.json` provenance, plus the prior evidence/root-review bytes, are preserved in `assets/v3/iterations/rack-standard/M02-03-C08-v02/`. Reproduce the one-time metadata export with `-- --refresh-c08-binding` against the preserved reviewed baseline; it explicitly rejects a baseline mismatch.
