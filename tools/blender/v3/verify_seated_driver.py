"""P07 native seated driver against actual final forklift, sources read-only."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, reset, runtime_xyz, xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source
from verify_loaded_forklift import add_hull

OUT=ROOT/'assets/v3/iterations/worker-base/P07';EPS=2e-6


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    paths=['assets/v3/blender/forklift.blend','assets/v3/blender/worker-base.blend','frontend/public/models/v3/worker-base.glb','frontend/public/data/v3/seated-driver-pose.json']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    pose=json.loads((ROOT/paths[-1]).read_text())['driver'];reset()
    vehicle=append_source(paths[0],'forklift_root',None)
    worker=append_source(paths[1],'worker_base_root',vehicle,pose['worker_root_translation'])
    conversion=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
    for name,(a,b,c) in pose['jointEulerXYZ'].items():
        # Three intrinsicXYZ is Rx@Ry@Rz; map that matrix into Blender axes.
        m=Matrix.Rotation(a,3,'X')@Matrix.Rotation(b,3,'Y')@Matrix.Rotation(c,3,'Z')
        obj=bpy.data.objects[name];obj.rotation_mode='QUATERNION';obj.rotation_quaternion=(conversion@m@conversion.transposed()).to_quaternion()
    # P02 runtime hides the complete original picker-ink batch and supplies
    # the accepted driver05extrusion. Its old source text outline is not a
    # closed collision solid. Keep all body/badge-base geometry unchanged;
    # driver-specific ink containment is checked in actual runtime instead.
    retired_ink=[]
    for obj in list(worker.children_recursive):
        if obj.name.startswith('role_badge_') and obj.name!='role_badge_base':
            retired_ink.append(obj.name);bpy.data.objects.remove(obj,do_unlink=True)
    bpy.context.view_layer.update();wp,wbvh=collect(worker)
    # Vehicle source collection includes the appended actor as a child; remove
    # its mesh names from the vehicle collision target before paired checks.
    names={p['name'] for p in wp};vp,vbvh=collect(vehicle);vp=[p for p in vp if p['name'] not in names]
    worker_bounds={'min':[min(p['low'][i] for p in wp) for i in range(3)],'max':[max(p['high'][i] for p in wp) for i in range(3)]}
    assert all(worker_bounds['min'][i]>=[-.6,0,-1.5][i]-EPS and worker_bounds['max'][i]<=[.6,2.1,1.5][i]+EPS for i in range(3))
    contacts=[]
    for label,x,y,z,part in [('seat',0,.84,-.70,'pelvis_cloth'),('sole_L',-.115,.53,-.395,'boot_L'),('sole_R',.115,.53,-.395,'boot_R')]:
        p=next(p for p in wp if p['name']==part)
        a,_,_,_=p['bvh'].ray_cast(xyz((x,y-.005,z)),xyz((0,1,0)),.02)
        # Exact native fixed surfaces, not the actor included in union BVH.
        hits=[]
        for target in vp:
            hit,normal,_,_=target['bvh'].ray_cast(xyz((x,y+.005,z)),xyz((0,-1,0)),.02)
            if hit is not None:hits.append((hit,target['name']))
        assert a is not None and abs(runtime_xyz(a)[1]-y)<EPS
        assert any(abs(runtime_xyz(hit)[1]-y)<EPS for hit,_ in hits),(label,hits)
        contacts.append({'contact':label,'point':[x,y,z],'actual_vehicle_parts':[name for hit,name in hits if abs(runtime_xyz(hit)[1]-y)<EPS]})
    hands=[]
    for side in ('L','R'):
        point=runtime_xyz(bpy.data.objects['anchor_hand_grip_'+side].matrix_world.translation)
        grip=runtime_xyz(bpy.data.objects['anchor_steering_grip_'+side].matrix_world.translation)
        error=sum((a-b)**2 for a,b in zip(point,grip))**.5;assert error<2e-5
        hands.append({'side':side,'actual_hand_anchor':point,'actual_steering_grip_anchor':grip,'error_m':error})
    intersections=[];pairs=0
    for w in wp:
        for v in vp:
            if any(w['high'][i]<=v['low'][i]+EPS or w['low'][i]>=v['high'][i]-EPS for i in range(3)):continue
            pairs+=1;overlap=w['bvh'].overlap(v['bvh'])
            if not overlap:continue
            allowed=(w['name']=='pelvis_cloth' and v['name'].startswith('seat_cushion')) or (w['name'].startswith('boot_') and v['name']=='driver_floorboard')
            assert allowed,('unexpected actual worker/vehicle triangle intersection',w['name'],v['name'],len(overlap))
            for p,target in [(w,v),(v,w)]:
                for point in p['samples']:
                    hit,n,_,distance=target['bvh'].find_nearest(point)
                    assert n.dot(point-hit)>=-EPS or distance<EPS,('solid penetration at allowed surface contact',p['name'],target['name'])
            intersections.append([w['name'],v['name'],'boundary contact only'])
    helmet=max(p['high'][1] for p in wp if p['name'].startswith('helmet_'))
    roof=next(p['low'][1] for p in vp if p['name']=='roof_guard')
    assert roof-helmet>=pose['minimum_helmet_roof_gap_m']
    # Whole rectangular lift/reach parameter region versus the fixed seated
    # worker. This is clearance only, never low/retracted operational admission.
    carriage=bpy.data.objects['joint__carriage'];reach=bpy.data.objects['joint__reach']
    moving={o.name for o in carriage.children_recursive if o.type=='MESH'};hulls={}
    for top,extension in ((.18,0),(.18,.4),(1.5,0),(1.5,.4)):
        carriage.location=xyz((0,top,.04));reach.location=xyz((0,0,.36+extension))
        parts,_=collect(vehicle);add_hull(hulls,[p for p in parts if p['name'] in moving])
    for name,h in hulls.items():empty_box(wp,h['low'],h['high'],('complete lift/reach swept hull versus actual seated worker',name))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in hashes.items())
    OUT.mkdir(parents=True,exist_ok=True)
    report={'task_id':'P07','source_hashes':hashes,'native_worker_closed_outward_parts':len(wp),'worker_bounds_vehicle_m':worker_bounds,'inside_unchanged_vehicle_component_bounds':True,'retired_picker_ink_replaced_by_P02_runtime_driver_badge':retired_ink,'actual_zero_gap_support_contacts':contacts,
            'actual_hand_control_anchors':hands,'actual_worker_vehicle_overlap_pairs_checked':pairs,'allowed_boundary_contacts':intersections,
            'helmet_top_y_m':helmet,'actual_guard_bottom_y_m':roof,'actual_helmet_guard_gap_m':roof-helmet,
            'whole_lift_reach_hulls_clear_of_worker':len(hulls),'worker_geometry_scale_unchanged':True,'native_sources_unchanged':True,
            'scope':'Actual final vehicle/seated body/controls and whole lift/reach clearance. No headcount change, entry/climb, steering-wheel IK or warehouse scheduler execution.'}
    (OUT/'actual-native-driver-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P07_NATIVE_VERIFIED '+json.dumps({'worker_parts':len(wp),'support_contacts':3,'hand_anchor_contacts':2,'helmet_gap_m':roof-helmet,'whole_moving_hulls':len(hulls)}))
