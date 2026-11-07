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
