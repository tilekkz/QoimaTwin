"""M14.6.2 real C08 U cradle/vertical locks and separate hinged restraints.

Metres/Y-up; C08/C02 source contracts and accepted vehicle/HU assets stay read-only.
The separate upper accessory fits the unchanged CLOSED loaded component union.
Open restraints are stopped handling, never a transit envelope.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, anchor, box, cylinder, finish, group, material, pivot, reset, runtime_xyz, xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_forklift import _rect_tube_z
from build_long_rack import block
from build_sealed_parcel import append_source
from build_standard_carton import collect, empty_box

OUT=ROOT/'assets/v3/iterations/long-cradle/M14.6.2'
EPS=2e-6
CONTRACT='docs/v3/contract-proposals/vehicle-handling-v3.json'
CONTRACT_SHA='22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4'


def difference(obj,cutter):
    bpy.context.view_layer.update()
    mod=obj.modifiers.new('Real machined bore','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)


def relief(obj,width=.0006):
    mod=obj.modifiers.new('Machined edge relief','BEVEL');mod.width=width;mod.segments=1;mod.harden_normals=True
    obj.modifiers.new('Weighted metal faces','WEIGHTED_NORMAL').keep_sharp=True


def stepped_pin(name,x,z,mat,parent):
    # A single closed turned pin; no coincident cap/shaft faces.
    rings=[(.005,.008),(.125,.008),(.125,.016),(.150,.016)]
    points=[xyz((x+r*math.cos(i*math.tau/32),y,z+r*math.sin(i*math.tau/32))) for y,r in rings for i in range(32)]
    faces=[tuple(reversed(range(32))),tuple(range(96,128))]
    for j in range(3):
        for i in range(32):n=(i+1)%32;faces.append((j*32+i,j*32+n,(j+1)*32+n,(j+1)*32+i))
    mesh=bpy.data.meshes.new(name+'_turned_solid');mesh.from_pydata(points,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
    relief(obj,.00015);return obj


def base():
    root=group('long-cradle');root['role']='forklift_attachment_base'
    root['reference_id']='M14_LONG_LOCK_REF';root['preserve_articulation']=True
    root['base_dimensions_xyz_m']=[3.2,.15,.85];root['attachment_mass_total_with_upper_rig_kg']=40
    root['upper_restraint_asset']='long-restraint-rig';root['operational_admission']=False
    root['closed_pins_required_for_transit']=True
    teal=material('V3_C08_teal','#2E7376');tan=material('V3_C08_pad','#C99A60')
    steel=material('V3_C08_pockets','#293D46');yellow=material('V3_C08_locks','#F4C542')
    for side,x in [('L',-1.4),('R',1.4)]:
        rail=block('pad_rail_'+side,[x-.1,0,-.425],[x+.1,.13,.425],teal,root,0)
        skin=block('pad_surface_'+side,[x-.1,.13,-.425],[x+.1,.15,.425],tan,root,0)
        for z in (-.28,.28):
            for target in (rail,skin):
                socket=block('temporary_removable_restraint_socket',[x-.032,.11,z-.0145],[x+.032,.151,z+.0145],steel,root,0)
                difference(target,socket)
                cut=cylinder('temporary_upper_rig_keeper_bore',(x,.12,z),.004,.25,steel,axis='X',vertices=24)
                difference(target,cut)
        # No socket-edge bevel that would reduce the exact clear fit.
        rail.modifiers.new('Weighted socket faces','WEIGHTED_NORMAL').keep_sharp=True
        skin.modifiers.new('Weighted pad faces','WEIGHTED_NORMAL').keep_sharp=True
        anchor('anchor_pad_'+side,(x,.15,0),root,'actual_HU_support')
    # Substantial rear crossbeam gives real frame depth while its lower edge
    # clears rack feet by10mm at the lowered release height. Machined windows
    # retain each complete fork tunnel; the top layer overlaps its roof1mm.
    bridge=block('operator_side_bridge',[-1.6,.05,-.425],[1.6,.13,-.35],teal,root,0)
    for x in (-.53,.53):
        # Actual side-guide relief, preserving a substantial visible beam.
        # Retraction brings guide tips under its rear edge;5mm lateral and
        # vertical air must survive the entire high reach stroke.
        notch=block('temporary_nested_guide_relief',[x-.035,.049,-.426],[x+.035,.09,-.37],steel,root,0)
        difference(bridge,notch)
    pockets=[]
    for side,x in [('L',-.4),('R',.4)]:
        obj=_rect_tube_z('real_fork_pocket_'+side,[x-.09,x+.09],[0,.12],[-.425,.425],.02,steel,root)
        for mod in list(obj.modifiers):obj.modifiers.remove(mod)
        window=block('temporary_pocket_window',[x-.091,0,-.426],[x+.091,.119,-.349],steel,root,0)
        difference(bridge,window)
        ear=block('lock_ear_'+side,[x-.022,.125,-.402],[x+.022,.15,-.358],teal,root,0)
        # Shaft hole passes through BOTH pocket walls, bridge and ear.
        for target in (obj,ear,bridge):
            cut=cylinder('temporary_vertical_shaft_bore',(x,.08,-.38),.010,.20,steel,vertices=32)
            difference(target,cut)
            cut=cylinder('temporary_recessed_cap_counterbore',(x,.145,-.38),.017,.04,steel,vertices=32)
            difference(target,cut)
        # Preserve the entire contractual rectangular .14x.08 clear tunnel;
        # a bevel across its concave corners would intrude into that gauge.
        obj.modifiers.new('Weighted pocket faces','WEIGHTED_NORMAL').keep_sharp=True
        relief(ear)
        joint=pivot('joint__cradle_lock_'+side,(0,0,0),root,'Y')
        joint['translation_axis_runtime']='Y';joint['translation_delta_range_m']=[0,.11]
        joint['closed_y_m']=0;joint['open_y_m']=.11;joint['requires_stopped_handling']=True
        stepped_pin('positive_lock_pin_'+side,x,-.38,yellow,joint)
        anchor('anchor_fork_pocket_'+side,(x,.1,0),root,'fork_top_interface')
        anchor('anchor_lock_axis_'+side,(x,.1,-.38),root,'actual_vertical_pin_axis')
        pockets.append(obj)
    relief(bridge)
    anchor('anchor_bundle_support',(0,.15,0),root,'LONG_HU_bottom')
    return root


def restraints():
    root=group('long-restraint-rig');root['role']='separate_upper_LONG_restraint_accessory'
    root['reference_id']='M14_LONG_LOCK_REF';root['preserve_articulation']=True
    root['mass_included_in_C08_total_40kg']=True;root['operational_admission']=False
    root['closed_pressure_pad_bottom_m']=.592;root['closed_top_y_m']=.63
    root['open_state_requires_stop']=True;root['open_angle_x_deg']=-80
    root['removable_before_rack_withdrawal']=True
    root['empty_transit_requires_rig_in_stow_fixture']=True
    teal=material('V3_C08_restraint_teal','#2E7376');tan=material('V3_C08_pressure_pad','#C99A60')
    steel=material('V3_C08_hinge','#293D46')
    for side,x in [('L',-1.4),('R',1.4)]:
        for label,z in [('rear',-.28),('front',.28)]:
            post=block('upright_'+side+'_'+label,[x-.03,.11,z-.0125],[x+.03,.61,z+.0125],teal,root,0)
            cut=cylinder('temporary_post_keeper_bore',(x,.12,z),.004,.10,steel,axis='X',vertices=24)
            difference(post,cut);relief(post,.0004)
            keeper=pivot('joint__restraint_keeper_'+side+'_'+label,(x,.12,z),root,'X')
            sign=-1 if side=='L' else 1
            keeper['translation_axis_runtime']='X';keeper['translation_delta_range_m']=[-.35,0] if sign<0 else [0,.35]
            keeper['open_requires_stop']=True
            cylinder('keeper_shaft_'+side+'_'+label,(0,0,0),.003,.22,steel,keeper,axis='X',vertices=24)
            cylinder('keeper_head_'+side+'_'+label,(sign*.113,0,0),.006,.006,tan,keeper,axis='X',vertices=16)
        cylinder('hinge_axle_'+side,(x,.62,-.28),.010,.08,steel,root,axis='X',vertices=16)
        joint=pivot('joint__restraint_'+side,(x,.62,-.28),root,'X')
        joint['rotation_delta_range_deg']=[-80,0];joint['requires_stopped_handling']=True
        block('hinged_top_bar_'+side,[-.03,-.01,0],[.03,.01,.56],teal,joint,.001)
        block('soft_pressure_pad_'+side,[-.025,-.028,.02],[.025,-.01,.54],tan,joint,.0004)
        anchor('anchor_pressure_contact_'+side,(0,-.028,.28),joint,'actual_top_sections_contact')
    return root


def bounds(parts):
    return [min(p['low'][i] for p in parts) for i in range(3)],[max(p['high'][i] for p in parts) for i in range(3)]


def verify_base(root):
    parts,bvh=collect(root);lo,hi=bounds(parts)
    assert max(abs(a-b) for a,b in zip(lo+hi,[-1.6,0,-.425,1.6,.15,.425]))<EPS
    checks=[]
    for side,x in [('L',-.4),('R',.4)]:
        empty_box(parts,[x-.07,.02,-.34],[x+.07,.10,.425],('actual pocket clear toward tips',side))
        # Closed pin obstructs the rear shaft location on purpose; the other
        # .80m of the tunnel stays clear and pins lift fully above the fork.
        joint=next(o for o in root.children if o.name=='joint__cradle_lock_'+side)
        joint.location=xyz((0,.11,0));openparts,_=collect(root)
        empty_box(openparts,[x-.07,.02,-.425],[x+.07,.10,.425],('whole open lock pocket',side))
        joint.location=xyz((0,0,0));bpy.context.view_layer.update()
        checks.append({'side':side,'inner_W_H_m':[.14,.08],'full_open_depth_m':.85,'nominal_pin_radial_air_m':.002,
                       'conservative_faceted_radial_air_m':.010*math.cos(math.pi/32)-.008,
                       'open_pin_bottom_y_m':.115,'fork_top_y_m':.10,'open_pin_vertical_air_m':.015})
    return {'closed_positive_outward_parts':len(parts),'bounds_runtime':{'min':lo,'max':hi},'actual_pocket_and_pin_checks':checks,
            'upper_rig_not_baked_into_base':True}


def union_contains(parts):
    for p in parts:
        for x,y,z in p['verts']:
            inbase=-1.6-EPS<=x<=1.6+EPS and -EPS<=y<=.15+EPS and abs(z)<=.425+EPS
            inhu=abs(x)<=2.1+EPS and .15-EPS<=y<=.67+EPS and abs(z)<=.325+EPS
            assert inbase or inhu,('outside unchanged CLOSED component union',p['name'],x,y,z)


def actual_loaded():
    # Reset the main-file identity as well as objects before native library
    # append; Blender must not append from its own current saved source file.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reset();fixture=group('long-cradle-loaded-fixture');fixture['role']='visual_QA_fixture'
    fixture['source_label']='One unchanged LONG HU with C08 base/locks and separate upper restraint; geometry only'
    cradle=append_source('assets/v3/blender/long-cradle.blend','long-cradle',fixture)
    rig=append_source('assets/v3/blender/long-restraint-rig.blend','long-restraint-rig',fixture)
    cargo=append_source('assets/v3/blender/long-bundle.blend','long-bundle',fixture,(0,.15,0))
    cp,cbvh=collect(cargo);bp,bbvh=collect(cradle);rp,rbvh=collect(rig)
    union_contains(bp+rp)
    # Whole upper-accessory solids must stay out of actual cargo. Boundary
    # contact of pads at section tops and feet at supporting rails is allowed.
    for p in rp:empty_box(cp,p['low'],p['high'],('upper restraint versus actual LONG geometry',p['name']))
    bottom=[];top=[]
    for x in (-1.4,1.4):
        for z in (-.20,.20):
            a,_,_,_=bbvh.ray_cast(xyz((x,.16,z)),xyz((0,-1,0)),.03)
            b,_,_,_=cbvh.ray_cast(xyz((x,.14,z)),xyz((0,1,0)),.03)
            assert a is not None and b is not None and abs(runtime_xyz(a)[1]-.15)<EPS and abs(runtime_xyz(b)[1]-.15)<EPS
            bottom.append([x,.15,z])
        for z in (-.225,-.135,-.045,.045,.135,.225):
            a,_,_,_=rbvh.ray_cast(xyz((x,.58,z)),xyz((0,1,0)),.04)
            b,_,_,_=cbvh.ray_cast(xyz((x,.61,z)),xyz((0,-1,0)),.04)
            assert a is not None and b is not None and abs(runtime_xyz(a)[1]-.592)<EPS and abs(runtime_xyz(b)[1]-.592)<EPS,(x,z,runtime_xyz(a) if a else None,runtime_xyz(b) if b else None)
            top.append([x,.592,z])
    checks={'actual_zero_gap_lower_supports':bottom,'actual_zero_gap_top_restraints':top,
            'closed_accessory_vertices_contained_in_unchanged_C08_base_or_loaded_HU_boxes':True,
            'mass_kg':{'HU':200,'attachment_total_including_upper_rig':40,'loaded':240},'HU_instances':1,
            'actions_accepted':False}
    return fixture,checks


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    assert hashlib.sha256((ROOT/CONTRACT).read_bytes()).hexdigest()==CONTRACT_SHA
    OUT.mkdir(parents=True,exist_ok=True)
    reset();root=base();checks=verify_base(root);s=finish('long-cradle',root);checks['base_glb_sha256']=s['sha256']
    reset();root=restraints();rp,_=collect(root);union_contains(rp)
    lo,hi=bounds(rp);assert abs(hi[1]-.63)<EPS
    checks['upper_rig_closed_outward_parts']=len(rp);checks['upper_rig_closed_bounds_runtime']={'min':lo,'max':hi}
    s=finish('long-restraint-rig',root);checks['upper_rig_glb_sha256']=s['sha256']
    root,loaded=actual_loaded();checks['loaded']=loaded;s=finish('long-cradle-loaded-fixture',root);checks['loaded_fixture_glb_sha256']=s['sha256']
    checks['canonical_C08_sha256_unchanged']=CONTRACT_SHA;checks['reference_id']='M14_LONG_LOCK_REF'
    checks['scope']='Actual closed base/pockets/pins, separate upper restraint, real HU contacts and closed loaded containment. Open sweeps/vehicle native contact are next M14.6.3; full pickup actions M14.8.'
    (OUT/'actual-mesh-and-contact-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    (ROOT/'assets/v3/specs/long-cradle.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('M1462_NATIVE_VERIFIED '+json.dumps({'base_parts':checks['closed_positive_outward_parts'],'upper_parts':len(rp),'lower_contacts':4,'upper_contacts':12,'component_union_contained':True}))
