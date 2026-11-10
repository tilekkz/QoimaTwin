"""Native admission of analytical SMALL top-entry candidates; no clip acceptance."""
import json,sys,math,hashlib,os,copy
from pathlib import Path
import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect,empty_box
from verify_cart_walk import connected
assert bpy.app.background
EPS=2e-6
directory=('gripper-raised-reach-probe' if os.environ.get('QOIMA_PICK_RAISE')=='1' else 'gripper-reach-probe') if os.environ.get('QOIMA_PICK_GRIPPER')=='1' else 'side-pole-probe' if os.environ.get('QOIMA_PICK_SIDE')=='1' else 'pole-probe'
if os.environ.get('QOIMA_PICK_FIXED_HANDLE')=='1' and directory=='gripper-raised-reach-probe':directory='gripper-raised-fixed-reach-probe'
if os.environ.get('QOIMA_PICK_FINE_BODIES')=='1':directory='tool-fine-raised-reach' if os.environ.get('QOIMA_PICK_RAISE')=='1' else 'tool-fine-pick-reach'
OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.3'/directory
data=json.loads((OUT/'candidates.json').read_text(encoding='utf8'))
body_filter=int(os.environ['QOIMA_PICK_BODY_INDEX']) if 'QOIMA_PICK_BODY_INDEX' in os.environ else None
suffix='' if body_filter is None else '-body'+str(body_filter)
head_yaw=float(os.environ['QOIMA_PICK_HEAD_YAW']) if 'QOIMA_PICK_HEAD_YAW' in os.environ else None
if head_yaw is not None:
 assert math.isfinite(head_yaw) and abs(head_yaw)<=.6
 suffix+='-head'+str(head_yaw).replace('-','minus').replace('.','p')
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);rotate(worker,(0,math.pi,0))
targets,_=collect(scene);nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive}
report=[]
from native_clearance import penetration as penetrates
for index,c in enumerate(data['candidates']):
 if body_filter is not None and c['body_index']!=body_filter:continue
 if head_yaw is not None:
  c=copy.deepcopy(c);c['pose']['joint__head'][1]=head_yaw
 for n,m in rest.items():n.matrix_basis=m
 worker.location=xyz(c['root'])
 for name,angles in c['pose'].items():
  if name.startswith('joint__elbow_swivel_'):
   node=nodes[name];node.rotation_mode='QUATERNION';node.rotation_quaternion=Matrix.Rotation(angles[0],4,xyz(c['twist_axis_runtime'])).to_quaternion()
  else:rotate(nodes[name],angles)
 nodes['joint__finger_upper_R'].location=xyz((0,-.0025,0));nodes['joint__finger_lower_R'].location=xyz((0,.0025,0));nodes['joint__finger_thumb_R'].location=xyz((0,0,-.005))
 bpy.context.view_layer.update();parts,_=physical_body(worker);byname={p['name']:p for p in parts};collisions=[]
 for a in parts:
  for b in targets:
   if penetrates(a,b):collisions.append([a['name'],b['name']])
 for a in parts:
  if not a['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R')):continue
  for b in parts:
   if b['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R','upper_sleeve_R')):continue
   if penetrates(a,b):collisions.append([a['name'],b['name']])
 links={label:connected(byname[a],byname[b]) for label,a,b in [('elbow','upper_sleeve_R','fore_sleeve_R'),('wrist','cuff_R','mitten_R_spine')]}
 inverse=nodes['joint__hand_R'].matrix_world.inverted();local=[]
 for p in[byname['fore_sleeve_R'],byname['cuff_R']]:
  vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
  local.append(p|dict(verts=vs,low=[min(v[i] for v in vs) for i in range(3)],high=[max(v[i] for v in vs) for i in range(3)],bvh=BVHTree.FromPolygons([xyz(v) for v in vs],p['triangles'],all_triangles=True)))
 cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0]
 try:empty_box(local,[cx-.038,-.068,.033],[cx+.038,-.032,.06],'actual own C-mouth clearance')
 except AssertionError:collisions.append(['own_forearm_cuff_in_C_mouth'])
 hand=runtime_xyz(nodes['anchor_hand_grip_R'].matrix_world.translation)
 report.append(dict(candidate=index,body_index=c['body_index'],collisions=collisions,links=links,error_m=math.dist(hand,data['target']),elbow_world=c['elbow_world']))
 if not collisions and all(links.values()):
  (OUT/('clear-candidate'+suffix+'.json')).write_text(json.dumps(c,indent=2)+'\n',encoding='utf8')
  print('CLEAR_PICK_POLE '+json.dumps(report[-1]));break
 if index%200==0:print('PICK_POLE_PROGRESS '+str(index),flush=True)
summary=dict(task_id='P03.5.3',candidate_sha256=hashlib.sha256((OUT/'candidates.json').read_bytes()).hexdigest(),candidates=len(data['candidates']),body_index_filter=body_filter,head_yaw_override=head_yaw,tested=len(report),clear=any(not r['collisions'] and all(r['links'].values()) for r in report),best=min(report,key=lambda r:len(r['collisions'])) if report else None,results=report,scope='Bounded analytical search/native sampled penetration check, not continuous collision or action acceptance.')
(OUT/('native-feasibility'+suffix+'.json')).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print('PICK_POLE_VERIFIED '+json.dumps({k:v for k,v in summary.items() if k not in ['results','scope']}))
