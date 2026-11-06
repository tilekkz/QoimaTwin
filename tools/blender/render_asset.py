"""Four honest geometry views for an individual saved asset (no reference compositing)."""
import bpy
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
asset=sys.argv[sys.argv.index('--')+1]
out=ROOT/'assets'/'previews'/asset
out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=640
scene.render.resolution_y=640
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.display.shading.light='STUDIO'
scene.display.shading.studiolight_rotate_z=.35
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type='BOTH'
scene.display.shading.curvature_ridge_factor=1.3
scene.display.shading.curvature_valley_factor=1.1
scene.display.shading.show_specular_highlight=True
scene.display.shading.background_type='WORLD'
scene.world.color=(.18,.18,.18)
scene.view_settings.view_transform='Standard'
meshes=[o for o in scene.objects if o.type=='MESH']
points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
lo=Vector([min(p[k] for p in points) for k in range(3)])
hi=Vector([max(p[k] for p in points) for k in range(3)])
target=(lo+hi)/2
extent=max(hi-lo)
data=bpy.data.cameras.new('QA camera')
cam=bpy.data.objects.new('QA camera',data)
scene.collection.objects.link(cam)
scene.camera=cam
data.type='ORTHO'
data.ortho_scale=extent*1.3
for name,direction in [('front',(0,-1,.03)),('side',(1,0,.03)),('rear',(0,1,.03)),('three-quarter',(1.1,-1.5,1))]:
    if asset in {'environment','warehouse'} and name=='three-quarter': direction=(1.1,1.5,1.2)
    cam.location=target+Vector(direction).normalized()*extent*3
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/f'{name}.png')
    bpy.ops.render.render(write_still=True)
print(f'ASSET_QA_RENDERED {asset}')
