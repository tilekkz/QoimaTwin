"""CPU actual cab/unchanged-body/unchanged-worker QA and a separate render fixture.

Open forklift-cab-stage.blend in a fresh background process. Never save back to
the production source. The separate with-driver-qa.blend is not an export asset.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

import bpy
import bmesh
from mathutils import Quaternion,Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[5]
STAGE=ROOT/'assets/v3/iterations/forklift/M14.3'
sys.path.insert(0,str(ROOT/'tools/blender/v3'))
from v3_common import xyz,runtime_xyz,material

hashfile=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(bpy.data.filepath)
source_hash=hashfile(source)
root=bpy.data.objects['forklift_root']
vehicle={o.name:o for o in root.children_recursive if o.type=='MESH'}
assert len(vehicle)==40
assert root.get('stage')=='M14.3_body_and_cab_no_mast'
spec=json.loads((ROOT/'assets/v3/specs/forklift.dimensions.json').read_text(encoding='utf-8'))
frozen=json.loads((ROOT/'assets/v3/iterations/forklift/M14.1/actual-blueprint-checks.json').read_text(encoding='utf-8'))
body=json.loads((ROOT/'assets/v3/iterations/forklift/M14.2/actual-source-checks.json').read_text(encoding='utf-8'))
assert hashfile(ROOT/'assets/v3/blender/forklift-body-wheels.blend')=='2c526a4fb281b49cce7c3e6e7411836a5968911965950708414975857aa670ff'

def evaluate(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    bm=bmesh.new();bm.from_mesh(mesh);bm.transform(obj.matrix_world);bm.normal_update()
    bvh=BVHTree.FromBMesh(bm)
    points=[runtime_xyz(v.co) for v in bm.verts]
    report={'name':obj.name,'parent':obj.parent.name if obj.parent else None,
            'volume':bm.calc_volume(signed=True),'manifold':all(e.is_manifold for e in bm.edges),
            'finite_unit_normals':all(all(math.isfinite(c) for c in f.normal) and abs(f.normal.length-1)<1e-5 for f in bm.faces),
            'modifier_types':[m.type for m in obj.modifiers],
            'min':[min(v[i] for v in points) for i in range(3)],'max':[max(v[i] for v in points) for i in range(3)]}
    bm.free();ev.to_mesh_clear()
    return bvh,points,report

solids={n:evaluate(o) for n,o in vehicle.items()}
assert all(s[2]['volume']>1e-8 and s[2]['manifold'] and s[2]['finite_unit_normals'] for s in solids.values())
assert solids['steering_column'][2]['max'][2]<=-.045+2e-5

# Load body source only as unexported comparison data, then unlink its objects.
with bpy.data.libraries.load(str(ROOT/'assets/v3/blender/forklift-body-wheels.blend'),link=False) as (available,loaded):
    loaded.objects=list(available.objects)
references=[o for o in loaded.objects if o]
refcoll=bpy.data.collections.new('QA_ONLY_BODY_REFERENCE');bpy.context.scene.collection.children.link(refcoll)
for obj in references:refcoll.objects.link(obj)
bpy.context.view_layer.update()
refparts={o.get('source_part_id'):o for o in references if o.type=='MESH'}
assert len(refparts)==25
body_errors=[]
for name,obj in refparts.items():
    _,old,old_report=evaluate(obj)
    _,new,new_report=solids[name]
    old=sorted(old);new=sorted(new)
    assert len(old)==len(new)
    error=max(abs(a-b) for p,q in zip(old,new) for a,b in zip(p,q))
    assert error<1e-8,(name,error)
    assert old_report['modifier_types']==new_report['modifier_types']
    body_errors.append({'part':name,'maximum_evaluated_vertex_error_m':error})
for obj in references:bpy.data.objects.remove(obj,do_unlink=True)
bpy.data.collections.remove(refcoll)

directions=[Vector((1,.337,.171)).normalized(),Vector((.213,1,.451)).normalized(),Vector((.319,.127,1)).normalized()]
def interior(name,point):
    bvh=solids[name][0];p=xyz(point);near=bvh.find_nearest(p);votes=0
    for d in directions:
        origin=p.copy();count=0
        for _ in range(100):
            hit,_,_,_=bvh.ray_cast(origin,d,20)
            if hit is None:break
            count+=1;origin=hit+d*.00001
        votes+=count%2
    return near[3] if votes>=2 else -near[3]

contacts=[]
def contact(a,b,p):
    margins=[interior(a,p),interior(b,p)]
    assert min(margins)>2e-5,(a,b,p,margins)
    contacts.append({'parts':[a,b],'point':p,'actual_interior_margins_m':margins})
for c in body['contacts']:contact(*c['parts'],c['point_runtime'])
contact('driver_floorboard','seat_pedestal',[0,.515,-.72])
contact('seat_pedestal','seat_cushion_rear',[0,.765,-.72])
contact('seat_cushion_rear','seat_cushion_nose',[0,.768,-.6525])
contact('seat_cushion_rear','seat_back',[0,.835,-.79])
for sign,side in ((-1,'L'),(1,'R')):
    contact('counterweight_body','guard_rear_'+side,[sign*.455,.8,-1.0])
    contact('petrol_nose','guard_front_'+side,[sign*.47,.7,-.07])
    for end,z in (('rear',-1.005),('front',-.07)):
        contact('guard_'+end+'_'+side,'roof_guard',[sign*.475,2.045,z])
c=spec['driver']['steering_column'];a=Vector(c['start']);b=Vector(c['end']);axis=(b-a).normalized()
p=a.lerp(b,(.70-a.y)/(b.y-a.y))
contact('petrol_nose','steering_column',list(p))
contact('steering_column','steering_hub',list(b-axis*.010))
contact('steering_hub','steering_yoke_crossbar',[0,1.285783894374534,-.2582260170000707])
for sign in [-1,1]:
    contact('steering_yoke_crossbar','steering_rim',[sign*.14,1.281,-.255])
for g in frozen['actualDriver']['grips']:
    sign=1 if g['side']=='L' else -1
    p=[v+sign*d*.035 for v,d in zip(g['centre'],g['axis'])]
    contact('steering_yoke_crossbar','steering_grip_'+g['side'],p)
assert len(contacts)==43
connected={next(iter(vehicle))}
while True:
    old=len(connected)
    for c in contacts:
        if any(n in connected for n in c['parts']):connected.update(c['parts'])
    if len(connected)==old:break
assert connected==set(vehicle)

# Actual unmodified source worker, posed with native Three intrinsic-XYZ
# quaternions mapped into Blender coordinates (w,x,-z,y), not copied Eulers.
workerfile=ROOT/'assets/v3/blender/worker-base.blend'
assert hashfile(ROOT/'frontend/public/models/v3/worker-base.glb')=='c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7'
with bpy.data.libraries.load(str(workerfile),link=False) as (available,loaded):
    loaded.objects=list(available.objects)
workers=[o for o in loaded.objects if o]
for obj in workers:bpy.context.scene.collection.objects.link(obj)
worker=next(o for o in workers if o.name=='worker_base_root')
worker.parent=root;worker.location=xyz(spec['driver']['worker_root_translation'])
for obj in workers:
    if obj.get('pivot_id') in spec['driver']['jointEulerXYZ']:
        x,y,z=spec['driver']['jointEulerXYZ'][obj['pivot_id']]
        sx,cx=math.sin(x/2),math.cos(x/2);sy,cy=math.sin(y/2),math.cos(y/2);sz,cz=math.sin(z/2),math.cos(z/2)
        qx=sx*cy*cz+cx*sy*sz;qy=cx*sy*cz-sx*cy*sz;qz=cx*cy*sz+sx*sy*cz;qw=cx*cy*cz-sx*sy*sz
        obj.rotation_mode='QUATERNION';obj.rotation_quaternion=Quaternion((qw,qx,-qz,qy))
bpy.context.view_layer.update()
workerparts={o.name:evaluate(o) for o in workers if o.type=='MESH'}
worker_anchors={o.get('anchor_id'):runtime_xyz(o.matrix_world.translation) for o in workers if o.get('anchor_id')}
for name,expected in frozen['actualDriver']['anchors'].items():
    assert max(abs(a-b) for a,b in zip(worker_anchors[name],expected))<2e-5,(name,worker_anchors[name],expected)

allowed={('driver_floorboard','boot_L'),('driver_floorboard','boot_R'),
         ('chassis_front_spine','boot_L'),('chassis_front_spine','boot_R'),
         ('seat_cushion_rear','pelvis_cloth')}
overlaps=[]
for vn,(vb,_,vr) in solids.items():
    for wn,(wb,_,wr) in workerparts.items():
        hits=vb.overlap(wb)
        if not hits:continue
        if (vn,wn) in allowed:
            assert wr['min'][1]>=vr['max'][1]-2e-5,(vn,wn,'support penetration')
            overlaps.append({'vehicle':vn,'worker':wn,'triangle_pairs':len(hits),'kind':'nonpenetrating support plane'})
        else:
            raise AssertionError(('unexpected actual vehicle/worker triangle intersection',vn,wn,len(hits)))
workerpoints=[p for _,ps,_ in workerparts.values() for p in ps]
worker_bounds={'min':[min(p[i] for p in workerpoints) for i in range(3)],'max':[max(p[i] for p in workerpoints) for i in range(3)]}
roof_gap=solids['roof_guard'][2]['min'][1]-worker_bounds['max'][1]
assert roof_gap>=.045
anchors={o.get('anchor_id'):runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get('anchor_id') and o not in workers}
for name in ('anchor_driver_seat','anchor_footrest_L','anchor_footrest_R','anchor_steering_grip_L','anchor_steering_grip_R'):
    assert max(abs(a-b) for a,b in zip(anchors[name],spec['anchors'][name]))<2e-5

# This is the unmodified neutral P01 source, including original blue clothing
# and badge. Production driver role05 is applied by accepted P02 at runtime.
root['asset_id']='forklift-cab-pair-qa';root['role']='QA_ONLY_seated_driver_clearance'
bpy.context.preferences.filepaths.save_version=0
fixture=STAGE/'with-driver-qa.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
assert hashfile(source)==source_hash
report={'stage':'M14.3','production_source_sha256':source_hash,'body_geometry_comparison':body_errors,
 'all25body_parts_unchanged':True,'closed_positive_parts':len(vehicle),'source_parts':[v[2] for v in solids.values()],
 'contacts':contacts,'all40vehicle_parts_connected':True,'actual_worker_anchors':worker_anchors,
 'actual_worker_bounds':worker_bounds,'roof_clearance_m':roof_gap,'allowed_surface_contacts':overlaps,
 'unexpected_worker_vehicle_intersections':0,'vehicle_anchors':anchors,
 'column_to_future_rear_plate_z_gap_m':-solids['steering_column'][2]['max'][2],
 'QA_worker_role':'unchanged neutral P01, not an extra production driver instance',
 'P01_geometry_scale_unchanged':True,'P01_source_sha256':hashfile(workerfile),'QA_fixture':str(fixture),
 'QA_fixture_sha256':hashfile(fixture),'production_source_saved':False,'complete_forklift_accepted':False}
(STAGE/'actual-cab-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('M14_3_CHECKS '+json.dumps({'vehicle_parts':len(vehicle),'contacts':len(contacts),'unchanged_body_parts':len(body_errors),
 'actual_roof_gap_m':roof_gap,'worker_bounds':worker_bounds,'unexpected_intersections':0,'paired_fixture':str(fixture)}))
