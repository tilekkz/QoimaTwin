# large-environment v2 reference

Generated 2026-11-07 with built-in image_gen. Primary direction: five user warehouse images inspected earlier in this session. Canonical geometry comes from current 03_3D_Scene_and_Replay.md, 07_Scale_Migration_and_Asset_Audit.md and contracts/layout.example.json (qoima-72x48-v2). The image is visual reference, not measurement authority or runtime texture.

## Geometry comparison

Reviewed all front/side/rear/three-quarter Blender previews for environment-shell and dock on 2026-11-07. Shell: 10,228 triangles, seven material batches; exact floor X0..72/Z0..48, slab top Y0, peripheral columns/window bands reach Y8. Unlike the concept image's more continuous sidewalls, the modeled side parapets are low and upper side glazing is sparse to keep the operating floor visible. Rear corrugation and clerestory mullions have real depth. The shell excludes racks, people, cargo and conveyors. Dock: 2,076 triangles, five batches; the door is retracted above a clear loading opening, with a dimensional frame, roller bed, rubber bumpers and safety guards. All four views showed coherent thickness and joins.

## Full generation prompt

```text
Use case: stylized-concept
Asset type: four-view modeling reference for a large modular warehouse architecture shell, version 2.
Primary request: A beautifully crafted miniature low-poly industrial warehouse CUTAWAY, floor exactly 72 metres wide X by 48 metres deep Z, wall/column height 8 metres Y. This is a NEW large warehouse, not a scaled small warehouse. Four coherent views of the SAME architecture: clean overhead plan, elevated front three-quarter overview, interior corner detail and straight rear elevation. Entire floor visible in overview and plan. Neutral grey presentation background, clean sheet.
Architecture: no roof. Broad concrete slab with straight subtle slab seams. Peripheral charcoal steel columns, shallow steel wall girts, cool slate grey corrugated wall modules, long high clerestory window bands with dimensional mullions and pale desaturated blue glazing. Rear wall full height, west and east walls are cutaway low parapets with intermittent upper window/column modules so the interior can be seen from above. Front facade absent, neat low perimeter curb only. Use plausible dimensional I-profile columns, precise joints, small bevels, restrained industrial vents. No internal columns through storage or work routes.
Layout: front working zone Z=0..12m is entirely clear for a future conveyor/packing line. Western receiving zone X=0..6m and Z=14..42m has quiet yellow boundary lines and two recessed loading openings in the west perimeter. Eastern shipping zone X=64..72m and Z=0..12m has two loading dock openings in the east perimeter. Large central storage area remains EMPTY; racks will be separate modular assets, do not include racks, cartons, conveyors, pallets, vehicles, people or cargo in the shell sheet. Floor has restrained saffron safety boundaries and a few directional chevrons only near dock service zones; no labels or invented text.
Style/medium: premium precise game-ready low-poly miniature, attractive matte cool charcoal and blue-grey architectural steel, warm neutral concrete, restrained saffron safety paint, soft small manufacturing bevels. Match dimensional game warehouse references, no glossy toy plastic. Keep construction legible and sparse enough for a <25k triangle reusable shell. Subtle ambient occlusion, broad neutral studio lighting.
Constraints: all four views same architecture/proportions, full 72x48 footprint, 8m tall peripheral columns, no roof, no overhead trusses crossing and hiding floor, do not fill working zones with props.
Avoid: photorealistic grunge, scratches, tiny noisy textures, busy signage, logos, watermark, dramatic perspective, dense mesh ornamental details.
```
