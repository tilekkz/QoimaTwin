"""Read-only source gate for M14.4, including continuous swept-hull clearance.

Run against forklift-mast-stage.blend in background Blender. AABB separation
of actual evaluated endpoint vertices is a conservative proof for the two
declared translation-only operating regions, rather than a frame-rate sample.
"""
import hashlib
import itertools
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, runtime_xyz, xyz
from build_standard_carton import collect, empty_box

OUT=ROOT/'assets/v3/iterations/forklift/M14.4'
if '--output-dir' in sys.argv:
    OUT=(ROOT/sys.argv[sys.argv.index('--output-dir')+1]).resolve()
    assert ROOT.resolve() in OUT.parents,'QA output must stay in repository'
EPS=2e-6
root=bpy.data.objects['forklift_root']
source=Path(bpy.data.filepath)
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
parts,_=collect(root)
byname={p['name']:p for p in parts}
assert all(all(abs(v-1)<EPS for v in o.scale) for o in [root]+list(root.children_recursive))
lo=[min(p['low'][i] for p in parts) for i in range(3)]
hi=[max(p['high'][i] for p in parts) for i in range(3)]
assert max(abs(a-b) for a,b in zip(lo+hi,[-.6,0,-1.5,.6,2.1,1.5]))<EPS


def inside(part,point):
    p=xyz(point);near,normal,_,distance=part['bvh'].find_nearest(p)
    return distance if normal.dot(p-near)<0 else -distance


contacts=[]
def contact(a,b,p):
    margins=[inside(byname[n],p) for n in (a,b)]
    assert min(margins)>1e-5,(a,b,p,margins)
    contacts.append({'parts':[a,b],'point_runtime':p,'interior_margins_m':margins})

contact('chassis_front_spine','mast_foot_rear_connection',[0,.18,-.075])
contact('mast_foot_rear_connection','mast_foot_low_crossmember',[0,.09,-.023])
for sign,side in ((-1,'L'),(1,'R')):
    contact('mast_foot_low_crossmember','mast_'+side+'_rear_web',[sign*.24,.09,-.013])
    for label,x in (('inner_flange',.207),('outer_flange',.273)):
        contact('mast_'+side+'_rear_web','mast_'+side+'_'+label,[sign*x,.5,-.013])
    contact('mast_'+side+'_rear_web','mast_top_crossmember',[sign*.24,2.04,-.013])
    contact('mast_shoe_'+side,'carriage_rear_plate',[sign*.24,.75,.0655])
    contact('carriage_rear_plate','reach_outer_'+side,[sign*.504,.66,.072])
    contact('reach_inner_'+side,'carriage_forward_plate',[sign*.53,.6575,.38])
    contact('carriage_forward_plate','fork_'+side,[sign*.4,.72,.3875])
    shoe=byname['mast_shoe_'+side]
    assert .218-EPS<=min(abs(shoe['low'][0]),abs(shoe['high'][0]))
    assert max(abs(shoe['low'][0]),abs(shoe['high'][0]))<=.262+EPS
    for level in ('lower','upper'):
        roller=byname['mast_roller_'+side+'_'+level]
        assert abs(roller['low'][2]-(-.006))<EPS
        assert abs(roller['low'][2]-byname['mast_'+side+'_rear_web']['high'][2])<EPS
    fork=byname['fork_'+side]
    assert abs((fork['high'][0]-fork['low'][0])-.08)<EPS
    assert abs(fork['high'][2]-.4-1.1)<EPS
assert abs(byname['carriage_rear_plate']['low'][2]-.064)<EPS

# Compare every frozen body/cab component except the explicitly refined guard.
with bpy.data.libraries.load(str(ROOT/'assets/v3/blender/forklift-cab-stage.blend'),link=False) as (data,loaded):
    loaded.objects=list(data.objects)
refs=[o for o in loaded.objects if o]
collection=bpy.data.collections.new('READ_ONLY_CAB_COMPARISON');bpy.context.scene.collection.children.link(collection)
for obj in refs:collection.objects.link(obj)
reference_root=next(o for o in refs if o.name.startswith('forklift_root'))
old,_=collect(reference_root)
errors=[]
for p in old:
    obj=next(o for o in refs if o.name==p['name'])
    name=obj.get('source_part_id',obj.name.split('.')[0])
    if name=='roof_guard':continue
    before,after=sorted(p['verts']),sorted(byname[name]['verts'])
    if name=='chassis_front_spine':
        # M14.5 removes a hidden coincident cap under the unchanged floorboard.
        # Every replacement vertex remains inside the original convex box.
        assert all(all(p['low'][i]-EPS<=v[i]<=p['high'][i]+EPS for i in range(3)) for v in after)
        assert abs(byname[name]['high'][1]-(p['high'][1]-.005))<EPS
        errors.append({'part':name,'refinement':'hidden cap lowered5mm inside original hull; actual driver floor unchanged','maximum_removed_cap_m':.005})
        continue
    assert len(before)==len(after),(name,len(before),len(after))
    error=max(abs(a-b) for p,q in zip(before,after) for a,b in zip(p,q))
    assert error<EPS,(name,error)
    errors.append({'part':name,'maximum_vertex_error_m':error})
for obj in refs:bpy.data.objects.remove(obj,do_unlink=True)
bpy.data.collections.remove(collection)

body_names={r['part'] for r in errors}|{'roof_guard'}
fixed={n:p for n,p in byname.items() if n in body_names}
carriage=bpy.data.objects['joint__carriage'];reach=bpy.data.objects['joint__reach']
forkL=bpy.data.objects['joint__fork_L'];forkR=bpy.data.objects['joint__fork_R']
moving_names={o.name for o in carriage.children_recursive if o.type=='MESH'}

regions=[]
for title,tops,reaches in (('high travel/reach',[.70,1.50],[0,.40]),('stopped low fullreach',[.18,.70],[.40])):
    hulls={}
    for top,extension,spacing in itertools.product(tops,reaches,[.24,.40]):
        carriage.location=xyz((0,top,.04));reach.location=xyz((0,0,.36+extension))
        forkL.location=xyz((-spacing,0,0));forkR.location=xyz((spacing,0,0))
        current,_=collect(root)
        for p in current:
            if p['name'] not in moving_names:continue
            if p['name'] not in hulls:hulls[p['name']]={'low':p['low'][:],'high':p['high'][:]}
            else:
                h=hulls[p['name']]
                h['low']=[min(a,b) for a,b in zip(h['low'],p['low'])]
                h['high']=[max(a,b) for a,b in zip(h['high'],p['high'])]
    checked=0;min_gap=100;exact=[]
    for name,a in hulls.items():
        for fixed_name,b in fixed.items():
            gaps=[max(b['low'][i]-a['high'][i],a['low'][i]-b['high'][i]) for i in range(3)]
            separating=max(gaps)
            if separating<=EPS:
                # The cast ramp has an intentionally empty high rear corner.
                # Test its actual triangles/interior against the whole moving
                # hull when a coarse fixed-body AABB cannot separate it.
                empty_box([b],a['low'],a['high'],('continuous sweep',title,name,fixed_name))
                exact.append({'moving':name,'fixed':fixed_name,'proof':'actual fixed triangles and interior clear of full swept hull'})
            else:min_gap=min(min_gap,separating)
            checked+=1
    regions.append({'region':title,'fork_top_range_m':tops,'reach_range_m':reaches,
                    'halfspacing_range_m':[.24,.40],'continuous_hull_pairs_clear':checked,
                    'axis_separated_pairs_minimum_gap_m':min_gap,'exact_mesh_hull_proofs':exact})

carriage.location=xyz((0,.7,.04));reach.location=xyz((0,0,.36));forkL.location=xyz((-.4,0,0));forkR.location=xyz((.4,0,0))
bpy.context.view_layer.update()
assert source_hash==hashlib.sha256(source.read_bytes()).hexdigest()
report={'task_id':'M14.4','status':'VERIFY','source_sha256':source_hash,'source_unchanged_by_QA':True,
 'dimensions_m':[hi[i]-lo[i] for i in range(3)],'closed_positive_outward_parts':len(parts),
 'actual_interior_connections':contacts,'frozen_body_cab_vertex_comparison':errors,
 'roof_refinement':'M14.2-REACH open slat guard; same bounds and underside, no original cab source/output edits',
 'surface_refinement':'M14.5 hidden chassis cap5mm below unchanged floorboard; fork heel backing inset1mm; welded contacts retained',
 'guide_air_m':{'shoe_each_X':.004,'rear_plate_to_fixed_rail_front':.004,'telescoping_each_X':.004,'telescoping_each_Y':.0045},
 'reach_stroke_m':.4,'fixed_guide_length_m':.64,'minimum_overlap_m':.24,
 'actual_inner_guide_bind_z_m':[byname['reach_inner_L']['low'][2],byname['reach_inner_L']['high'][2]],
 'actual_minimum_nested_overlap_m':min(min(byname['reach_inner_L']['high'][2]+delta,byname['reach_outer_L']['high'][2])-max(byname['reach_inner_L']['low'][2]+delta,byname['reach_outer_L']['low'][2]) for delta in (0,.4)),
 'roller_web_contact':'Four actual cylinder tangencies at Z=-.006',
 'continuous_moving_vs_body_clearance':regions,'fork_dimensions_W_H_L_m':[.08,.07,1.10],
 'limits':'This is the mast mechanics/source gate. Complete HU actions, cradle, runtime control constraints and paired driver remain separate M14/P/W gates.'}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'actual-mast-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('M144_SOURCE_VERIFIED '+json.dumps({'parts':len(parts),'connections':len(contacts),'frozen_parts':len(errors),'continuous_regions':regions}))
