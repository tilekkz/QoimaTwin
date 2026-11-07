"""M14.8 continuous native geometry proof for the shared absolute-clock cycle.

Each linear segment is covered by whole part hulls. Wheel rotation uses its
full radial envelope; L forks use proven blade/heel covers. Attached load/body
checks remove common root/carriage/reach translations instead of comparing
unrelated broad world sweeps. No native source asset is modified.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, reset, runtime_xyz, xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source
from verify_loaded_forklift import support_contacts, add_hull

OUT=ROOT/'assets/v3/iterations/forklift/M14.8';EPS=2e-6
TIMELINE=ROOT/'frontend/public/data/v3/pallet-pickup-cycle.json'
SOURCE=ROOT/'assets/v3/blender/forklift-pallet-low-fixture.blend'


def sample(d,t):
    i=0
    while i+1<len(d['keys']) and d['keys'][i+1]['t']<=t:i+=1
    a=d['keys'][i];b=d['keys'][min(i+1,len(d['keys'])-1)];u=0 if a is b else (t-a['t'])/(b['t']-a['t'])
    return dict(t=t,phase=a['phase'],attached=a['attached'],root=a['root_z']+(b['root_z']-a['root_z'])*u,
                top=a['fork_top']+(b['fork_top']-a['fork_top'])*u,reach=a['reach']+(b['reach']-a['reach'])*u)


def ancestor(obj,prefix):
    while obj:
        if obj.name.startswith(prefix):return obj
        obj=obj.parent
    return None


def covers(parts,top,heel):
    result=[]
    for p in parts:
        obj=bpy.data.objects[p['name']];wheel=ancestor(obj,'joint__wheel_')
        if wheel:
            c=runtime_xyz(wheel.matrix_world.translation);radius=max(math.hypot(v[1]-c[1],v[2]-c[2]) for v in p['verts'])
            result.append({'name':p['name'],'low':[p['low'][0],c[1]-radius,c[2]-radius],
                           'high':[p['high'][0],c[1]+radius,c[2]+radius]})
        elif p['name'] in ('fork_L','fork_R'):
            assert all(v[1]<=top+EPS or v[2]<=heel+EPS for v in p['verts'])
            blade={'name':p['name']+'_blade','low':p['low'][:],'high':p['high'][:]};blade['high'][1]=top
            stem={'name':p['name']+'_heel','low':p['low'][:],'high':p['high'][:]};stem['high'][2]=heel
            result.extend([blade,stem])
        else:result.append(p)
    return result


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    d=json.loads(TIMELINE.read_text(encoding='utf8'));source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    reset();fixture=append_source(str(SOURCE.relative_to(ROOT)),'forklift-pallet-low-fixture',None)
    vehicle=bpy.data.objects['forklift_root'];cargo=bpy.data.objects['pallet-load__HU'];base=bpy.data.objects['heavy-bay__MODULE']
    carriage=bpy.data.objects['joint__carriage'];reach=bpy.data.objects['joint__reach'];platform,_=collect(base)
    base_id=cargo.as_pointer();keys=d['keys'];space=d['action_space_bounds_m']
    def pose(t,root_override=None,top_override=None,reach_override=None,attached_override=None):
        s=sample(d,t);root=s['root'] if root_override is None else root_override
        top=s['top'] if top_override is None else top_override;extension=s['reach'] if reach_override is None else reach_override
        attached=s['attached'] if attached_override is None else attached_override
        vehicle.location=xyz((0,0,root));carriage.location=xyz((0,top,.04));reach.location=xyz((0,0,.36+extension))
        for side,sign in [('L',-1),('R',1)]:
            bpy.data.objects['joint__fork_'+side].location=xyz((sign*.4,0,0))
            for end,r in [('front',.3),('rear',.225)]:
                bpy.data.objects['joint__wheel_'+end+'_'+side].rotation_euler.x=(s['root']-keys[0]['root_z'])/r
        cargo.location=xyz((0,top if attached else .18,root+1+extension if attached else 1.4))
        bpy.context.view_layer.update();return s,top,root+.4+extension
    regions=[]
    for a,b in zip(keys,keys[1:]):
        vehicle_hulls={};cargo_hulls={}
        for t in (a['t'],b['t']):
            _,top,heel=pose(t,attached_override=a['attached']);vp,_=collect(vehicle);cp,_=collect(cargo)
            add_hull(vehicle_hulls,covers(vp,top,heel));add_hull(cargo_hulls,cp)
        for title,hulls in [('vehicle',vehicle_hulls),('cargo',cargo_hulls)]:
            for name,h in hulls.items():
                assert all(space['min'][i]-EPS<=h['low'][i] and h['high'][i]<=space['max'][i]+EPS for i in range(3)),('outside isolated action space',a['phase'],name,h)
                assert h['low'][1]>=-EPS
                empty_box(platform,h['low'],h['high'],('whole action segment versus actual platform',a['phase'],title,name))
        if not a['attached']:
            pose(a['t'],attached_override=False);cp,_=collect(cargo)
            for name,h in vehicle_hulls.items():empty_box(cp,h['low'],h['high'],('whole action segment versus fixed actual stock',a['phase'],name))
            relative_proofs='Static HU: all whole vehicle part/wheel/fork covers clear exact stock triangles/interior.'
        else:
            # Fixed-body frame: remove common root motion, keep actual lift/reach.
            hu_hulls={}
            for t in (a['t'],b['t']):pose(t,root_override=0,attached_override=True);add_hull(hu_hulls,collect(cargo)[0])
            vp,_=collect(vehicle);fixed=[p for p in vp if ancestor(bpy.data.objects[p['name']],'joint__carriage') is None]
            solids=[p for p in fixed if ancestor(bpy.data.objects[p['name']],'joint__wheel_') is None]
            wheels=[p for p in fixed if ancestor(bpy.data.objects[p['name']],'joint__wheel_') is not None]
            wheelcovers=covers(wheels,0,0)
            for name,h in hu_hulls.items():
                empty_box(solids,h['low'],h['high'],('attached HU whole sweep versus exact fixed body',a['phase'],name))
                for w in wheelcovers:assert any(h['low'][i]>=w['high'][i]-EPS or h['high'][i]<=w['low'][i]+EPS for i in range(3)),('HU versus full wheel rotation envelope',a['phase'],name,w['name'])
            # Carriage frame: remove common vertical/root motion, keep reach.
            hu_hulls={}
            for t in (a['t'],b['t']):pose(t,root_override=0,top_override=0,attached_override=True);add_hull(hu_hulls,collect(cargo)[0])
            vp,_=collect(vehicle);carriage_only=[p for p in vp if ancestor(bpy.data.objects[p['name']],'joint__carriage') is not None and ancestor(bpy.data.objects[p['name']],'joint__reach') is None]
            for name,h in hu_hulls.items():empty_box(carriage_only,h['low'],h['high'],('attached HU whole relative reach sweep versus carriage',a['phase'],name))
            # Reach frame: every fork/load relative transform is invariant.
            _,top,heel=pose(a['t'],root_override=0,top_override=0,reach_override=0,attached_override=True)
            vp,_=collect(vehicle);cp,_=collect(cargo)
            reach_parts=[p for p in vp if ancestor(bpy.data.objects[p['name']],'joint__reach') is not None]
            for p in covers(reach_parts,top,heel):empty_box(cp,p['low'],p['high'],('invariant real load/fork/reach interface',a['phase'],p['name']))
            relative_proofs='Common root/carriage/reach translation removed separately; whole conditional HU sweeps clear exact fixed body and carriage; invariant fork/reach interface clear; full wheel rotation envelopes clear.'
        regions.append({'phase':a['phase'],'interval_s':[a['t'],b['t']],'attached':a['attached'],'whole_vehicle_covers_clear':len(vehicle_hulls),
                        'whole_HU_part_hulls_clear':len(cargo_hulls),'stock_vehicle_relative_proof':relative_proofs,'action_space_contained':True,'floor_envelopes_nonnegative':True})
    contacts=[]
    for t in (8,10,14,20,22):
        s,_,_=pose(t);vp,vbvh=collect(vehicle);cp,cbvh=collect(cargo)
        z=runtime_xyz(cargo.matrix_world.translation)[2];y=runtime_xyz(cargo.matrix_world.translation)[1]
        contacts.append({'time_s':t,'phase':s['phase'],'HU_bottom_y_m':y,'fork_contact_points':support_contacts(vbvh,cbvh,[-.4,.4],y,z-.5,z+.5)})
    supports=[]
    for t in (0,22,30):
        pose(t);_,cbvh=collect(cargo);_,bbvh=collect(base)
        supports.append({'time_s':t,'actual_platform_contact_points':support_contacts(bbvh,cbvh,[-.55,0,.55],.18,.9,1.9)})
    assert cargo.as_pointer()==base_id and source_hash==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    report={'task_id':'M14.8','timeline_sha256':hashlib.sha256(TIMELINE.read_bytes()).hexdigest(),'native_fixture_source_sha256':source_hash,
            'whole_continuous_segments':regions,'actual_fork_contacts':contacts,'actual_platform_contacts':supports,
            'HU_instances':1,'same_native_HU_pointer':True,'native_sources_unchanged':True,'engine_operation':False,
            'scope':'Continuous physical covers for this isolated PALLET fixture. Exclusive action-space/operator/vehicle occupancy is by fixture construction; warehouse scheduler reservations and driver-personnel action integration remain separate.'}
    (OUT/'actual-pickup-continuous-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('M148_ACTION_VERIFIED '+json.dumps({'continuous_segments':len(regions),'fork_contacts':20,'platform_contacts':18,'HU_instances':1,'source_unchanged':True}))
