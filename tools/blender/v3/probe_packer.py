"""Native admission for actual thumb-face/top-seam contact candidates."""
import json,sys,math,os,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect
from verify_cart_walk import connected
EPS=2e-6

def penetrates(a,b):
    if any(a['high'][i]<=b['low'][i]+EPS or a['low'][i]>=b['high'][i]-EPS for i in range(3)):return False
    if a['bvh'].overlap(b['bvh']):return True
    for p,q in [(a,b),(b,a)]:
        for point in p['samples']:
            hit,n,_,d=q['bvh'].find_nearest(point)
            if d>EPS and n.dot(point-hit)<-EPS:return True
    return False

if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    out=ROOT/'assets/v3/iterations/packer/P04.1';which=os.environ.get('QOIMA_PACKER_PROBE_SET','front-tail-R');assert which in ['front-tail-R','table-L','top-seam-probe']
    candidate_file=out/(which+'/contact-candidates.json' if which=='top-seam-probe' else which+'-candidates.json');data=json.loads(candidate_file.read_text(encoding='utf8'))
    reset();scene=append_source('assets/v3/blender/packer-workcell-fixture.blend','packer_workcell_root',None)
    worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None)
    targets,_=collect(scene);nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive};results=[];admitted=[]
    for body in data:
        for side in body['sides']:
            for i,c in enumerate(body['sides'][side]):
                for n,m in rest.items():n.matrix_basis=m
                worker.location=xyz(body['root']);rotate(worker,body.get('root_euler',[0,math.pi,0]));rotate(nodes['joint__torso'],(body['lean'],0,0));rotate(nodes['joint__head'],body['head'])
                for s in ['L','R']:rotate(nodes['joint__foot_'+s],body.get('foot_pose',[0,0,0]))
                rotate(nodes['joint__upper_arm_L'],body['idle_left_upper'])
                for name,a in c['pose'].items():
                    if name.startswith('joint__elbow_swivel_'):
                        n=nodes[name];n.rotation_mode='QUATERNION';n.rotation_quaternion=Matrix.Rotation(a[0],4,xyz(c['axis'])).to_quaternion()
                    else:rotate(nodes[name],a)
                bpy.context.view_layer.update();parts,_=physical_body(worker);byname={p['name']:p for p in parts}
                collisions=[[a['name'],b['name']] for a in parts for b in targets if penetrates(a,b)]
                active=lambda p:p['name'].startswith(('fore_sleeve_'+side,'cuff_'+side,'mitten_'+side))
                self_collisions=[[a['name'],b['name']] for a in parts if active(a) for b in parts if not active(b) and b['name']!='upper_sleeve_'+side and penetrates(a,b)]
                links={label:connected(byname[a],byname[b]) for label,a,b in [('elbow','upper_sleeve_'+side,'fore_sleeve_'+side),('wrist','cuff_'+side,'mitten_'+side+'_spine')]}
                contact=runtime_xyz(nodes['joint__hand_'+side].matrix_world@xyz(c['contact_local']));error=math.dist(contact,body['target'])
                floor=[byname['boot_'+s]['low'][1] for s in ['L','R']]
                row=dict(root=body['root'],lean=body['lean'],ankle=body.get('ankle',0),side=side,candidate=i,collisions=collisions,self_collisions=self_collisions,links=links,contact=contact,error=error,boot_minima_y_m=floor)
                results.append(row)
                if not collisions and not self_collisions and all(links.values()) and error<EPS and all(abs(y)<EPS for y in floor):
                    admitted.append(dict(body=body|{'sides':None},side=side,candidate=c));print('CLEAR_PACKER_CONTACT '+json.dumps(row));break
    sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['assets/v3/blender/worker-manual.blend','assets/v3/blender/packer-workcell-fixture.blend',candidate_file.relative_to(ROOT).as_posix()]}
    report_file=out/(which+'/native-contact-search.json' if which=='top-seam-probe' else which+'-native.json')
    report_file.write_text(json.dumps(dict(tested=len(results),results=results,admitted=admitted,source_hashes=sources,source_kind='visual_fixture',engine_operation=False),indent=2)+'\n',encoding='utf8')
    print('PACKER_CONTACT_SEARCH '+json.dumps({'tested':len(results),'admitted':len(admitted),'best_collision_count':min((len(r['collisions']) for r in results),default=None)}))
