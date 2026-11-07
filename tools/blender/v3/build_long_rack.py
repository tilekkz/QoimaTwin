"""M04 cantilever rack and explicitly labelled C08 transfer-interface gauge.

Keep canonical C04/C08/C09 data read-only. The gauge verifies the rack's relief;
it is not a complete attachment/lock/action or an additional stock object.
"""
import hashlib
import json
from pathlib import Path

import bpy

from v3_common import ROOT, anchor, box, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box
from build_forklift import _rect_tube_z

EPS=2e-6
OUT=ROOT/'assets/v3/iterations/long-rack/M04-01'


def block(name,lo,hi,mat,parent,bevel=.005):
    return box(name,[(a+b)/2 for a,b in zip(lo,hi)],[b-a for a,b in zip(lo,hi)],mat,parent,bevel)


def build():
    root=group('long-rack');root['reference_id']='M04_TRANSFER_REF'
    root['role']='storage_module_template';root['storage_type']='LONG'
    root['level_support_planes_m']=[.25,1.30];root['upper_level_reserve_only']=True
    root['operational_admission']=False
    root['surface_design']='Three separate arms at each level; tie beams behind cargo; front transfer opening retained'
    charcoal=material('V3_LONG_RACK_charcoal','#293D46')
    teal=material('V3_LONG_RACK_mounts','#2E7376')
    tan=material('V3_LONG_RACK_arms','#C99A60')
    for i,x in enumerate((-1.6,0,1.6)):
        block(f'foot_{i}',[x-.09,0,-.65],[x+.09,.12,.65],charcoal,root,.006)
        block(f'post_{i}',[x-.08,0,-.63],[x+.08,2.2,-.47],charcoal,root,.009)
        for level,y in enumerate((.25,1.30),1):
            block(f'collar_L{level}_{i}',[x-.11,y-.15,-.64],[x+.11,y+.02,-.43],teal,root,.007)
            block(f'arm_L{level}_{i}',[x-.08,y-.12,-.55],[x+.08,y,.54],tan,root,.005)
    for level,y in enumerate((.25,1.30),1):
        block(f'rear_tie_L{level}',[-2.4,y-.12,-.63],[2.4,y,-.47],tan,root,.006)
        anchor(f'anchor_bin_L{level}',(0,y,.15),root,'usable_bottom_centre_not_HU_origin')
        for i,x in enumerate((-1.6,0,1.6)):
            anchor(f'anchor_support_L{level}_{i}',(x,y,.225),root,'canonical_LONG_support_witness')
    anchor('anchor_floor_origin',(0,0,0),root,'module_floor_centre')
    return root


def transfer_gauge(parent):
    root=group('C08_cradle_interface_gauge',parent,(0,.08,.225))
    root.rotation_euler.z=3.141592653589793
    root['role']='attachment_interface_clearance_gauge_not_complete_asset'
    root['operational_admission']=False;root['actual_lock_and_strength_verified']=False
    teal=material('V3_LONG_GAUGE_frame','#2E7376')
    tan=material('V3_LONG_GAUGE_pad','#C99A60')
    dark=material('V3_LONG_GAUGE_pockets','#293D46')
    for side,x in (('L',-1.4),('R',1.4)):
        block('gauge_pad_rail_'+side,[x-.10,0,-.425],[x+.10,.13,.425],teal,root,.002)
        block('gauge_pad_top_'+side,[x-.10,.13,-.425],[x+.10,.15,.425],tan,root,.001)
    # Operator-side bridge (vehicle-Z), open toward tips. With the required
    # yawPI at the rack it lies ahead of the arm tips in rack+Z, not behind.
    block('gauge_approach_bridge',[-1.6,.10,-.425],[1.6,.13,-.35],teal,root,.001)
    for side,x in (('L',-.4),('R',.4)):
        obj=_rect_tube_z('gauge_pocket_'+side,[x-.09,x+.09],[0,.12],[-.425,.425],.02,dark,root)
        obj['forklift_component_class']='transfer_gauge_only'
    return root


def verify_rack(root):
    parts,bvh=collect(root)
    low=[min(p['low'][i] for p in parts) for i in range(3)]
    high=[max(p['high'][i] for p in parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(low+high,[-2.4,0,-.65,2.4,2.2,.65]))<EPS
    assert len(parts)==20
    supports=[]
    for level,y in enumerate((.25,1.30),1):
        empty_box(parts,[-2.2,y,-.30],[2.2,y+.65,.60],('unchanged C04 usable',level))
        for x in (-1.6,0,1.6):
            for z in (-.08,.225,.52):
                p,normal,_,_=bvh.ray_cast(xyz((x,y+.01,z)),xyz((0,-1,0)),.03)
                assert p is not None and abs(runtime_xyz(p)[1]-y)<EPS,(level,x,z,runtime_xyz(p) if p else None)
                assert normal.dot(xyz((0,1,0)))>.999
                supports.append([x,y,z])
    # Positive interior witnesses prove the load path, not merely parent names.
    byname={p['name']:p for p in parts};contacts=[]
    def contact(a,b,point):
        margins=[]
        for name in (a,b):
            p=xyz(point);near,normal,_,dist=byname[name]['bvh'].find_nearest(p)
            assert normal.dot(p-near)<0 and dist>1e-5,(a,b,point,dist)
            margins.append(dist)
        contacts.append({'parts':[a,b],'point':point,'interior_margins_m':margins})
    for i,x in enumerate((-1.6,0,1.6)):
        contact(f'foot_{i}',f'post_{i}',[x,.06,-.55])
        for level,y in enumerate((.25,1.30),1):
            contact(f'post_{i}',f'arm_L{level}_{i}',[x,y-.06,-.51])
            contact(f'post_{i}',f'collar_L{level}_{i}',[x,y-.06,-.55])
            contact(f'arm_L{level}_{i}',f'rear_tie_L{level}',[x,y-.06,-.51])
    return {'bounds_runtime':{'min':low,'max':high},'closed_positive_outward_parts':len(parts),
            'actual_support_rays':supports,'actual_interior_connections':contacts,
            'C04_usable_clear_per_level':[4.4,.65,.9],'three_arm_support_centres_x_m':[-1.6,0,1.6],
            'upper_LONG_reserve_retrieval_remains_blocked':True}


def verify_transfer(rack,gauge):
    rackparts,_=collect(rack)
    bpy.context.view_layer.update();gaugeparts,_=collect(gauge)
    assert len(gaugeparts)==7
    # Every part's swept hull over rack+Z0..2m is tested against exact rack
    # triangles/interior. This covers the complete lowered withdrawal path.
    for p in gaugeparts:
        high=p['high'][:];high[2]+=2.0
        empty_box(rackparts,p['low'],high,('full withdrawal sweep',p['name']))
    return {'full_lowered_withdrawal_axis':'rack+Z','full_lowered_withdrawal_m':[0,2],
            'cradle_gauge_origin_rack_m':[0,.08,.225],'pad_top_y_m':.23,'rack_support_plane_y_m':.25,
            'disengagement_gap_m':.02,'pad_vs_arm_lateral_air_m':.02,'pad_vs_foot_lateral_air_m':.01,
            'bridge_vs_arm_tip_air_m':.035,'swept_solid_hulls_clear_of_actual_rack':len(gaugeparts),
            'pocket_inner_W_H_m':[.14,.08],'gauge_own_bounds_W_H_D_m':[3.2,.15,.85],
            'gauge_scope':'Exact C08 dimensions and U-interface only; full cradle pins/locks/strength/actions remain M14 attachment gate.'}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    OUT.mkdir(parents=True,exist_ok=True)
    reset();rack=build();checks=verify_rack(rack);stats=finish('long-rack',rack)
    checks['glb_sha256']=stats['sha256'];checks['triangles']=stats['triangles']
    reset();fixture=group('long-transfer-interface-fixture')
    fixture['role']='visual_QA_fixture';fixture['source_label']='C04/C08 geometric interface gauge, not complete attachment or stock'
    rack=build();rack.parent=fixture;gauge=transfer_gauge(fixture)
    checks['transfer_interface']=verify_transfer(rack,gauge)
    gauge_stats=finish('long-transfer-interface-fixture',fixture)
    checks['fixture_sha256']=gauge_stats['sha256']
    checks['reference_id']='M04_TRANSFER_REF';checks['operational_admission']=False
    (OUT/'mesh-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    (ROOT/'assets/v3/specs/long-rack.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('M04_SOURCE_VERIFIED '+json.dumps({'parts':checks['closed_positive_outward_parts'],'support_rays':len(checks['actual_support_rays']),
          'connections':len(checks['actual_interior_connections']),'continuous_transfer_hulls':7,'triangles':stats['triangles']}))
