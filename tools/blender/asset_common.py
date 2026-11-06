"""Small metric Y-up modelling helpers. Execute only in task background Blender."""
from pathlib import Path
import json
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'qoyma-20x18-v1'

def xyz(point):
    return Vector((point[0], -point[2], point[1]))

def reset():
    if not bpy.app.background:
        raise RuntimeError('Use a new --background --factory-startup process.')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1

def material(name, color, roughness=.65, metallic=0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    if isinstance(color, str):
        color = color.lstrip('#')
        rgb = [int(color[i:i+2], 16)/255 for i in (0,2,4)]
        rgba = [(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4) for c in rgb] + [1]
    else:
        rgba = list(color[:3])+[color[3] if len(color)>3 else 1]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    node = next(node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = rgba
    node.inputs['Roughness'].default_value = roughness
    node.inputs['Metallic'].default_value = metallic
    return mat

def group(name):
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root['layout_version'] = VERSION
    return root

def _finish_object(obj, name, mat, parent, bevel=0):
    obj.name = name
    if mat is not None:
        obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new('Small manufactured edge bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = 1
        mod.harden_normals = True
        normal = obj.modifiers.new('Weighted face normals', 'WEIGHTED_NORMAL')
        normal.keep_sharp = True
        normal.weight = 50
    return obj

def box(name, loc, size, mat, parent=None, bevel=.01):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz(loc))
    obj = bpy.context.object
    obj.dimensions = (size[0], size[2], size[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish_object(obj,name,mat,parent,min(bevel,min(size)*.3) if bevel else 0)

def cylinder(name, loc, radius, depth, mat, parent=None, axis='Y', vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=xyz(loc))
    obj = bpy.context.object
    direction = {'X':(1,0,0),'Y':(0,0,1),'Z':(0,-1,0)}[axis]
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector(direction).to_track_quat('Z','Y')
    return _finish_object(obj,name,mat,parent,min(radius*.12,depth*.12,.008))

def beam(name, start, end, width, mat, parent=None):
    left,right = xyz(start),xyz(end)
    delta = right-left
    bpy.ops.mesh.primitive_cube_add(size=1,location=(left+right)*.5)
    obj = bpy.context.object
    obj.dimensions = (width,width,delta.length)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.rotation_mode='QUATERNION'
    obj.rotation_quaternion=delta.to_track_quat('Z','Y')
    return _finish_object(obj,name,mat,parent,min(width*.16,.006))

def ico(name, loc, radius, mat, parent=None, scale=(1,1,1), subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,radius=radius,location=xyz(loc))
    obj=bpy.context.object
    obj.scale=(scale[0],scale[2],scale[1])
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return _finish_object(obj,name,mat,parent)

def finish(asset_id, root, batch_runtime=True):
    source=ROOT/'assets'/'blender'/f'{asset_id}.blend'
    output=ROOT/'frontend'/'public'/'models'/f'{asset_id}.glb'
    source.parent.mkdir(parents=True,exist_ok=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    root['asset_id']=asset_id
    if 'role' not in root: root['role']='visual_asset'
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    meshes=[obj for obj in root.children_recursive if obj.type=='MESH']
    if root.type=='MESH': meshes.append(root)
    if batch_runtime:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in meshes: obj.select_set(True)
        bpy.context.view_layer.objects.active=meshes[0]
        bpy.ops.object.convert(target='MESH')
    # Preserve all editable parts in .blend, but export a material-batched runtime.
    batches={}
    for obj in (list(root.children_recursive) if batch_runtime else []):
        if obj.type=='MESH':
            key=tuple(mat.name for mat in obj.data.materials)
            batches.setdefault(key,[]).append(obj)
    for index,parts in enumerate(batches.values()):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts: obj.select_set(True)
        bpy.context.view_layer.objects.active=parts[0]
        if len(parts)>1: bpy.ops.object.join()
        bpy.context.object.name=f'{asset_id}__material_{index:02d}'
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for obj in root.children_recursive: obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',export_yup=True,export_extras=True,use_selection=True,export_texcoords=False,export_cameras=False,export_lights=False)
    objects=[obj for obj in root.children_recursive if obj.type=='MESH']
    # Joined objects can retain a rotated local frame; local AABB corners then
    # exaggerate world bounds. Measure the exported vertices themselves.
    bpy.context.view_layer.update()
    points=[obj.matrix_world@vertex.co for obj in objects for vertex in obj.data.vertices]
    minimum=[min(p[axis] for p in points) for axis in range(3)]
    maximum=[max(p[axis] for p in points) for axis in range(3)]
    triangles=0
    for obj in objects:
        obj.data.calc_loop_triangles()
        triangles+=len(obj.data.loop_triangles)
    report={'asset_id':asset_id,'source':str(source),'glb_bytes':output.stat().st_size,'runtime_meshes':len(objects),'triangles':triangles,'bounds_blender':{'min':minimum,'max':maximum},'runtime_size':[maximum[0]-minimum[0],maximum[2]-minimum[2],maximum[1]-minimum[1]]}
    (ROOT/'assets'/'blender'/f'{asset_id}.stats.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ASSET_EXPORTED '+json.dumps(report))
