"""M14.6.3 actual six native HU assemblies and bounded continuous interfaces.

This proves geometry/contact at declared poses, not operator/traffic admission.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, finish, group, reset, runtime_xyz, xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source
from build_long_rack import build as rack_model

OUT=ROOT/'assets/v3/iterations/forklift/M14.6.3';EPS=2e-6
SOURCES={'HEAVY_BOX':('heavy-box','heavy-box'),'PALLET_LOAD':('pallet-load','pallet-load__HU'),
         'IBC':('ibc','ibc__HU'),'LONG_BUNDLE':('long-bundle','long-bundle'),
         'DRUM':('drum','drum'),'FRAGILE_CRATE':('fragile-crate','fragile-crate')}


def named(root,name):return next(o for o in root.children_recursive if o.name==name)


def source(asset,name,parent,offset=(0,0,0)):
    return append_source('assets/v3/blender/'+asset+'.blend',name,parent,offset)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True);reset()


def add_hull(target,parts):
    for p in parts:
        if p['name'] not in target:target[p['name']]={'low':p['low'][:],'high':p['high'][:]}
        else:
            h=target[p['name']];h['low']=[min(a,b) for a,b in zip(h['low'],p['low'])];h['high']=[max(a,b) for a,b in zip(h['high'],p['high'])]


def support_contacts(vehicle_bvh,cargo_bvh,xs,y,z0,z1):
    contacts=[]
    for x in xs:
        found=[]
        for i in range(1,40):
            z=z0+(z1-z0)*i/40
            a,an,_,_=vehicle_bvh.ray_cast(xyz((x,y+.004,z)),xyz((0,-1,0)),.02)
            b,bn,_,_=cargo_bvh.ray_cast(xyz((x,y-.004,z)),xyz((0,1,0)),.02)
            if a is not None and b is not None and abs(runtime_xyz(a)[1]-y)<EPS and abs(runtime_xyz(b)[1]-y)<EPS and an.dot(xyz((0,1,0)))>.99 and bn.dot(xyz((0,-1,0)))>.99:
                found.append([x,y,z])
        assert len(found)>=2,('missing actual fork support',x,y,z0,z1)
        assert found[-1][2]-found[0][2]>.03
        contacts.extend([found[0],found[-1]])
    return contacts


def loaded_case(load):
    aid,cargo_root=SOURCES[load['archetype_id']];fresh()
    fixture=group('forklift-loaded-'+aid);fixture['role']='visual_QA_fixture'
    fixture['source_label']='One native C08 cargo/vehicle assembly; pose geometry, no source operation or scheduler execution'
    vehicle=source('forklift','forklift_root',fixture);cargo=source(aid,cargo_root,fixture)
    islong=aid=='long-bundle';attachment=source('long-cradle','long-cradle',fixture) if islong else None
    rig=source('long-restraint-rig','long-restraint-rig',fixture) if islong else None
    carriage=named(vehicle,'joint__carriage');reach=named(vehicle,'joint__reach')
    xs=load['fork_centres_x_m'];toptravel=load['fork_top_travel_y_m']
    centre=(load['cargo_bounds_local_m']['min'][2]+load['cargo_bounds_local_m']['max'][2])/2
    miny=.20 if islong else .18
    def pose(top,extension):
        carriage.location=xyz((0,top,.04));reach.location=xyz((0,0,.36+extension))
        for side,x in zip(('L','R'),xs):named(vehicle,'joint__fork_'+side).location=xyz((x,0,0))
        cargo.location=xyz((0,top+.05 if islong else top,centre+extension))
        for obj in (attachment,rig):
            if obj:obj.location=xyz((0,top-.1,1+extension))
        bpy.context.view_layer.update()
    frames=[]
    for label,top,extension in [('travel',toptravel,0),('stopped_low',miny,.4),('stopped_high',1.5,.4)]:
        pose(top,extension);vp,vbvh=collect(vehicle);cp,cbvh=collect(cargo)
        for p in cp:empty_box(vp,p['low'],p['high'],(aid,label,'cargo versus actual vehicle',p['name']))
        if islong:
            ap,abvh=collect(attachment);rp,_=collect(rig)
            moving=[p for p in vp if not p['name'].startswith('fork_')]
            # Test each vehicle hull against actual attachment triangles, so
            # machined bridge relief is respected rather than filling its void.
            for p in moving:empty_box(ap+rp,p['low'],p['high'],(aid,label,'actual attachment versus nonfork vehicle hull',p['name']))
            contacts=support_contacts(vbvh,abvh,xs,top,1+extension-.25,1+extension+.25)
            # The source bores/pins are real32-sided meshes. Verify every pin
            # vertex within fork Y lies in actual free bore space at this pose.
            pin_vertices=0
            for p in ap:
                if not p['name'].startswith('positive_lock_pin_'):continue
                for sample in p['samples']:
                    point=runtime_xyz(sample)
                    if top-.07+EPS<point[1]<top-EPS:
                        v=xyz(point);near,normal,_,_=vbvh.find_nearest(v)
                        assert normal.dot(v-near)>=-EPS,('actual pin inside fork material',label,p['name'],point)
                        pin_vertices+=1
            assert pin_vertices>0
        else:
            contacts=support_contacts(vbvh,cbvh,xs,top,load['cargo_bounds_local_m']['min'][2]+extension,load['cargo_bounds_local_m']['max'][2]+extension)
            pin_vertices=0
        frames.append({'pose':label,'fork_top_y_m':top,'extension_m':extension,'actual_zero_gap_contacts':contacts,'pin_vertices_inside_actual_free_bores':pin_vertices,'travel_profile':label=='travel'})
    # Two conditional convex translation regions; do not overfill the forbidden
    # low/retracted corner with a single broad swept box.
    pose(toptravel,0);vp,_=collect(vehicle)
    if islong:
        ap=collect(attachment)[0]+collect(rig)[0]
        for p in vp:
            if p['name'].startswith('reach_outer_'):
                low=p['low'][:];low[2]-=.4
                empty_box(ap,low,p['high'],('whole relative guide/cradle reach stroke',p['name']))
    moving_names={o.name for o in carriage.children_recursive if o.type=='MESH'}
    fixed=[p for p in vp if p['name'] not in moving_names]
    sweeps=[]
    for label,corners in [('extended_vertical',[(miny,.4),(1.5,.4)]),('high_lift_and_reach',[(toptravel,0),(toptravel,.4),(1.5,0),(1.5,.4)])]:
        hulls={}
        for top,extension in corners:
            pose(top,extension)
            for obj in (cargo,attachment,rig):
                if obj:add_hull(hulls,collect(obj)[0])
        for name,h in hulls.items():empty_box(fixed,h['low'],h['high'],(aid,label,'whole actual load swept hull versus fixed vehicle',name))
        sweeps.append({'region':label,'whole_actual_part_hulls_clear':len(hulls)})
    pose(toptravel,0)
    # C08 travel component containment, including separate closed upper rig.
    allparts=collect(vehicle)[0]+collect(cargo)[0]
    for obj in (attachment,rig):
        if obj:allparts+=collect(obj)[0]
    boxes=load['component_bounds_local_m']
    for p in allparts:
        for v in p['verts']:assert any(all(b['min'][i]-EPS<=v[i]<=b['max'][i]+EPS for i in range(3)) for b in boxes),(aid,'outside unchanged C08 component union',p['name'],v)
    stat=finish('forklift-loaded-'+aid,fixture)
    return {'archetype_id':load['archetype_id'],'asset_id':'forklift-loaded-'+aid,'HU_instances':1,'gross_plus_attachment_kg':load['total_lifted_mass_kg'],
            'native_scale':1,'frames':frames,'continuous_fixed_body_sweeps':sweeps,'actual_closed_component_containment':True,'glb_sha256':stat['sha256']}


def removable_rig_and_rack():
    fresh();fixture=group('long-rack-release-fixture');fixture['role']='visual_QA_fixture'
    fixture['source_label']='Actual lowered attachment exit; upper accessory removed before withdrawal; no operational/personnel admission'
    rack=rack_model();rack.parent=fixture
    # Remove restraints200mm above the final rack plane. At the final plane,
    # outward keeper extraction would hit the adjacent rack arms.
    cargo=source('long-bundle','long-bundle',fixture,(0,.45,.225))
    cradle=source('long-cradle','long-cradle',fixture,(0,.30,.225))
    rig=source('long-restraint-rig','long-restraint-rig',fixture,(0,.30,.225))
    for obj in (cradle,rig):obj.rotation_euler.z=math.pi
    cp,_=collect(cargo);bp,_=collect(cradle);rackparts,_=collect(rack)
    keepers=[o for o in rig.children if o.name.startswith('joint__restraint_keeper_')]
    postparts=[p for p in collect(rig)[0] if p['name'].startswith('upright_')]
    # Actual machined horizontal bores: rays on the axis and a3.5mm ring
    # clear both source frame and post.24-sidedR4 leaves>=.966mm radial air
    # around theR3 shaft throughout translation; heads start outside the rail.
    bore_rays=0
    for joint in keepers:
        centre=runtime_xyz(joint.matrix_world.translation)
        for parts in (bp,postparts):
            for p in parts:
                if not (p['low'][0]-.001<=centre[0]<=p['high'][0]+.001 and p['low'][2]-.005<=centre[2]<=p['high'][2]+.005):continue
                for i in range(9):
                    a=0 if i==0 else .0035*math.cos((i-1)*math.tau/8);b=0 if i==0 else .0035*math.sin((i-1)*math.tau/8)
                    hit,_,_,_=p['bvh'].ray_cast(xyz((centre[0]-.15,centre[1]+a,centre[2]+b)),xyz((1,0,0)),.30)
                    assert hit is None,('actual upper keeper bore obstructed',p['name'],i)
                    bore_rays+=1
        sign=-1 if '_L_' in joint.name else 1;joint.location+=xyz((sign*.35,0,0))
    bpy.context.view_layer.update()
    # Free pins move toward the rack front while still below the HU. They are
    # removed separately before lifting the U clamps, so no pin crosses dunnage.
    pin_hulls={}
    for joint in keepers:add_hull(pin_hulls,collect(joint)[0])
    for joint in keepers:joint.location+=xyz((0,0,-.75))
    for joint in keepers:add_hull(pin_hulls,collect(joint)[0])
    for name,h in pin_hulls.items():
        for target,title in [(cp,'actual HU'),(bp,'actual base'),(rackparts,'actual rack'),(postparts,'actual post')]:empty_box(target,h['low'],h['high'],('whole free keeper front-removal sweep',title,name))
    for joint in keepers:
        for o in list(joint.children_recursive)+[joint]:bpy.data.objects.remove(o,do_unlink=True)
    rigparts,_=collect(rig);vertical={}
    add_hull(vertical,rigparts);rig.location+=xyz((0,.58,0));add_hull(vertical,collect(rig)[0])
    for name,h in vertical.items():
        for target,title in [(cp,'unchanged actual HU'),(bp,'actual machined base sockets'),(rackparts,'actual two-level rack')]:
            empty_box(target,h['low'],h['high'],('whole vertical removal sweep',title,name))
    # Detached rig is outside this engineering view, retained in its separate
    # native source asset. It cannot remain on an empty-cradle transit profile.
    for o in list(rig.children_recursive)+[rig]:bpy.data.objects.remove(o,do_unlink=True)
    cargo.location=xyz((0,.25,.225));cradle.location=xyz((0,.08,.225));bpy.context.view_layer.update();cp,_=collect(cargo)
    vehicle=source('forklift','forklift_root',fixture,(0,0,1.625));vehicle.rotation_euler.z=math.pi
    named(vehicle,'joint__carriage').location=xyz((0,.18,.04));named(vehicle,'joint__reach').location=xyz((0,0,.76))
    bpy.context.view_layer.update();hulls={}
    add_hull(hulls,collect(cradle)[0])
    for p in collect(vehicle)[0]:
        if p['name'] not in ('fork_L','fork_R'):add_hull(hulls,[p]);continue
        # A single box would fill the actual L-fork's empty upper corner.
        # Prove every native vertex belongs to blade or heel, then sweep the
        # two whole conservative solid covers independently.
        assert all(v[1]<=.18+EPS or v[2]>=.825-EPS for v in p['verts'])
        blade={'name':p['name']+'_blade','low':p['low'][:],'high':p['high'][:]};blade['high'][1]=.18
        heel={'name':p['name']+'_heel','low':p['low'][:],'high':p['high'][:]};heel['low'][2]=.825
        add_hull(hulls,[blade,heel])
    for name,h in hulls.items():
        high=h['high'][:];high[2]+=2
        for target,title in [(rackparts,'actual rack'),(cp,'stored actual HU')]:empty_box(target,h['low'],high,('complete lowered reverse exit',title,name))
    stats=finish('long-rack-release-fixture',fixture)
    return {'restraint_removal_HU_bottom_y_m':.45,'upper_rig_vertical_removal_m':.58,'keeper_outward_retraction_m':.35,
            'keeper_then_front_translation_m':.75,'actual_keeper_bore_rays':bore_rays,'whole_free_keeper_sweep_hulls_clear':len(pin_hulls),'whole_rig_removal_hulls_clear':len(vertical),
            'HU_top_y_m':.97,'removed_post_bottom_y_m':.99,'top_air_m':.02,
            'whole_vehicle_and_cradle_withdrawal_hulls_clear':len(hulls),'rack_Z_withdrawal_m':[0,2],
            'lowered_pad_top_y_m':.23,'stored_HU_bottom_y_m':.25,'release_gap_m':.02,
            'actual_fixture_sha256':stats['sha256'],'limits':'Geometry only. Upper-rig keeper extraction and manual removal/stow must be explicit stopped actions; no invisible removal or empty transit with rig installed is admitted.'}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    OUT.mkdir(parents=True,exist_ok=True)
    contract=ROOT/'docs/v3/contract-proposals/vehicle-handling-v3.json'
    data=json.loads(contract.read_text(encoding='utf-8'));loads=[loaded_case(load) for load in data['loads']]
    removal=removable_rig_and_rack()
    report={'task_id':'M14.6.3','C08_sha256':hashlib.sha256(contract.read_bytes()).hexdigest(),'native_load_cases':loads,'actual_LONG_removal_and_rack_exit':removal,
            'operational_admission':False,'limits':'Actual geometry contacts/closed travel containment and bounded continuous interface sweeps. Full absolute-clock action, exclusive operator/vehicle/traffic reservations and upper-rig install/stow remain action/integration gates. No upper reserve access.'}
    (OUT/'actual-loaded-native-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('M1463_NATIVE_VERIFIED '+json.dumps({'cargo_families':len(loads),'native_frames':sum(len(x['frames']) for x in loads),'rack_exit_hulls':removal['whole_vehicle_and_cradle_withdrawal_hulls_clear']}))
