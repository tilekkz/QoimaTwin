"""Actual evaluated source-solid QA; never saves or edits the source file."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tools/blender/v3'))
from v3_common import runtime_xyz,xyz

STAGE=ROOT/'assets/v3/iterations/forklift/M14.2'
root=bpy.data.objects['forklift_root']
objects={o.name:o for o in root.children_recursive if o.type=='MESH'}
assert len(objects)==25
assert root.get('stage')=='M14.2_body_wheels_only'
assert root.matrix_world==__import__('mathutils').Matrix.Identity(4)
deps=bpy.context.evaluated_depsgraph_get()
solids={}
reports=[]
for name,obj in objects.items():
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    bm=bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(obj.matrix_world)
    bm.normal_update()
    assert all(e.is_manifold for e in bm.edges),name+' nonmanifold'
    volume=bm.calc_volume(signed=True)
    assert volume>1e-8,(name,volume)
    assert all(math.isfinite(c) for v in bm.verts for c in v.co)
    assert all(math.isfinite(c) for f in bm.faces for c in f.normal)
    assert all(abs(f.normal.length-1)<1e-5 for f in bm.faces)
    verts=[runtime_xyz(v.co) for v in bm.verts]
    bounds={'min':[min(v[i] for v in verts) for i in range(3)],
            'max':[max(v[i] for v in verts) for i in range(3)]}
    solids[name]=(BVHTree.FromBMesh(bm),verts)
    reports.append({'name':name,'parent':obj.parent.name,'vertices':len(bm.verts),
                    'faces':len(bm.faces),'positive_volume_m3':volume,'bounds':bounds,
                    'closed_manifold':True,'finite_unit_face_normals':True})
    bm.free()
    ev.to_mesh_clear()

directions=[Vector((1,.337,.171)).normalized(),Vector((.213,1,.451)).normalized(),Vector((.319,.127,1)).normalized()]
def interior(name,point):
    bvh,_=solids[name]
    p=xyz(point)
    nearest=bvh.find_nearest(p)
    votes=0
    for d in directions:
        origin=p.copy(); count=0
        for _ in range(100):
            hit,normal,index,dist=bvh.ray_cast(origin,d,20)
            if hit is None:break
            count+=1;origin=hit+d*.00001
        votes+=count%2
    return nearest[3] if votes>=2 else -nearest[3]

contacts=[]
def contact(a,b,p):
    margins=[interior(a,p),interior(b,p)]
    assert min(margins)>2e-5,(a,b,p,margins)
    contacts.append({'parts':[a,b],'point_runtime':p,'actual_solid_interior_margins_m':margins})

contact('chassis_rear_spine','chassis_front_spine',[0,.25,-.695])
contact('chassis_front_spine','driver_floorboard',[0,.49,-.4])
for sign,side in ((-1,'L'),(1,'R')):
    contact('driver_floorboard','entry_step_'+side,[sign*.295,.49,-.4])
contact('chassis_front_spine','petrol_nose',[0,.515,-.10])
contact('chassis_rear_spine','counterweight_body',[0,.51,-1.1])
contact('counterweight_body','counterweight_upper_step',[0,.85,-1.15])
contact('chassis_front_spine','rear_drop_connection',[0,.18,-.11])
contact('rear_drop_connection','low_forward_spine',[0,.085,-.085])
contact('low_forward_spine','front_axle_saddle',[0,.085,.4])
contact('front_axle_saddle','axle_front',[0,.30,.40])
contact('chassis_rear_spine','axle_rear',[0,.225,-1])
for axle,y,z,w,inner in (('front',.30,.40,.24,.135),('rear',.225,-1.,.20,.095)):
    for sign,side in ((-1,'L'),(1,'R')):
        suffix=axle+'_'+side
        contact('axle_'+axle,'hub_'+suffix,[sign*.33,y,z])
        contact('hub_'+suffix,'tyre_'+suffix,[sign*.35,y+inner+.0075,z])
        contact('hub_'+suffix,'hub_centre_'+suffix,[sign*(.35+w/2-.00425),y,z])
assert len(contacts)==24
connected={contacts[0]['parts'][0]}
while True:
    old=len(connected)
    for c in contacts:
        if any(n in connected for n in c['parts']):connected.update(c['parts'])
    if len(connected)==old:break
assert connected==set(objects),'Some actual source part has no contact chain'

ground=[]
for axle,y,z in (('front',.30,.40),('rear',.225,-1)):
    for sign,side in ((-1,'L'),(1,'R')):
        name='tyre_'+axle+'_'+side
        bvh,verts=solids[name]
        miny=min(p[1] for p in verts)
        assert abs(miny)<2e-5,(name,miny)
        hit,normal,index,dist=bvh.ray_cast(xyz((sign*.35,-.02,z+.00001)),xyz((0,1,0)),2)
        assert hit is not None
        h=runtime_xyz(hit)
        assert abs(h[1])<2e-5,(name,h)
        ground.append({'tyre':name,'actual_min_y':miny,'actual_ray_contact':h})

pivots={o.name:{'parent':o.parent.name,'local_runtime':runtime_xyz(o.location),
        'world_runtime':runtime_xyz(o.matrix_world.translation),'axis':o.get('rotation_axis_runtime')}
        for o in root.children_recursive if o.get('pivot_id')}
assert len(pivots)==6
for side in ('L','R'):
    assert pivots['joint__wheel_rear_'+side]['local_runtime']==[0,0,0]
    assert pivots['joint__wheel_rear_'+side]['parent']=='joint__rear_steer_'+side

steer=[]
for sign,side in ((-1,'L'),(1,'R')):
    wheel=[o for n,o in objects.items() if n.endswith('rear_'+side)]
    joint=bpy.data.objects['joint__rear_steer_'+side]
    joint.rotation_mode='QUATERNION'
    maxx=0;minimum_y=10
    for step in range(-150,151):
        angle=math.radians(step*.5)
        joint.rotation_quaternion=Quaternion(xyz((0,1,0)),angle)
        bpy.context.view_layer.update()
        for obj in wheel:
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
            pts=[runtime_xyz(ev.matrix_world@v.co) for v in mesh.vertices]
            maxx=max(maxx,max(abs(p[0]) for p in pts))
            minimum_y=min(minimum_y,min(p[1] for p in pts))
            ev.to_mesh_clear()
    joint.rotation_quaternion=Quaternion()
    bpy.context.view_layer.update()
    assert maxx<.60 and abs(minimum_y)<2e-5,(side,maxx,minimum_y)
    steer.append({'side':side,'poses':301,'angle_range_deg':[-75,75],
                   'actual_max_abs_x':maxx,'min_y':minimum_y,
                   'continuous_cylinder_bound_abs_x':.35+math.hypot(.225,.10)})

allpoints=[v for _,verts in solids.values() for v in verts]
bound={'min':[min(v[i] for v in allpoints) for i in range(3)],'max':[max(v[i] for v in allpoints) for i in range(3)]}
assert max(abs(a-b) for a,b in zip(bound['min'],[-.6,0,-1.5]))<2e-5
assert max(abs(a-b) for a,b in zip(bound['max'],[.6,.92,.7]))<2e-5
normal_count=sum(r['faces'] for r in reports)
report={'stage':'M14.2_body_wheels_only','source':bpy.data.filepath,
        'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
        'actual_meshes':reports,'actual_bounds':bound,'contacts':contacts,
        'all25parts_connected_by_actual_solid_witnesses':True,'ground':ground,
        'pivots':pivots,'steer':steer,'finite_unit_face_normals_checked':normal_count,
        'no_source_save':True,'complete_forklift_or_action_accepted':False}
(STAGE/'actual-source-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('M14_2_SOURCE_CHECKS '+json.dumps({'closed_parts':len(reports),'contacts':len(contacts),
      'ground':len(ground),'pivots':len(pivots),'bounds':bound,'steer':steer}))
