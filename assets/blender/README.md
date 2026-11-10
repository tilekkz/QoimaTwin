# Blender pipeline — participant A

`calibration.blend` and `frontend/public/models/calibration.glb` are technical
fixtures, not a proposed warehouse design. The cube is exactly 1m; axis empties
and the S_A1_B1 box anchor verify the canonical coordinate conversion.

Rebuild from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/export-calibration.ps1
```

The script uses a NEW factory-startup background Blender process. It never
clears a live user's scene. Blender defaults to the verified Windows 5.0 path;
pass `-BlenderPath` if installed elsewhere.

For live MCP editing, `tools/start-blender.ps1` starts a separate hidden Blender
instance with this task's calibration file. It checks for an existing listener
on localhost:9876 first and will not replace it. Verify `get_addon_status` and
`get_scene_info` before editing; do not assume that an existing listener is this
project. Keep the task instance open while using MCP.

Runtime axes are X/Z floor, Y up, metres. Blender coordinates are
`(x_B, y_B, z_B) = (x_runtime, -z_runtime, y_runtime)`. Export glTF +Y up,
custom properties/extras, no second corrective rotation in Three.js.

Future assets: one rack bay, one crate, picker/cart, pack station, buffer.
Keep business slot IDs stable; SKU assignment is data, not permanent mesh names.
Use plain metal/rough PBR, no runtime external textures/CDNs. Start without
compression decoders. Project targets: <=5MB GLB, <=100k visible triangles per
warehouse, <=150 draw calls for the complete paired frame. These targets have
not been measured for a warehouse yet. See root 03_3D_Scene_and_Replay.md.
