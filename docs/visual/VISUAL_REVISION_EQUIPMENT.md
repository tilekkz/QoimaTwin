# Equipment visual revision

2026-11-07. Geometry revision `equipment-polish-2` in
`tools/blender/v2/build_equipment.py`. Four assets were rebuilt and exported;
v1 sources, contracts, runtime code and previous QA reports were not changed.

**Observed changes**

| Asset | Geometry change and four-view observation |
|---|---|
| Forklift | Lofted counterweight with rounded plan/shoulders, sculpted side body and wheel arches, connected formed cab sides, padded seat/shell/hinges, steering console, and continuous rounded tyres with recessed hubs replace the box stacks and separate tyre blocks. The hydraulic rod reaches its top clevis. Front/side/rear/quarter show a coherent body and cab, supported steps, connected mast and paired forks. |
| Crate | New corrugated carton body, 4 mm closing flaps, meeting seam and a 0.6 mm folded tape strip replace the thick lid and raised perimeter frames. Flat paper label, small barcode/address rules and handling arrows add packaging identity. Four views read as a closed cardboard carton; no protruding lid or bottom border remains. |
| Packing station | One laminated worktop, sloping moulded printer housing, tapered monitor shell, real annular tape roll with spindle/supports, and thinner open-carton walls/flaps. The four views show connected benches/feet, supported equipment and clear service lanes. |
| Pallet | Rounded board/block cuts, end grain on cut faces and small fasteners within the envelope. Nine blocks, three lower runners and open fork pockets remain readable from the side and quarter views. |

**Measured exported geometry**

Values below come from the newly exported mesh vertices, in runtime metres, Y up.
Bounds are rounded to six decimals; floor-origin assets have minimum Y = 0.

| Asset | Runtime minimum XYZ | Runtime maximum XYZ | Size XYZ | Triangles / meshes / GLB bytes |
|---|---|---|---|---|
| Forklift | `[-.555,0,-1.319]` | `[.555,2.15,1.3]` | `[1.11,2.15,2.619]` | 17,936 / 27 / 883,864 |
| Crate | `[-.275,-.225,-.325]` | `[.275,.225,.325]` | `[.55,.45,.65]` | 574 / 6 / 37,940 |
| Packing station | `[-1.1,0,-1.5]` | `[1.1,1.42,1.5]` | `[2.2,1.42,3]` | 6,508 / 21 / 372,160 |
| Pallet | `[-.7,0,-.5]` | `[.7,.14,.5]` | `[1.4,.14,1]` | 3,156 / 5 / 170,988 |

**Preserved functional transforms**

The saved before/after manifests were compared directly: **51/51 named nodes
retained** (forklift 17, station 23, pallet 6, crate 5). Maximum change in asset-space
position, local position and local quaternion components is **0**. Full exact values
and parent names are in
[anchor-preservation.json](../../work/visual-polish/equipment/anchor-preservation.json).
The principal rest positions are listed below; `±` denotes separate left/right nodes.

| Asset / node group | Preserved asset-space XYZ |
|---|---|
| Forklift driver seat / footwell | `[0,.99,-.65]` / `[0,.54,-.20]` |
| Forklift hands | `[±.11,1.13,-.27]` |
| Steering pivot / carriage pivot | `[0,1.13,-.27]` / `[0,.24,.475]` |
| Front wheel spin pivots | `[±.45,.30,.06]`, radius `.30` |
| Rear wheel spin and steer pivots | `[±.45,.225,-1.02]`, radius `.225` |
| Pallet / cargo / buffer-pallet anchors on carriage | `[0,-.071,1.08]` / `[0,.069,1.08]` / `[0,-.008,1.08]` |
| Fork tips | `[±.225,.025,1.30]` |
| Station input / output / work cargo | `[-.72,.85,.23]` / `[.72,.85,.29]` / `[.23,.85,.005]` |
| Station worker / hands | `[.05,0,.85]` / `[-.03,1.05,.22]`, `[.43,1.05,.22]` |
| Scanner pivot / grip / lens | `[-.315,.894,-.27]` / `[-.315,.982,-.256]` / `[-.315,1.081,-.1765]` |
| Label output / packing carton pivot | `[-.52,.89,-.245]` / `[.23,.85,.005]` |
| Carton front / rear flap hinges | `[.23,1.15,.22]` / `[.23,1.15,-.21]` |
| Carton left / right flap hinges | `[-.01,1.15,.005]` / `[.47,1.15,.005]` |
| Input transfer path anchors | `[0,.9,1.5]` → `[0,.9,1.25]` → `[-.72,.9,1.25]` → `[-.72,.85,.5]` |
| Output transfer path anchors | `[.72,.85,-.5]` → `[.72,.9,-1.2]` → `[0,.9,-1.2]` → `[0,.9,-1.5]` |
| Pallet base / cargo | `[0,0,0]` / `[0,.14,0]` |
| Four pallet fork entries | `[±.225,.058,±.5]` |
| Crate cargo / contents / bottom | `[0,0,0]` / `[0,0,0]` / `[0,-.225,0]` |
| Crate grips | `[±.20,-.19,0]` |

Fork support top remains `.045`, pallet deck underside `.116`, pickup contact lift
`.071`, and buffer pickup lift `.008`. Steering rest orientation, articulation
parents and limits are retained. Crate's asset root was renamed from `crate__MODULE`
to `crate_root`; its five child parent-name strings follow that root, while their
local and asset transforms remain identical. Cargo stays centred at the origin.

**Review evidence and current limit**

All 16 fresh source renders completed serially using `render_asset.py --namespace v2`
with two Blender threads. The equipment agent opened all four comparison sheets;
the parent also reviewed all four and found no new visible form/join defects in
those views. GPU ownership was released after the series.

- [Forklift before/after and four views](../../work/visual-polish/equipment/after/forklift-before-after.png)
- [Crate before/after and four views](../../work/visual-polish/equipment/after/crate-before-after.png)
- [Packing station before/after and four views](../../work/visual-polish/equipment/after/packing-station-before-after.png)
- [Pallet before/after and four views](../../work/visual-polish/equipment/after/pallet-before-after.png)

Originals are preserved under `work/visual-polish/equipment/before`; new sources,
exports and renders are copied under `after`. Exact sizes/hashes are recorded in
[export-comparison.json](../../work/visual-polish/equipment/export-comparison.json).
This is a source four-view art review and an anchor comparison. Browser lighting,
materials and runtime contacts for these revised GLBs remain to be checked; the old
runtime PASS does not certify this revision.
