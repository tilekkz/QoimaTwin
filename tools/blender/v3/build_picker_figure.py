"""P03.1 unchanged P01body with actual-GLB solved pushing arm pose."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix,Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,finish,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_sealed_parcel import append_source
from build_standard_carton import collect

OUT=ROOT/'assets/v3/iterations/worker-base/P03.1'


def pose_arms(worker,pose):
    conversion=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
    for name,(a,b,c) in pose['jointEulerXYZ'].items():
        obj=next(o for o in worker.children_recursive if o.name==name)
        m=Matrix.Rotation(a,3,'X')@Matrix.Rotation(b,3,'Y')@Matrix.Rotation(c,3,'Z')
        obj.rotation_mode='QUATERNION';obj.rotation_quaternion=(conversion@m@conversion.transposed()).to_quaternion()
    bpy.context.view_layer.update()


def physical_body(worker):
    # P02 runtime replaces this original decorative ink batch. Keep the old
    # editable source decoration intact, but it is not a physical body solid.
    ink=[(o,o.parent) for o in worker.children_recursive if o.name.startswith('role_badge_') and o.name!='role_badge_base']
    for o,_ in ink:o.parent=None
    try:return collect(worker)
    finally:
        for o,parent in ink:o.parent=parent
        bpy.context.view_layer.update()


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background only')
    paths=['assets/v3/blender/worker-base.blend','frontend/public/models/v3/worker-base.glb','assets/v3/specs/picker-push-pose.json']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    pose=json.loads((ROOT/paths[-1]).read_text());reset()
    worker=append_source(paths[0],'worker_base_root',None)
    vertices={o.name:[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH'}
    pose_arms(worker,pose)
    assert all(vertices[o.name]==[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH')
    parts,_=physical_body(worker);lo=[min(p['low'][i] for p in parts) for i in range(3)];hi=[max(p['high'][i] for p in parts) for i in range(3)]
    assert abs(lo[1])<2e-6 and abs(hi[1]-1.7)<2e-6
    contacts=[]
    for side,expected in zip(('L','R'),pose['grip_centres_worker_m']):
        node=next(o for o in worker.children_recursive if o.name=='anchor_hand_grip_'+side)
        point=runtime_xyz(node.matrix_world.translation);assert max(abs(a-b) for a,b in zip(point,expected))<2e-6
        axis=runtime_xyz(node.matrix_world.to_3x3()@Vector((1,0,0)));assert max(abs(a-b) for a,b in zip(axis,[-1,0,0]))<2e-6
        contacts.append({'side':side,'actual_grip_centre':point,'actual_grip_axis':axis})
    worker['reference_id']='R05';worker['pose_reference_id']='R11';worker['role_hint']='picker'
    worker['role']='working_figure_pose_checkpoint';worker['preserve_articulation']=True
    worker['body_mesh_geometry_unchanged']=True;worker['runtime_role_badge_factory']='P02'
    OUT.mkdir(parents=True,exist_ok=True);stats=finish('picker-figure',worker)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in hashes.items())
    report={'task_id':'P03.1','source_hashes':hashes,'same_native_body_mesh_coordinates':True,'unchanged_worker_scale':1,
            'closed_outward_body_parts':len(parts),'physical_body_bounds_m':{'min':lo,'max':hi},'actual_grips':contacts,
            'joints':len(stats['pivots']),'anchors':len(stats['anchors']),'glb_sha256':stats['sha256'],
            'scope':'Pose checkpoint of unchanged physical P01body. Original decorative source ink excluded only from physical body QA and restored before saving; runtime uses accepted P02volumetric picker badge. Real cart contact/action comes later.'}
    assert report['joints']==17 and report['anchors']==7
    (OUT/'actual-picker-figure-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P031_FIGURE_VERIFIED '+json.dumps({'body_parts':len(parts),'joints':17,'anchors':7,'grip_targets':2,'height_m':hi[1]}))
