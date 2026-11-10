# tall-rack v2 reference

Generated 2026-11-07 with built-in image_gen. Primary direction: five user warehouse images inspected earlier in this session. Canonical geometry comes from current 03_3D_Scene_and_Replay.md, 07_Scale_Migration_and_Asset_Audit.md and contracts/layout.example.json (qoima-72x48-v2). The image is visual reference, not measurement authority or runtime texture.

## Geometry comparison and LOD refinement

Reviewed all four Blender views of rack-high and rack-low on 2026-11-07. Both have exact 0.9 x 5.4 x 1.5m envelopes and three real deck tops at 0.225/2.025/3.825m. Near model: 2,924 triangles and seven material batches, four dimensional posts/feet, guards, deck supports, labels, geometric recesses and rear/end bracing. Far model: 300 triangles and two batches; it preserves four posts/feet, three decks/supports, rear X bracing and two aisle-side guards. The first far-model three-quarter view showed an incomplete top outline; two rear guard boxes were traded for two longitudinal top ties to restore a closed top ring without changing its triangle budget. Targeted revised preview review is pending export by the parent task.

## Full generation prompt

```text
Use case: stylized-concept
Asset type: precise four-view modeling reference for a single TALL modular warehouse rack version 2.
Primary request: The SAME rack in orthographic front, orthographic right side, orthographic rear and gentle three-quarter views on a neutral grey studio background. Clean two-by-two sheet. Exact overall dimensions X width0.9m, Y height5.4m, Z depth1.5m. It is very tall and narrow, not a wide rack row. All views show the full same object.
Construction: Four charcoal steel corner posts on small realistic footplates with restrained saffron lower guards. Three and ONLY THREE actual shelf decks with visible birch panel thickness on blue-teal steel support beams, top surfaces at heights0.225m,2.025m,3.825m. The tall upper post extension ends at5.4m with a perimeter top tie frame, NO fourth deck. Two upper levels are real reserve addresses; lowest is the active pickface. Each shelf is empty and has one tiny blank recessed holder. Dimensional rear X bracing, short-end diagonal braces and a small number of readable bolt heads. Open long aisle-facing side allows access. Mounting perforations are regular restrained details, not noisy raster texture. Subtle beam connector plates, soft small bevels. Shelf supports should look structurally coherent despite tall proportions.
Style: beautifully crafted matte miniature industrial low-poly game model, same visual language as charcoal steel and tan carton warehouse references, matte cool charcoal/blue-teal steel, warm light birch decks, muted yellow safety guards. Premium precise sculptural depth. No glossy plastic. Useful medium detail suitable for a 3000-triangle near model, simplified far counterpart will retain all four posts and three decks.
Lighting: broad neutral studio lighting and soft grounding shadows. No dramatic perspective; orthographic panels are actual orthographic.
Constraints: exact dimensions .9m×5.4m×1.5m and three shelf tops .225/2.025/3.825m; consistent SAME object across all views, four posts, top tie is open, not a shelf. Empty shelves, no cargo, no people, no other bays. No text except optional simple view/dimension labels, no logos/watermark/barcodes.
Avoid: a scaled old2.6m rack, extra shelf, floating panels, thin wireframe-only placeholder, grunge, rust, dents, detailed noisy grain or bright orange palette.
```
