"""One explicit R-thumb hinge in an additive picker derivative; original body read-only."""
import sys,json,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,pivot,xyz,finish
from build_sealed_parcel import append_source
from build_small_pick_source import parent_at_rest,rotate
from build_picker_figure import physical_body
from build_standard_carton import collect
from native_clearance import connected_parts as connected
assert bpy.app.background
paths=['assets/v3/blender/worker-manual.blend','frontend/public/models/v3/worker-manual.glb','assets/v3/blender/worker-base.blend']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
reset();worker=append_source(paths[0],'worker_base_root',None);before,_=physical_body(worker);raw={o.name:[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH'}
finger=bpy.data.objects['joint__finger_thumb_R'];thumb=bpy.data.objects['mitten_R_thumb']
hinge=pivot('joint__thumb_press_R',(-.032,-.006,-.015),finger,'X');hinge['joint_mode']='manual_thumb_press';hinge['rotation_range_radians']=[0,.06];hinge['meaning']='Declared picker-only rigid thumb press; original finger slide retained. No wrist range or body mesh change.'
parent_at_rest(thumb,hinge);after,_=physical_body(worker);previous={p['name']:p for p in before};error=max(abs(a-b) for p in after for v,w in zip(p['verts'],previous[p['name']]['verts']) for a,b in zip(v,w));assert error<2e-6
assert len(after)==50 and all(raw[o.name]==[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH')
states=[]
for slide in[0,-.0025,-.005]:
 for angle in[0,.015,.03,.045,.06]:
  finger.location=xyz((0,0,slide));rotate(hinge,(angle,0,0));parts,_=collect(bpy.data.objects['joint__hand_R']);links=connected(parts);states.append(dict(slide_m=slide,press_rad=angle,closed_parts=len(parts),connection_pairs=links))
finger.location=xyz((0,0,0));rotate(hinge,(0,0,0));worker['role']='picker_manual_thumb_derivative';worker['reference_id']='R05';worker['preserve_articulation']=True;worker['body_mesh_geometry_unchanged']=True;worker['thumb_control_spec']='docs/adaptive-v3/specs/P03.5.3.3.1.md';worker['original_worker_manual_sha256']=hashes[paths[0]]
stats=finish('worker-small-pick',worker);assert len(stats['pivots'])==28 and len(stats['anchors'])==7
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
out=ROOT/'assets/v3/iterations/worker-base/P03.5.3.3.1';out.mkdir(parents=True,exist_ok=True)
report=dict(task_id='P03.5.3.3.1',passed=True,source_hashes=hashes,raw_body_meshes_unchanged=50,neutral_world_vertex_error_m=error,pivots=28,anchors=7,thumb_press_range_x_rad=[0,.06],thumb_bind_finger_frame_m=[-.032,-.006,-.015],connection_states=states,glb_sha256=stats['sha256'],scope='Additive R05 picker rig derivative. Native connection sweep only; actual tool/clip/contact/clearance remain parent action gates.')
(out/'native-thumb-rig.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('PICKER_THUMB_RIG_VERIFIED '+json.dumps({k:v for k,v in report.items() if k not in['connection_states','source_hashes','scope']}))
