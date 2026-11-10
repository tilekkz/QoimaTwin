# rack-bay reference

Generated 2026-11-06 using built-in image_gen. Four-view modeling reference, not a runtime texture.

## Source and assessment

Primary visual direction: user-provided five warehouse reference images in `C:/Users/izbas/Documents/Codex/2026-11-06/https-farabi-university-news-108095-lang/outputs/Qoyma_Twin/рефы`. These were inspected. Charcoal dimensional steel frames, tan cartons, yellow accents, matte low-poly warehouse style.

The rack generation was already running when the folder path arrived; it is retained because its generated charcoal and teal frame, dimensional decks and safety feet match the subsequently inspected references. It is concept guidance; build exact contract dimensions, keep the open front, and place rear braces physically at the rear.

## Model comparison

Compared all four Blender previews (front, side, rear, three-quarter) with this sheet on 2026-11-06. The model preserves four dimensional steel posts, footplates and muted saffron guards, exactly three warm birch decks, beam brackets, top perimeter ties and structural cross bracing. Its access face is intentionally +X toward the canonical aisle, with the X bracing behind it on -X, rather than using image-panel labels as world axes. The sole active shelf top is exactly 0.675m. Runtime bounds measured 0.900000 x 2.600000 x 1.500000m, with 3,572 triangles and eight material batches. The physical construction and silhouette are coherent in all four views.

## Full prompt

```text
Use case: stylized-concept
Asset type: detailed multi-view 3D modeling reference sheet for a single modular warehouse rack bay.
Primary request: Show the SAME beautifully crafted miniature industrial warehouse rack in four consistent views: orthographic front, orthographic right side, orthographic rear, and gentle three-quarter view. Neutral cool grey studio background. A clean two-by-two layout, generous separation, no perspective distortion in orthographic views. The object is a narrow but deep industrial rack, exact overall proportions width X=0.9 metres, height Y=2.6 metres, depth Z=1.5 metres. All four views must represent these exact same proportions and components.
Subject/construction: Four precise square-section steel corner posts ending in small floor footplates; three shelf levels with top surfaces at 0.675m, 1.52m, and 2.38m from floor. The lowest shelf is the only active pick address and is empty; upper shelves are empty decorative storage levels, not additional addresses. Shelf decks are warm light birch panels, visibly thick, held on blue-teal steel beams. Rear X cross bracing and restrained side cross bracing have physically visible thickness and coherent joins. Posts have small regular mounting apertures with a handful of readable bolt heads, exact but uncluttered. Small muted saffron safety protectors at feet and one small blank recessed label holder at the lowest shelf. A top cap rail ties the posts. Keep the open front free for access. All shelves empty; no boxes, people, other rack bays or environment.
Style/medium: premium toy-like low-poly miniature product model, precise dimensional construction, soft small bevels, believable matte powder-coated cool charcoal and blue-teal steel, subtle ambient occlusion, controlled clean geometry. Sculptural details should be legible and appropriate to a game-ready model, not noisy surface textures.
Lighting: broad soft studio lighting, subtle grounding shadows.
Text: optional tiny neutral view labels only, no logos or watermarks.
Constraints: same physical object in all views, four posts, exactly three shelf decks, lower shelf top at 0.675m, full object uncropped. Show useful form and depth without dramatic camera angles.
Avoid: pallet racks many bays wide, bright orange beams, photoreal grunge, rust, scratches, grain noise, floating pieces, flat box-only placeholder, unsafe construction, extra shelves.
```

