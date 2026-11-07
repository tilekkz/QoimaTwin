"""Lean queued Workbench views with a fixed-camera before/after axle closeup.

Shares verified I09 projected-vertex fit and matte settings. No source save.
The closeup deliberately frames only the front structural region and hides
cab/controls; full views and paired quarter retain the complete hierarchy.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[6]
sys.path.insert(0,str(ROOT/'tools/blender/v3'))
from v3_common import xyz
args=sys.argv[sys.argv.index('--')+1:]
p=argparse.ArgumentParser();p.add_argument('asset_id');p.add_argument('--mode',choices=['full','close','quarter'],required=True);p.add_argument('--out',required=True);a=p.parse_args(args)
out=Path(a.out);assert out.is_absolute();out.mkdir(parents=True,exist_ok=True)
source=Path(bpy.data.filepath);sha=hashlib.sha256(source.read_bytes()).hexdigest()
root=next(o for o in bpy.context.scene.objects if o.get('namespace')=='v3' and o.get('asset_id')==a.asset_id)
objects=[o for o in root.children_recursive if o.type=='MESH']
points=[]
for obj in objects:
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
    points.extend(ev.matrix_world@v.co for v in m.vertices);ev.to_mesh_clear()
low=Vector([min(v[i] for v in points) for i in range(3)]);high=Vector([max(v[i] for v in points) for i in range(3)])
extent=max(high-low);scene=bpy.context.scene
for obj in scene.objects:
    if obj.type=='MESH' and obj not in objects:obj.hide_render=True
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
s=scene.display.shading;s.light='STUDIO';s.studiolight_rotate_z=.35;s.color_type='MATERIAL';s.show_shadows=True;s.show_cavity=True;s.cavity_type='BOTH';s.curvature_ridge_factor=.65;s.curvature_valley_factor=.55;s.show_specular_highlight=False;s.background_type='WORLD'
if scene.world is None:scene.world=bpy.data.worlds.new('QA_repair_world')
scene.world.color=(.48,.49,.48);scene.view_settings.view_transform='Standard';scene.view_settings.exposure=.7
bpy.ops.mesh.primitive_plane_add(size=extent*10,location=(0,0,low.z-.002));floor=bpy.context.object;floor.name='STUDIO_ONLY__repair_floor'
mat=bpy.data.materials.new('STUDIO_ONLY__repair_floor_mat');mat.diffuse_color=(.65,.66,.64,1);floor.data.materials.append(mat)
data=bpy.data.cameras.new('STUDIO_ONLY__repair_camera');camera=bpy.data.objects.new('STUDIO_ONLY__repair_camera',data);scene.collection.objects.link(camera);scene.camera=camera
data.type='ORTHO';data.clip_start=.001;data.clip_end=extent*20
views=[('front',(0,.02,1)),('side',(1,.02,0)),('rear',(0,.02,-1)),('three-quarter',(1.25,.8,1.6)),('wheel-close',(1.25,.7,1.6))] if a.mode=='full' else [('wheel-close',(1.25,.7,1.6))] if a.mode=='close' else [('three-quarter',(1.25,.8,1.6))]
reports={}
for name,direction in views:
    isclose=name=='wheel-close'
    for obj in objects:obj.hide_render=isclose and obj.get('forklift_component_class') in ('cab','control')
    fit=[xyz((x,y,z)) for x in [-.64,.64] for y in [-.02,.78] for z in [-.30,.76]] if isclose else points
    minimum=Vector([min(v[i] for v in fit) for i in range(3)]);maximum=Vector([max(v[i] for v in fit) for i in range(3)])
    target=(minimum+maximum)*.5
    camera.location=target+xyz(direction).normalized()*extent*3
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    inverse=camera.rotation_euler.to_quaternion().inverted()
    projected=[inverse@(v-target) for v in fit]
    lo=[min(v[i] for v in projected) for i in range(2)];hi=[max(v[i] for v in projected) for i in range(2)]
    shift=camera.rotation_euler.to_quaternion()@Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,0))
    camera.location+=shift;target+=shift
    projected=[inverse@(v-target) for v in fit]
    data.ortho_scale=2*max(abs(v[i]) for v in projected for i in range(2))*1.16
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    reports[name]={'png':str(out/(name+'.png')),'sha256':hashlib.sha256((out/(name+'.png')).read_bytes()).hexdigest(),
                   'camera_location':list(camera.location),'camera_quaternion':list(camera.rotation_euler.to_quaternion()),'ortho_scale':data.ortho_scale,
                   'fit':'fixed front-structure ROI, cab/controls hidden' if isclose else 'actual evaluated complete hierarchy vertices'}
assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
report={'source':str(source),'source_sha256':sha,'asset_id':a.asset_id,'mode':a.mode,'resolution':[900,900],'views':reports,'source_saved':False}
(out/'render-provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('AXLE_REPAIR_RENDERED '+json.dumps(report))
