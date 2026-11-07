"""P03.4 replay actual runtime joint poses on unchanged editable native meshes."""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect

WORKER=os.environ.get('QOIMA_WALK_WORKER','worker-base');assert WORKER in ('worker-base','worker-manual')
OUT=ROOT/('assets/v3/iterations/picking-cart/P03.4' if WORKER=='worker-base' else 'assets/v3/iterations/worker-base/P03.5.1/gait');EPS=2e-6
C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))

def rotate(obj,angles):
    a,b,c=angles;m=Matrix.Rotation(a,3,'X')@Matrix.Rotation(b,3,'Y')@Matrix.Rotation(c,3,'Z')
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=(C@m@C.transposed()).to_quaternion()

def connected(a,b):
    if a['bvh'].overlap(b['bvh']):return True
    for p,q in [(a,b),(b,a)]:
        for v in p['samples']:
            hit,n,_,dist=q['bvh'].find_nearest(v)
            if dist<EPS or n.dot(v-hit)<-EPS:return True
    return False

if __name__=='__main__':
    paths=['assets/v3/blender/'+WORKER+'.blend','assets/v3/blender/picking-cart.blend','assets/v3/blender/order-tote.blend']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    data=json.loads((OUT/'runtime-native-poses.json').read_text())
    for path,expected in data['input_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    reset();worker=append_source(paths[0],'worker_base_root',None);cart=append_source(paths[1],'picking-cart',None);tote=append_source(paths[2],'order-tote',None)
    nodes={o.name:o for o in worker.children_recursive};cn={o.name:o for o in cart.children_recursive};frames=[];joint_links=0;max_floor_error=0;max_hand_error=0;contacts=0
    for f in data['frames']:
        cart.location=xyz(f['cart']);worker.location=xyz([a+b for a,b in zip(f['cart'],f['worker'])]);tote.location=xyz([a+b for a,b in zip(f['cart'],[0,.62,0])])
        for name,pose in f['joints'].items():nodes[name].location=xyz(pose['position']);rotate(nodes[name],pose['euler'])
        for label,pose in f['wheels'].items():o=cn['joint__wheel_'+label];o.location=xyz(pose['position']);rotate(o,pose['euler'])
        bpy.context.view_layer.update();wp,_=physical_body(worker);cp,_=collect(cart);tp,_=collect(tote)
        cmap={p['name']:p for p in cp};wmap={p['name']:p for p in wp}
        wheel_minima=[];sole_minima=[]
        for label in f['wheels']:
            p=cmap['tyre_'+label];error=abs(p['low'][1]);max_floor_error=max(max_floor_error,error);assert error<EPS,(f['time'],label,p['low'])
            wheel_minima.append({'wheel':label,'floor_vertex':min(p['verts'],key=lambda v:v[1])})
            # Actual solid hub still captures the fixed axle despite <.643mm
            # polygon contact correction. Radial overlap exceeds the offset.
            assert math.dist(runtime_xyz(cn['joint__wheel_'+label].matrix_world.translation),runtime_xyz(cn['fixed_axle_'+label].matrix_world.translation))<.000643
        for side in ['L','R']:
            palm=runtime_xyz(nodes['anchor_hand_grip_'+side].matrix_world.to_3x3()@xyz((0,0,1)))
            assert palm[1]<-.9 and abs(palm[0])<2e-5,('palm not down',f['time'],side,palm)
            assert connected(wmap['cuff_'+side],wmap['mitten_'+side+'_spine']),('wrist gap',f['time'],side)
            boot=wmap['boot_'+side];expected=f['state']['feet'][side]['lift'];assert abs(boot['low'][1]-expected)<EPS
            assert min(p['low'][1] for p in wp)>=-EPS
            sole_minima.append({'side':side,'sole_y_m':boot['low'][1],'stance':f['state']['feet'][side]['stance']})
            h=runtime_xyz(nodes['anchor_hand_grip_'+side].matrix_world.translation);target=runtime_xyz(cn['anchor_grip_'+side].matrix_world.translation)
            error=math.dist(h,target);max_hand_error=max(max_hand_error,error);assert error<2e-5
            for a,b in [('trouser_thigh_'+side,'trouser_shin_'+side),('trouser_shin_'+side,'boot_'+side)]:assert connected(wmap[a],wmap[b]),('visible leg joint gap',f['time'],a,b);joint_links+=1
        assert any(p['stance'] and abs(p['sole_y_m'])<EPS for p in sole_minima)
        for w in wp:
            for p in cp+tp:
                if any(w['high'][i]<=p['low'][i]+EPS or w['low'][i]>=p['high'][i]-EPS for i in range(3)):continue
                overlap=w['bvh'].overlap(p['bvh']);assert not overlap or (w['name'].startswith('mitten_') and p['name']=='straight_grip_bar'),('actual paired triangle intersection',f['time'],w['name'],p['name'])
                for a,b in [(w,p),(p,w)]:
                    for v in a['samples']:
                        hit,n,_,dist=b['bvh'].find_nearest(v);assert dist<EPS or n.dot(v-hit)>=-EPS,('actual solid penetration',f['time'],a['name'],b['name'])
        # Four unchanged real tote underside ribs still sit on the actual deck.
        for x in [-.20,.20]:
            for z in [-.12,.12]:
                point=[x+f['cart'][0],.62,z+f['cart'][2]]
                deck=cmap['actual_wood_deck_upper'];a,_,_,_=deck['bvh'].ray_cast(xyz([point[0],.625,point[2]]),xyz((0,-1,0)),.02)
                hits=[p['bvh'].ray_cast(xyz([point[0],.615,point[2]]),xyz((0,1,0)),.02)[0] for p in tp]
                assert a is not None and abs(runtime_xyz(a)[1]-.62)<EPS and any(h is not None and abs(runtime_xyz(h)[1]-.62)<EPS for h in hits)
                contacts+=1
        frames.append({'time':f['time'],'actual_wheel_floor_contacts':wheel_minima,'actual_soles':sole_minima,'worker_closed_parts':len(wp)})
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report={'task_id':'P03.4','source_hashes':hashes,'runtime_input_hashes':data['input_hashes'],'actual_native_frames':len(frames),'frames':frames,'maximum_native_wheel_floor_error_m':max_floor_error,'maximum_native_hand_anchor_error_m':max_hand_error,'native_leg_joint_connections':joint_links,'native_tote_rib_deck_contacts':contacts,'actual_paired_worker_cart_tote_penetration':False,'source_meshes_unchanged':True,'scope':'91actual native poses at100ms spacing plus901runtime poses. This bounded visual flat-floor fixture is not a continuous collision certificate or engine/path run.'}
    (OUT/'actual-native-walk-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P034_NATIVE_WALK_VERIFIED '+json.dumps({k:report[k] for k in ['actual_native_frames','maximum_native_wheel_floor_error_m','maximum_native_hand_anchor_error_m','native_leg_joint_connections','native_tote_rib_deck_contacts']}))
