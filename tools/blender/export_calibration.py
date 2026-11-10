"""Create a task-local scale/axis fixture, not the warehouse design.

Run in a NEW factory-startup background Blender; never in a user's live scene.
"""
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'assets' / 'blender' / 'calibration.blend'
GLB = ROOT / 'frontend' / 'public' / 'models' / 'calibration.glb'
SOURCE.parent.mkdir(parents=True, exist_ok=True)
GLB.parent.mkdir(parents=True, exist_ok=True)

if not bpy.app.background:
    raise RuntimeError('Run with --background --factory-startup; this clears the temporary scene.')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1

def runtime_to_blender(pos):
    x, y, z = pos
    return x, -z, y

for name, pos in {
    'anchor_origin': (0, 0, 0), 'anchor_x': (1, 0, 0),
    'anchor_y': (0, 1, 0), 'anchor_z': (0, 0, 1),
    'anchor_box__S_A1_B1': (1.5, 0.9, 4),
}.items():
    obj = bpy.data.objects.new(name, None)
    obj.location = runtime_to_blender(pos)
    obj['layout_version'] = 'qoyma-20x18-v1'
    bpy.context.collection.objects.link(obj)

bpy.ops.mesh.primitive_cube_add(size=1, location=runtime_to_blender((0.5, 0.5, 0.5)))
cube = bpy.context.object
cube.name = 'calibration_cube_1m'
cube['layout_version'] = 'qoyma-20x18-v1'
cube['role'] = 'calibration_not_warehouse'
material = bpy.data.materials.new('CalibrationNeutral')
material.use_nodes = True
shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
shader.inputs['Base Color'].default_value = (0.2, 0.4, 0.5, 1)
shader.inputs['Roughness'].default_value = 0.8
cube.data.materials.append(material)
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
bpy.ops.export_scene.gltf(filepath=str(GLB), export_format='GLB', export_yup=True, export_extras=True)
print(f'QOIMA_CALIBRATION_EXPORTED {GLB}')
