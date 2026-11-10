"""FIX01.1: explicit axial wrist controls; same accepted body mesh coordinates."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import ROOT, finish, pivot, runtime_xyz
from build_picker_figure import physical_body


def inward_palms(worker):
    for side, angle in [('L', math.pi/2), ('R', -math.pi/2)]:
        hand=next(o for o in worker.children_recursive if o.name=='joint__hand_'+side)
        roll=next((o for o in worker.children_recursive if o.name=='joint__palm_roll_'+side),None)
        if roll is None:
            basis=hand.matrix_basis.copy()
            roll=pivot('joint__palm_roll_'+side,(0,0,0),hand.parent,'Y')
            roll.matrix_basis=basis
            hand.parent=roll;hand.matrix_basis=Matrix.Identity(4)
        roll['joint_mode']='forearm_axial_pronation'
        roll['rotation_range_radians']=[-math.pi,math.pi]
        roll['neutral_runtime_y_rad']=angle
        roll['meaning']='Axial pronation, distinct from the original wrist flexion limits.'
        roll.rotation_mode='XYZ';roll.rotation_euler=(0,0,angle)
    worker['neutral_palm_direction']='inward_towards_legs'
    worker['palm_orientation_correction']='FIX01.1 2026-11-08'
    bpy.context.view_layer.update()


if __name__=='__main__':
    out=ROOT/'assets/v3/iterations/worker-base/FIX01.1';out.mkdir(parents=True,exist_ok=True)
    results=[]
    for asset in ('worker-base','worker-manual'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        source=ROOT/'work/v3/corrections-2026-11-08/before/assets/v3/blender'/f'{asset}.blend'
        if not source.exists():source=ROOT/'assets/v3/blender'/f'{asset}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(source))
        worker=bpy.data.objects['worker_base_root']
        raw={o.name:[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH'}
        inward_palms(worker)
        assert all(raw[o.name]==[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH')
        parts,_=physical_body(worker);byname={p['name']:p for p in parts};palms=[]
        for side,direction in [('L',[1,0,0]),('R',[-1,0,0])]:
            hand=bpy.data.objects['joint__hand_'+side]
            axis=runtime_xyz(hand.matrix_world.to_3x3()@__import__('mathutils').Vector((0,-1,0)))
            assert max(abs(a-b) for a,b in zip(axis,direction))<2e-6
            cuff=byname['cuff_'+side];spine=byname['mitten_'+side+'_spine']
            assert cuff['bvh'].overlap(spine['bvh']),('disconnected wrist',asset,side)
            # Hand must clear the corresponding actual trouser solid.
            for glove in [p for p in parts if p['name'].startswith('mitten_'+side)]:
                for target in [p for p in parts if p['name'].startswith('trouser_')]:
                    assert not glove['bvh'].overlap(target['bvh']),('hand/leg intersection',asset,glove['name'],target['name'])
            palms.append(dict(side=side,actual_open_palm_direction=axis,actual_cuff_spine_overlap=True))
        assert abs(max(p['high'][1] for p in parts)-1.7)<2e-6
        stats=finish(asset,worker)
        results.append(dict(asset=asset,prior_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),raw_mesh_coordinates_unchanged=True,body_parts=len(parts),palms=palms,pivots=len(stats['pivots']),glb_sha256=stats['sha256']))
    (out/'actual-neutral-palms.json').write_text(json.dumps(dict(task_id='FIX01.1',results=results),indent=2)+'\n',encoding='utf8')
    print('INWARD_PALMS_VERIFIED '+json.dumps(results))
