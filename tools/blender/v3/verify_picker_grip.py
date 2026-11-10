"""P03.3 actual glove/bar contact and native paired clearance; no source edits."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_picker_figure import pose_arms,physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect

OUT=ROOT/'assets/v3/iterations/picking-cart/P03.3';EPS=2e-6

if __name__=='__main__':
    paths=['assets/v3/blender/worker-base.blend','assets/v3/blender/picking-cart.blend','assets/v3/blender/order-tote.blend','frontend/public/data/v3/picker-push-pose.json']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    pose=json.loads((ROOT/paths[-1]).read_text());reset()
    cart=append_source(paths[1],'picking-cart',None);tote=append_source(paths[2],'order-tote',None,(0,.62,0))
    worker=append_source(paths[0],'worker_base_root',None,(0,0,-.7975));pose_arms(worker,pose)
    wp,wbvh=physical_body(worker);cp,cbvh=collect(cart);tp,tbvh=collect(tote)
    bar=next(p for p in cp if p['name']=='straight_grip_bar');contacts=[];anchors=[]
    for side,x in [('L',-.195),('R',.195)]:
        h=next(o for o in worker.children_recursive if o.name=='anchor_hand_grip_'+side)
        target=next(o for o in cart.children_recursive if o.name=='anchor_grip_'+side)
        assert (h.matrix_world.translation-target.matrix_world.translation).length<2e-5
        axis=runtime_xyz(h.matrix_world.to_3x3()@Vector((1,0,0)));assert max(abs(a-b) for a,b in zip(axis,[-1,0,0]))<2e-5
        palm=runtime_xyz(h.matrix_world.to_3x3()@xyz((0,0,1)));assert palm[1]<-.85 and abs(palm[0])<2e-5
        anchors.append({'side':side,'hand':runtime_xyz(h.matrix_world.translation),'cart':runtime_xyz(target.matrix_world.translation),'hand_axis':axis})
        gloves=[p for p in wp if p['name'].startswith('mitten_'+side)]
        assert gloves,('missing physical glove',side,[p['name'] for p in wp])
        # Witness rays start inside the real open hand channel, where the
        # accepted 45mm bar meets the flat inner glove surfaces tangentially.
        for label,direction in [('up',(0,1,0)),('down',(0,-1,0)),('rear',(0,0,-1)),('front',(0,0,1))]:
            start=xyz((x,.9775,-.4375));d=xyz(direction)
            b,_,_,_=bar['bvh'].ray_cast(start,d,.06)
            candidates=[]
            for p in gloves:
                a,_,_,_=p['bvh'].ray_cast(start,d,.06)
                if a is not None:candidates.append((a,p['name']))
            if b is None or not candidates:continue
            a,name=min(candidates,key=lambda pair:(pair[0]-start).length)
            if (a-b).length<EPS:contacts.append({'side':side,'surface':name,'direction':label,'point':runtime_xyz(a),'gap_m':(a-b).length})
        for label,local in [('finger_upper',(0,1,0)),('finger_lower',(0,-1,0)),('palm_back',(0,0,-1))]:
            start=h.matrix_world.translation;d=h.matrix_world.to_3x3()@xyz(local)
            b,_,_,_=bar['bvh'].ray_cast(start,d,.06)
            hits=[(hit,p['name']) for p in gloves if (hit:=p['bvh'].ray_cast(start,d,.06)[0]) is not None]
            if b is not None and hits:
                a,name=min(hits,key=lambda item:(item[0]-start).length)
                if (a-b).length<EPS:contacts.append(dict(side=side,surface=name,direction=label,point=runtime_xyz(a),gap_m=(a-b).length))
        assert any(c['side']==side for c in contacts),('no actual surface witness',side)
    checked=0
    for w in wp:
        for target in cp+tp:
            if any(w['high'][i]<=target['low'][i]+EPS or w['low'][i]>=target['high'][i]-EPS for i in range(3)):continue
            checked+=1;overlap=w['bvh'].overlap(target['bvh'])
            assert not overlap or (w['name'].startswith('mitten_') and target['name']=='straight_grip_bar'),('body/cart/tote triangles',w['name'],target['name'],len(overlap))
            # Also catch containment and forbid penetration at tangent contact.
            for p,q in [(w,target),(target,w)]:
                for v in p['samples']:
                    hit,n,_,dist=q['bvh'].find_nearest(v)
                    assert dist<EPS or n.dot(v-hit)>=-EPS,('actual solid penetration',p['name'],q['name'],dist)
    soles=[]
    for side,x in [('L',-.115),('R',.115)]:
        boot=next(p for p in wp if p['name']=='boot_'+side)
        a,_,_,_=boot['bvh'].ray_cast(xyz((x,-.01,-.7975)),xyz((0,1,0)),.03)
        assert a is not None and abs(runtime_xyz(a)[1])<EPS;soles.append(runtime_xyz(a))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in hashes.items())
    OUT.mkdir(parents=True,exist_ok=True)
    report={'task_id':'P03.3','source_hashes':hashes,'actual_hand_anchors':anchors,'actual_glove_bar_surface_contacts':contacts,'actual_boot_floor_contacts':soles,'physical_body_parts':len(wp),'cart_parts':len(cp),'candidate_native_pairs_checked':checked,'solid_penetration':False,'native_tote_instances':1,'all_source_meshes_unchanged':True,'scope':'Standing coupled contact only. No gait, steering or payload transfer admission.'}
    (OUT/'actual-native-grip-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P033_GRIP_VERIFIED '+json.dumps({'hand_anchors':2,'actual_surface_contacts':len(contacts),'sole_contacts':2,'body_parts':len(wp),'paired_checks':checked}))
