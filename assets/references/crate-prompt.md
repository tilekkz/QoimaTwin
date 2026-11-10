# crate reference

Generated 2026-11-06 using built-in image_gen. Four-view modeling reference, not a runtime texture.

## Source and assessment

Primary visual direction: user-provided five warehouse reference images in `C:/Users/izbas/Documents/Codex/2026-11-06/https-farabi-university-news-108095-lang/outputs/Qoyma_Twin/рефы`. These were inspected. Charcoal dimensional steel frames, tan cartons, yellow accents, matte low-poly warehouse style.

The carton was generated after inspecting all five user references. Preserve blank labels, dimensional lid and tape, and clean matte material rather than the slight paper noise in the sheet.

## Model comparison and refinement

Compared all four Blender previews (front, side, rear, three-quarter) with this sheet on 2026-11-06. The model preserves clean kraft faces, a two-part closed lid, folded lower rim, dimensional recess seams, one wrapping paper tape strip with folded ends, and a blank label on the aisle-facing +X face. Runtime bounds measured 0.550000 x 0.450000 x 0.650000m, with 604 triangles and seven material batches. The initial comparison exposed a coplanar frame/label surface; the script was refined to separate those surfaces by 0.0002m while preserving the exact bounding envelope. A targeted rerender checks this fix.

## Full prompt

```text
Use case: stylized-concept
Asset type: detailed multi-view modeling reference sheet for one standardized warehouse carton.
Primary request: Show the SAME beautifully crafted low-poly miniature kraft shipping carton in four consistent views: orthographic front, orthographic right side, orthographic back, gentle three-quarter view with the top clearly visible. Clean two-by-two layout, full uncropped object in every panel on neutral grey studio background with subtle grounding shadows. Exact proportions: width X 0.55 metres, height Y 0.45 metres, depth Z 0.65 metres.
Subject/construction: A closed dimensional corrugated cardboard box. Precise slightly softened edges, narrow inset panel borders and thin real seam lines. Two top flaps meet down the centre and are secured with one warm beige paper tape strip that wraps over the front and back edge, with small convincing folded ends. Subtle thickness visible at lid seams, no open flaps. A tiny blank off-white rectangular shipping label sits in a shallow border/recess on the front face. Keep the side faces mostly clean with a restrained vertical fold seam near one back corner. A slightly dark lower carton rim gives grounded construction without turning into a pallet or crate. No loose props, no arrows or barcodes.
Style/medium: premium precise game-ready low-poly miniature product model, sculptural and friendly industrial warehouse style. Matte kraft tan carton, warm beige tape, ivory blank label; shaded face colour variations are clean flat material colours, not photorealistic textures. The visual direction is the user's warehouse references: dimensional tan cartons on charcoal shelves and restrained yellow industrial accents.
Lighting/mood: broad soft studio lighting, matte surface, useful visible form without harsh dramatic shading. High legibility of tape folds, panel seams and label thickness. A few very small bevels create highlights.
Constraints: identical physical object across all four views, exact 0.55 x 0.45 x 0.65 proportions; no logos, letters, numbers, watermark, barcode or busy graphic pattern. No wood, no metal handles or bright colours, no noisy paper fibre, scratches, grunge, dents, distressed damage or shiny tape. Not a featureless flat cuboid; geometry must make its construction readable.
```

