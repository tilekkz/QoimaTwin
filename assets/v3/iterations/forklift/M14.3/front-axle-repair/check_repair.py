"""Bounded actual front-frame repair QA; no route/role pipeline rerun."""
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[6]
STAGE=ROOT/'assets/v3/iterations/forklift/M14.3/front-axle-repair'
sys.path.insert(0,str(ROOT/'tools/blender/v3'))
from v3_common import xyz,runtime_xyz
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(bpy.data.filepath);source_hash=H(source)
assert H(ROOT/'docs/v3/contract-proposals/vehicle-handling-v3.json')=='22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4'
assert H(ROOT/'frontend/public/models/v3/worker-base.glb')=='c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7'
root=bpy.data.objects['forklift_root']
parts={o.get('source_part_id'):o for o in root.children_recursive if o.type=='MESH'}
assert len(parts)==45
changed={'low_forward_spine','front_axle_saddle','axle_front'}
added={'lower_front_crossmember','outboard_frame_cheek_L','outboard_frame_cheek_R',
       'front_bearing_collar_L','front_bearing_collar_R'}
affected=changed|added

def evaluate(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();m.calc_loop_triangles()
    points=[runtime_xyz(obj.matrix_world@v.co) for v in m.vertices]
    triangles=[[points[v] for v in tri.vertices] for tri in m.loop_triangles]
    bm=bmesh.new();bm.from_mesh(m);bm.transform(obj.matrix_world);bm.normal_update()
    assert all(e.is_manifold for e in bm.edges),obj.name
    vol=bm.calc_volume(signed=True);assert vol>1e-8,(obj.name,vol)
    assert all(math.isfinite(c) for p in points for c in p)
    assert all(abs(f.normal.length-1)<1e-5 and all(math.isfinite(c) for c in f.normal) for f in bm.faces)
    bounds={'min':[min(v[i] for v in points) for i in range(3)],'max':[max(v[i] for v in points) for i in range(3)]}
    result={'name':obj.get('source_part_id'),'points':points,'triangles':triangles,'volume':vol,'bounds':bounds,
            'modifiers':[m.type for m in obj.modifiers],'bvh':BVHTree.FromBMesh(bm)}
    bm.free();ev.to_mesh_clear();return result

solids={n:evaluate(o) for n,o in parts.items()}

def comparison(file,expected,skip=()):
    with bpy.data.libraries.load(str(file),link=False) as (available,loaded):loaded.objects=list(available.objects)
    refs=[o for o in loaded.objects if o];coll=bpy.data.collections.new('QA_ONLY_COMPARE');bpy.context.scene.collection.children.link(coll)
    for obj in refs:coll.objects.link(obj)
    bpy.context.view_layer.update()
    meshes={o.get('source_part_id'):o for o in refs if o.type=='MESH'};assert len(meshes)==expected
    out=[]
    for name,obj in meshes.items():
        if name in skip:continue
        old=evaluate(obj);new=solids[name]
        a,b=sorted(old['points']),sorted(new['points']);assert len(a)==len(b),name
        error=max(abs(x-y) for p,q in zip(a,b) for x,y in zip(p,q));assert error<1e-8,(name,error)
        assert old['modifiers']==new['modifiers']
        out.append({'part':name,'max_evaluated_vertex_error_m':error})
    for obj in refs:bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(coll);return out

unchanged=comparison(STAGE/'before/forklift-cab-stage.blend',40,changed)
assert len(unchanged)==37
body_match=comparison(ROOT/'assets/v3/blender/forklift-body-wheels.blend',30)

directions=[Vector((1,.337,.171)).normalized(),Vector((.213,1,.451)).normalized(),Vector((.319,.127,1)).normalized()]
def interior(name,p):
    b=solids[name]['bvh'];p=xyz(p);distance=b.find_nearest(p)[3];votes=0
    for d in directions:
        q=p.copy();count=0
        for _ in range(80):
            h,_,_,_=b.ray_cast(q,d,20)
            if h is None:break
            count+=1;q=h+d*.00001
        votes+=count%2
    return distance if votes>=2 else -distance

before=json.loads((ROOT/'assets/v3/iterations/forklift/M14.3/actual-cab-checks.json').read_text(encoding='utf-8'))
contacts=[]
def contact(a,b,p):
    margins=[interior(a,p),interior(b,p)];assert min(margins)>2e-5,(a,b,p,margins)
    contacts.append({'parts':[a,b],'point':p,'actual_interior_margins_m':margins})
for c in before['contacts']:contact(*c['parts'],c['point'])
contact('low_forward_spine','lower_front_crossmember',[0,.060,0])
for sign,side in ((-1,'L'),(1,'R')):
    contact('entry_step_'+side,'outboard_frame_cheek_'+side,[sign*.585,.40,-.17])
    contact('lower_front_crossmember','outboard_frame_cheek_'+side,[sign*.585,.080,0])
    contact('front_axle_saddle','front_bearing_collar_'+side,[sign*.20,.30,.40])
    contact('axle_front','front_bearing_collar_'+side,[sign*.215,.30,.40])
assert len(contacts)==52
connected={next(iter(parts))}
while True:
    old=len(connected)
    for c in contacts:
        if any(n in connected for n in c['parts']):connected.update(c['parts'])
    if len(connected)==old:break
assert connected==set(parts)

# Actual source triangles at the moving rear-plate Z band. Clipping captures
# the ramp shape; its overall AABB would incorrectly fill the low gooseneck.
def clip(poly,z,keep_greater):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        ina=a[2]>=z if keep_greater else a[2]<=z
        inb=b[2]>=z if keep_greater else b[2]<=z
        if ina!=inb:
            t=(z-a[2])/(b[2]-a[2]);out.append([a[i]+t*(b[i]-a[i]) for i in range(3)])
        if inb:out.append(b)
    return out
slice_points=[]
for tri in solids['low_forward_spine']['triangles']:
    p=clip(tri,0,True)
    if p:p=clip(p,.08,False)
    slice_points+=p
slice_max_y=max(p[1] for p in slice_points)
assert .11-slice_max_y>.0149

clearances=[]
def gap(name,value):assert value>2e-5,(name,value);clearances.append({'interface':name,'continuous_gap_m':value})
gap('rearplate_minY_to_actual_ramp_slice',.11-slice_max_y)
gap('rearplate/outerguide_minY_to_rear_crossmember',.11-solids['lower_front_crossmember']['bounds']['max'][1])
gap('outerguide/plate_max_absX_to_cheeks',min(abs(p[0]) for n in added if n.startswith('outboard') for p in solids[n]['points'])-.56)
max_y=max(p[1] for n in affected for p in solids[n]['points']);max_z=max(p[2] for n in affected for p in solids[n]['points'])
gap('high_forward_plate_and_forks',.63-max_y)
gap('low_extended_forward_plate',.76-max_z);gap('low_extended_fork_stem',.775-max_z)
gap('rear_steered_tyre_envelope',min(p[2] for n in affected for p in solids[n]['points'])-(-1+math.hypot(.225,.10)))
worker_min_y=before['actual_worker_bounds']['min'][1];gap('unchanged_seated_worker_all_new_fixed_parts',worker_min_y-max_y)

tyres=['tyre_front_L','tyre_front_R','tyre_rear_L','tyre_rear_R']
for n in affected:
    for t in tyres:assert not solids[n]['bvh'].overlap(solids[t]['bvh']),(n,t)
front_inner=min(abs(p[0]) for p in solids['tyre_front_R']['points'])
gap('front_tyre_inner_face_to_bearing_collar',front_inner-max(abs(p[0]) for p in solids['front_bearing_collar_R']['points']))
gap('rear_crossmember_to_front_tyre_rear_face',min(p[2] for p in solids['tyre_front_R']['points'])-solids['lower_front_crossmember']['bounds']['max'][2])
gap('shaft_to_rotating_annular_tyre_bore',.135*math.cos(math.pi/24)-.09)
stub=min(abs(p[0]) for p in solids['hub_front_R']['points'])-max(abs(p[0]) for p in solids['front_bearing_collar_R']['points'])
assert .0089<stub<.0091

allpoints=[p for s in solids.values() for p in s['points']]
assert all(-.60002<=p[0]<=.60002 and -.00002<=p[1]<=2.10002 and -1.50002<=p[2]<=1.50002 for p in allpoints)
negatives={'raised_rear_frame_20mm_rejected':.11-(slice_max_y+.02)<0,'cheek_shift20mm_into_guide_rejected':.57-.02-.56<0}
assert all(negatives.values())

# Reuse accepted frozen P01 posed objects for a single paired-quarter witness;
# no role/worker rebuilding and no source/production worker modification.
fixture_source=ROOT/'assets/v3/iterations/forklift/M14.3/with-driver-03.blend'
with bpy.data.libraries.load(str(fixture_source),link=False) as (available,loaded):loaded.objects=list(available.objects)
refs=[o for o in loaded.objects if o]
worker=next(o for o in refs if o.name=='worker_base_root')
keep={worker,*worker.children_recursive}
for obj in keep:bpy.context.scene.collection.objects.link(obj)
worker.parent=root
for obj in refs:
    if obj not in keep:bpy.data.objects.remove(obj,do_unlink=True)
root['asset_id']='forklift-cab-repair-pair-qa';root['role']='QA_ONLY_unchanged_seated_P01'
bpy.context.preferences.filepaths.save_version=0
pair=STAGE/'paired-after.blend';bpy.ops.wm.save_as_mainfile(filepath=str(pair))
assert H(source)==source_hash
report={'scope':'bounded front attachment repair; no mast/action acceptance','source_sha256':source_hash,
 'closed_positive_parts':45,'actual_contacts':contacts,'all45parts_connected':True,'unchanged37parts':unchanged,
 'body_cab30part_consistency':body_match,'affected_parts':sorted(affected),
 'actual_affected_bounds':{n:solids[n]['bounds'] for n in affected},
 'actual_ramp_triangle_slice_max_y':slice_max_y,'continuous_interface_clearances':clearances,
 'proof_domain':'all forkTop>=.70/reach0...40 and fullreach.40/forkTop.18...1.50; both forkhalfspacing.24...40; same hull',
 'actual_tyre_triangle_intersections':0,'front_exposed_stub_m':stub,'before_front_exposed_stub_m':.084,
 'ground_wheel_centres_unchanged':True,'new_parts_contained_in_original_hull':True,'negative_cases':negatives,
 'paired_fixture':str(pair),'paired_fixture_sha256':H(pair),'P01_reused_frozen_fixture':str(fixture_source),
 'production_worker_embedded':False,'C08_modified':False,'production_source_saved':False}
(STAGE/'actual-repair-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('AXLE_REPAIR_CHECKS '+json.dumps({'parts':45,'contacts':len(contacts),'unchanged':len(unchanged),
 'body_cab_consistent':len(body_match),'slice_y':slice_max_y,'stub':stub,'clearances':clearances,'negative_cases':negatives}))
