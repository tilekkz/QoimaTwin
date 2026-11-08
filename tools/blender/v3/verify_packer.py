"""Replay runtime poses on unchanged native solids, not proxy limb capsules."""
import sys,json,hashlib
from pathlib import Path
import bpy
from mathutils import Quaternion,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_picker_figure import physical_body
from build_standard_carton import collect,empty_box
from verify_cart_walk import connected
from probe_packer import penetrates
EPS=2e-6;C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
def quat(node,value):
    x,y,z,w=value;q=Quaternion((w,x,y,z));node.rotation_mode='QUATERNION';node.rotation_quaternion=(C@q.to_matrix()@C.transposed()).to_quaternion()
if __name__=='__main__':
    assert bpy.app.background
    out=ROOT/'assets/v3/iterations/packer/P04.2';data=json.loads((out/'runtime-native-poses.json').read_text(encoding='utf8'))
    for p,h in data['input_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    reset();scene=append_source('assets/v3/blender/packer-workcell-fixture.blend','packer_workcell_root',None);worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None)
    targets,_=collect(scene);bytarget={p['name']:p for p in targets};nodes={n.name:n for n in worker.children_recursive};frames=[];contacts=0;mouth_checks=0;worst_floor=0;worst_matrix=0;defects=[]
    for f in data['frames']:
        worker.location=xyz(f['worker']['position']);quat(worker,f['worker']['quaternion'])
        for name,p in f['joints'].items():nodes[name].location=xyz(p['position']);quat(nodes[name],p['quaternion'])
        bpy.context.view_layer.update();parts,_=physical_body(worker);names={p['name']:p for p in parts}
        for name,p in f['joints'].items():
            if 'world' not in p:continue
            m=C.transposed().to_4x4()@nodes[name].matrix_world@C.to_4x4();error=max(abs(m[i][j]-p['world'][j*4+i]) for i in range(4) for j in range(4));worst_matrix=max(worst_matrix,error);assert error<EPS,(f['time'],name,'native/runtime transform mismatch',error)
        pairs=[[a['name'],b['name']] for a in parts for b in targets if penetrates(a,b)]
        for side in ['L','R']:
            active=lambda p:p['name'].startswith(('fore_sleeve_'+side,'cuff_'+side,'mitten_'+side))
            pairs += [[a['name'],b['name']] for a in parts if active(a) for b in parts if not active(b) and b['name']!='upper_sleeve_'+side and penetrates(a,b)]
            if not connected(names['cuff_'+side],names['mitten_'+side+'_spine']):pairs.append(['wrist_gap',side])
            if not connected(names['upper_sleeve_'+side],names['fore_sleeve_'+side]):pairs.append(['elbow_gap',side])
            floor=abs(names['boot_'+side]['low'][1]);worst_floor=max(worst_floor,floor);assert floor<EPS
            inverse=nodes['joint__hand_'+side].matrix_world.inverted();local=[]
            for p in [names['fore_sleeve_'+side],names['cuff_'+side]]:
                vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
                local.append(p|dict(verts=vs,low=[min(v[i] for v in vs) for i in range(3)],high=[max(v[i] for v in vs) for i in range(3)],bvh=BVHTree.FromPolygons([xyz(v) for v in vs],p['triangles'],all_triangles=True)))
            cx=runtime_xyz(nodes['anchor_hand_grip_'+side].location)[0]
            try:empty_box(local,[cx-.038,-.068,.033],[cx+.038,-.032,.06],side+' central hand opening');mouth_checks+=1
            except AssertionError as e:pairs.append(['own_cuff_forearm_in_hand_opening',side,str(e)])
        assert min(p['low'][1] for p in parts)>=-EPS
        hits=[]
        for c in f['contacts']:
            if not c['active']:continue
            side=c['side'];point=c['target_workcell_m'];target=bytarget['worktop_R' if side=='L' else 'front_paper_and_print'];glove=names['mitten_'+side+'_lower_pad']
            # Nearest actual triangles avoid short-ray BVH cancellation at a
            # metre-scale world offset. Opposed normals and distance to the
            # prescribed point retain the same2um surface-contact requirement.
            p,n,_,dp=target['bvh'].find_nearest(xyz(point));q,m,_,dq=glove['bvh'].find_nearest(xyz(point))
            assert p is not None and q is not None,(f['time'],side,'missing opposed surface')
            assert max(dp,dq,(p-q).length)<EPS and runtime_xyz(n)[2]>.99 and runtime_xyz(m)[2]<-.99,(f['time'],side,'contact normal/gap',runtime_xyz(p),runtime_xyz(q),runtime_xyz(n),runtime_xyz(m),(p-q).length)
            hits.append(dict(side=side,gap_m=(p-q).length,target=target['name'],glove=glove['name']));contacts+=1
        if pairs:defects.append(dict(time=f['time'],mode=f['mode'],pairs=pairs))
        frames.append(dict(time=f['time'],mode=f['mode'],penetration_pairs=pairs,contacts=hits))
    report=dict(task_id='P04.2',passed=not defects,source_kind='visual_fixture',engine_operation=False,input_hashes=data['input_hashes'],actual_native_frames=len(frames),native_opposed_surface_contacts=contacts,own_forearm_cuff_clear_of_central_hand_opening_checks=mouth_checks,maximum_boot_floor_error_m=worst_floor,maximum_native_runtime_matrix_element_difference=worst_matrix,defects=defects,frames=frames,scope='153 sampled native poses including idle/blocked, with paired solid/forearm-body clearance, cuff/elbow links, central hand-opening gauges and nearest actual film/wood triangle contacts. Not a continuous collision certificate or engine run.')
    (out/'actual-native-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PACKER_NATIVE_CHECKS '+json.dumps({k:report[k] for k in ['passed','actual_native_frames','native_opposed_surface_contacts','maximum_boot_floor_error_m']}),flush=True)
    if defects:print('PACKER_FIRST_DEFECT '+json.dumps(defects[0]),flush=True)
    assert not defects,'Native transition clearance failed; see actual-native-checks.json'
