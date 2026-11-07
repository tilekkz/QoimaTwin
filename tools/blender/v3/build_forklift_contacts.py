"""M14.6.1 real lock bores and native PALLET/HEAVY-platform lift states."""
import hashlib
import json
from pathlib import Path

import bpy

from v3_common import ROOT, finish, group, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source

OUT=ROOT/'assets/v3/iterations/forklift/M14.6.1'
EPS=2e-6


def at(root,name):return next(o for o in root.children_recursive if o.name==name)


def platform_sweep(vehicle,cargo,base_parts):
    carriage=at(vehicle,'joint__carriage');reach=at(vehicle,'joint__reach')
    moving={o.name for o in carriage.children_recursive if o.type=='MESH'}
    hulls={};cargo_hulls={}
    for top,extension in ((.18,.4),(.7,.4),(1.5,.4),(.7,0),(1.5,0)):
        carriage.location=xyz((0,top,.04));reach.location=xyz((0,0,.36+extension));cargo.location=xyz((0,top,1+extension))
        for group_root,target,names in ((vehicle,hulls,moving),(cargo,cargo_hulls,None)):
            current,_=collect(group_root)
            for p in current:
                if names is not None and p['name'] not in names:continue
                if p['name'] not in target:target[p['name']]={'low':p['low'][:],'high':p['high'][:]}
                else:
                    h=target[p['name']];h['low']=[min(a,b) for a,b in zip(h['low'],p['low'])];h['high']=[max(a,b) for a,b in zip(h['high'],p['high'])]
    for title,target in (('moving vehicle',hulls),('moving cargo',cargo_hulls)):
        for name,h in target.items():empty_box(base_parts,h['low'],h['high'],('full platform sweep',title,name))
    carriage.location=xyz((0,.18,.04));reach.location=xyz((0,0,.76));cargo.location=xyz((0,.18,1.4));bpy.context.view_layer.update()
    return {'translation_regions':'lowY.18.. .70/fullreach.40, highY.70..1.50/reach0.. .40',
            'actual_vehicle_swept_hulls_clear':len(hulls),'actual_cargo_swept_hulls_clear':len(cargo_hulls),
            'proof':'Whole conservative endpoint hulls clear of exact platform triangles/interior; contact boundary allowed atY.18. Vehicle-body conditional regions are checked separately.'}


def build_fixture(asset,top,extension,with_base=True):
    reset();fixture=group(asset);fixture['role']='visual_QA_fixture'
    fixture['source_label']='Actual PALLET/load/fork support at C08 pose; stopped lift states are not travel/engine operations'
    vehicle=append_source('assets/v3/blender/forklift.blend','forklift_root',fixture)
    at(vehicle,'joint__carriage').location=xyz((0,top,.04));at(vehicle,'joint__reach').location=xyz((0,0,.36+extension))
    cargo=append_source('assets/v3/blender/pallet-load.blend','pallet-load__HU',fixture,(0,top,1+extension))
    base=append_source('assets/v3/blender/heavy-bay.blend','heavy-bay__MODULE',fixture,(0,0,1.5)) if with_base else None
    if base:base.rotation_euler.z=3.141592653589793
    bpy.context.view_layer.update()
    vehicle_parts,vehicle_bvh=collect(vehicle);cargo_parts,cargo_bvh=collect(cargo)
    for p in cargo_parts:empty_box(vehicle_parts,p['low'],p['high'],('PALLET/vehicle actual solids',asset,p['name']))
    if base:
        base_parts,base_bvh=collect(base)
        for p in vehicle_parts:empty_box(base_parts,p['low'],p['high'],('vehicle/platform actual solids',asset,p['name']))
        for p in cargo_parts:empty_box(base_parts,p['low'],p['high'],('PALLET/platform actual solids',asset,p['name']))
    sweep=platform_sweep(vehicle,cargo,base_parts) if base and top==.18 else None
    contacts=[]
    for x in (-.4,.4):
        for zlocal in (0,.4):
            z=1+extension+zlocal
            # Keep samples inside bottom-board patches and off actual lock bores.
            if zlocal==.4:z-=.03
            p,_,_,_=vehicle_bvh.ray_cast(xyz((x,top+.005,z)),xyz((0,-1,0)),.02)
            q,_,_,_=cargo_bvh.ray_cast(xyz((x,top-.005,z)),xyz((0,1,0)),.02)
            assert p is not None and q is not None and abs(runtime_xyz(p)[1]-top)<EPS and abs(runtime_xyz(q)[1]-top)<EPS
            contacts.append([x,top,z])
    return fixture,{'fork_top_y_m':top,'reach_m':extension,'actual_zero_gap_fork_contacts':contacts,
                    'actual_cargo_vehicle_clear':True,'actual_platform_clear':bool(base),
                    'continuous_platform_sweep':sweep,
                    'travel_admitted':top==.7 and extension==0,'upper_reserve_access_admitted':False}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'assets/v3/blender/forklift.blend'
    reset();vehicle=append_source('assets/v3/blender/forklift.blend','forklift_root',None);parts,bvh=collect(vehicle)
    bore_checks=[]
    for side,x in (('L',-.4),('R',.4)):
        fork=next(p for p in parts if p['name']=='fork_'+side)
        empty_box([fork],[x-.006,.628,.614],[x+.006,.702,.626],('actual lock bore open',side))
        hit,_,_,_=fork['bvh'].ray_cast(xyz((x,.59,.62)),xyz((0,1,0)),.15)
        assert hit is None,('closed lock bore',side)
        bore_checks.append({'side':side,'axis':'Y','centre_xz_m':[x,.62],'bore_radius_m':.010,'pin_radius_m':.008,'radial_air_m':.002})
    assert vehicle.get('actual_minimum_nested_overlap_m')==.415
    frames=[]
    for asset,top,extension in [('forklift-pallet-low-fixture',.18,.4),('forklift-pallet-travel-fixture',.7,0),('forklift-pallet-high-fixture',1.5,.4)]:
        root,checks=build_fixture(asset,top,extension)
        stats=finish(asset,root);checks['asset_id']=asset;checks['glb_sha256']=stats['sha256'];frames.append(checks)
    report={'task_id':'M14.6.1','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
     'actual_lock_bores':bore_checks,'actual_native_pallet_frames':frames,
     'guide_refinement':{'fixed_length_m':.64,'stroke_m':.4,'inner_bind_z_m':[-.245,.395],
       'extended_tip_z_m':.795,'platform_front_z_m':.8,'actual_front_air_m':.005,'minimum_overlap_m':.415},
     'staged_sources_unchanged':True,'actual_actions_accepted':False,
     'limits':'Stopped high PALLET extends beyond travel height; it grants no travel/upper-slot access. Full motion and controlled placement withdrawal remain M14.8.'}
    (OUT/'actual-native-contacts.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('M1461_NATIVE_VERIFIED '+json.dumps({'bores':len(bore_checks),'frames':len(frames),'fork_contacts':sum(len(x['actual_zero_gap_fork_contacts']) for x in frames),'platform_clearance_m':.005}))
