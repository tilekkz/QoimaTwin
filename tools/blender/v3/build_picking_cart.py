"""P03.2 metric R11cart with real caster assemblies and separate native tote."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,anchor,cylinder,finish,group,material,pivot,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_long_rack import block
from build_sealed_parcel import append_source
from build_standard_carton import collect,empty_box

OUT=ROOT/'assets/v3/iterations/picking-cart/P03.2';EPS=2e-6


def tyre(name,mat,parent):
    # Closed annulus, real6mm shoulder relief at this small wheel scale.
    profile=[(-.020,.035),(-.020,.069),(-.014,.075),(.014,.075),(.020,.069),(.020,.035)]
    n=24;verts=[xyz((x,r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n))) for x,r in profile for i in range(n)]
    faces=[]
    for j in range(6):
        for i in range(n):q=(i+1)%n;k=(j+1)%6;faces.append((j*n+i,j*n+q,k*n+q,k*n+i))
    mesh=bpy.data.meshes.new(name+'_annular_profile');mesh.from_pydata(verts,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
    obj['radius_m']=.075;obj['segments']=24;obj['width_m']=.04;return obj


def build():
    root=group('picking-cart');root['role']='equipment_template';root['reference_id']='R11'
    root['preserve_articulation']=True;root['operational_admission']=False;root['baked_tote_or_stock']=False
    root['outer_dimensions_xyz_m']=[.72,1,.92];root['wheel_radius_m']=.075
    root['top_tray_clear_W_D_m']=[.65,.70];root['tray_floor_planes_y_m']=[.22,.62]
    dark=material('V3_CART_frame','#293D46');teal=material('V3_CART_rims','#2E7376')
    tan=material('V3_CART_decks_caps','#C99A60');rubber=material('V3_CART_tyre','#202D32')
    # Closed outward new parts use front faces; opposing faces at real panel
    # support contacts must not draw through each other from below.
    for mat in (dark,teal,tan,rubber):mat.use_backface_culling=True
    for side,x in [('L',-.325),('R',.325)]:
        for end,z in [('rear',-.425),('front',.425)]:
            block('frame_post_'+end+'_'+side,[x-.035,.195,z-.035],[x+.035,1 if end=='rear' else .705,z+.035],dark,root,.003)
    for label,y in [('lower',.22),('upper',.62)]:
        block('actual_wood_deck_'+label,[-.325,y-.02,-.35],[.325,y,.35],tan,root,.0008)
        for side,lo,hi in [('L',-.36,-.325),('R',.325,.36)]:
            block('tray_side_'+label+'_'+side,[lo,y,-.39],[hi,y+.07,.39],teal,root,.001)
        for end,lo,hi in [('rear',-.425,-.35),('front',.35,.425)]:
            block('tray_end_'+label+'_'+end,[-.325,y,lo],[.325,y+.07,hi],teal,root,.001)
        for side,lo,hi in [('L',-.36,-.30),('R',.30,.36)]:
            block('deck_support_ledge_'+label+'_'+side,[lo,y-.04,-.39],[hi,y-.02,.39],dark,root,.0008)
        anchor('anchor_'+label+'_tote_bottom',(0,y,0),root,'actual_tote_support_floor')
    cylinder('straight_grip_bar',(0,.9775,-.4375),.0225,.65,dark,root,axis='X',vertices=32)
    anchor('anchor_handle_centre',(0,.9775,-.4375),root,'push_handle_centre')
    for side,x in [('L',-.195),('R',.195)]:anchor('anchor_grip_'+side,(x,.9775,-.4375),root,'actual_glove_contact_axis')
    for side,sx in [('L',-1),('R',1)]:
        for end,sz in [('rear',-1),('front',1)]:
            label=end+'_'+side;x=sx*.28;z=sz*.38
            # Inboard bearing/mount permits the whole wheel/yoke yaw envelope
            # inside the same .72x.92 frame at every swivel angle.
            mx=sx*.30;mz=sz*.405
            block('caster_mount_plate_'+label,[mx-.06,.19,mz-.05],[mx+.06,.205,mz+.05],dark,root,.001)
            caster=pivot('joint__caster_'+label,(x,.165,z),root,'Y')
            caster['rotation_delta_range_deg']=[-180,180];caster['zero_trail']=True
            cylinder('swivel_bearing_'+label,(0,.015,0),.025,.03,dark,caster,axis='Y',vertices=16)
            block('fork_bridge_'+label,[-.035,-.007,-.03],[.035,.013,.03],dark,caster,.001)
            for ear,a,b in [('L',-.035,-.023),('R',.023,.035)]:
                block('fork_ear_'+label+'_'+ear,[a,-.100,-.025],[b,.005,.025],dark,caster,.001)
            cylinder('fixed_axle_'+label,(0,-.09,0),.0075,.07,dark,caster,axis='X',vertices=16)
            wheel=pivot('joint__wheel_'+label,(0,-.09,0),caster,'X')
            wheel['radius_m']=.075;wheel['rolling_axis_runtime']='X'
            wheel['floor_contact_profile']='Actual24faceted tyre; runtime may apply a bounded vertical contact correction within the hub/axle overlap, never scale.'
            tyre('tyre_'+label,rubber,wheel)
            cylinder('wheel_hub_'+label,(0,0,0),.040,.036,dark,wheel,axis='X',vertices=24)
            for sign in (-1,1):cylinder('hub_cap_'+label+('_L' if sign<0 else '_R'),(sign*.020,0,0),.018,.004,tan,wheel,axis='X',vertices=16)
            anchor('anchor_wheel_axis_'+label,(0,0,0),wheel,'wheel_centre')
    anchor('anchor_floor_origin',(0,0,0),root,'cart_floor_centre')
    return root


def connected(parts):
    links=[];adj={p['name']:set() for p in parts}
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            if any(a['high'][j]<b['low'][j]-EPS or b['high'][j]<a['low'][j]-EPS for j in range(3)):continue
            touches=bool(a['bvh'].overlap(b['bvh']))
            if not touches:
                for p,target in [(a,b),(b,a)]:
                    for v in p['samples']:
                        near,n,_,dist=target['bvh'].find_nearest(v)
                        if dist<EPS or n.dot(v-near)<-EPS:touches=True;break
                    if touches:break
            if touches:adj[a['name']].add(b['name']);adj[b['name']].add(a['name']);links.append([a['name'],b['name']])
    reached={parts[0]['name']};queue=list(reached)
    while queue:
        for n in adj[queue.pop()]-reached:reached.add(n);queue.append(n)
    assert reached==set(adj),('unconnected cart parts',sorted(set(adj)-reached))
    return links


def verify(root):
    parts,bvh=collect(root);lo=[min(p['low'][i] for p in parts) for i in range(3)];hi=[max(p['high'][i] for p in parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(lo+hi,[-.36,0,-.46,.36,1,.46]))<EPS
    empty_box(parts,[-.325,.62,-.35],[.325,.96,.35],'exact upper clear opening and unchanged tote sweep')
    empty_box(parts,[-.325,.22,-.35],[.325,.56,.35],'lower clear opening, not baked contents')
    wheels=[]
    for side,sx in [('L',-1),('R',1)]:
        for end,sz in [('rear',-1),('front',1)]:
            label=end+'_'+side;p=next(p for p in parts if p['name']=='tyre_'+label)
            hit,n,_,_=p['bvh'].ray_cast(xyz((sx*.28,-.01,sz*.38)),xyz((0,1,0)),.03)
            assert hit is not None and abs(runtime_xyz(hit)[1])<EPS and n.dot(xyz((0,1,0)))<-.9
            caster=next(o for o in root.children if o.name=='joint__caster_'+label);cp,_=collect(caster)
            radius=max(math.hypot(v[0]-sx*.28,v[2]-sz*.38) for q in cp for v in q['verts'])
            assert radius<.08
            wheels.append({'id':label,'actual_floor_point':runtime_xyz(hit),'full_yaw_XZ_radius_m':radius,'minimum_body_margin_m':.08-radius})
    supports=[]
    for label,y in [('lower',.22),('upper',.62)]:
        for x in (-.315,.315):
            for z in (-.25,.25):
                deck=next(p for p in parts if p['name']=='actual_wood_deck_'+label)
                ledge=next(p for p in parts if p['name']=='deck_support_ledge_'+label+('_L' if x<0 else '_R'))
                a,_,_,_=deck['bvh'].ray_cast(xyz((x,y-.025,z)),xyz((0,1,0)),.02)
                b,_,_,_=ledge['bvh'].ray_cast(xyz((x,y-.015,z)),xyz((0,-1,0)),.02)
                assert a is not None and b is not None and abs(runtime_xyz(a)[1]-(y-.02))<EPS and abs(runtime_xyz(b)[1]-(y-.02))<EPS
                supports.append([x,y-.02,z])
    links=connected(parts)
    return {'closed_outward_parts':len(parts),'bounds_m':{'min':lo,'max':hi},'all_parts_connected':True,'actual_connection_links':links,
            'four_actual_floor_contacts_and_full_swivel_bounds':wheels,'eight_actual_panel_support_contacts':supports,
            'upper_clear_W_D_m':[.65,.70],'floor_planes_y_m':[.22,.62],'handle_centre_m':[0,.9775,-.4375],'handle_radius_m':.0225}


def tote_fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True);reset();root=group('picking-cart-tote-fixture');root['role']='visual_QA_fixture'
    root['source_label']='Unchanged separate M07tote supported on actual R11cart upper panel; no stock/capacity inference'
    cart=append_source('assets/v3/blender/picking-cart.blend','picking-cart',root)
    tote=append_source('assets/v3/blender/order-tote.blend','order-tote',root,(0,.62,0))
    cp,cbvh=collect(cart);tp,tbvh=collect(tote)
    for p in tp:empty_box(cp,p['low'],p['high'],('native unchanged tote versus actual cart',p['name']))
    contacts=[]
    # Real tote underside has longitudinal ribs, not a fictitious full base.
    for x in (-.20,.20):
        for z in (-.12,.12):
            a,_,_,_=cbvh.ray_cast(xyz((x,.625,z)),xyz((0,-1,0)),.02)
            b,_,_,_=tbvh.ray_cast(xyz((x,.615,z)),xyz((0,1,0)),.02)
            assert a is not None and b is not None and abs(runtime_xyz(a)[1]-.62)<EPS and abs(runtime_xyz(b)[1]-.62)<EPS
            contacts.append([x,.62,z])
    stats=finish('picking-cart-tote-fixture',root)
    return {'tote_instances':1,'tote_scale':1,'actual_zero_gap_floor_contacts':contacts,'lateral_margin_m':.025,'depth_margin_m':.15,'tote_top_y_m':.96,'fixture_sha256':stats['sha256']}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    path=ROOT/'assets/v3/blender/order-tote.blend';source_hash=hashlib.sha256(path.read_bytes()).hexdigest();OUT.mkdir(parents=True,exist_ok=True)
    reset();root=build();checks=verify(root);stats=finish('picking-cart',root);checks['glb_sha256']=stats['sha256']
    checks['native_tote']=tote_fixture();assert source_hash==hashlib.sha256(path.read_bytes()).hexdigest();checks['tote_source_unchanged_sha256']=source_hash
    checks['scope']='R11cart geometry and actual native tote fit/support. No baked contents, scale, capacity declaration, hand or locomotion acceptance.'
    (OUT/'actual-cart-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf8')
    (ROOT/'assets/v3/specs/picking-cart.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf8')
    print('P032_CART_VERIFIED '+json.dumps({'closed_parts':checks['closed_outward_parts'],'connection_links':len(checks['actual_connection_links']),'floor_contacts':4,'panel_supports':8,'tote_supports':4}))
