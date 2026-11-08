"""Bounded actual-tool deposit candidates; never accepts a continuous action."""
import sys,json,math,hashlib,os
from pathlib import Path
import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_sealed_parcel import append_source
from build_standard_carton import collect,empty_box
from build_picker_figure import physical_body
from native_clearance import penetration,touching
assert bpy.app.background
directory=os.environ.get('QOIMA_PICK_POSE_DIRECTORY','tool-deposit-reach');assert directory in ['tool-deposit-reach','tool-predeposit-reach','tool-deposit-body-reach']
OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.3'/directory;EPS=2e-6
data=json.loads((OUT/'positive-twist-candidates.json').read_text(encoding='utf8'))
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-small-pick.blend','worker_base_root',None);rotate(worker,(0,math.pi,0))
tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None,tuple(a-b for a,b in zip(data['target'],[0,.148,.23])))
units=[]
for i,x in [(17,-.0325),(23,.0325)]:
 n=next(n for n in scene.children_recursive if n.name=='primary_unit__'+str(i));n.parent=tool;n.location=xyz((x,-.002,0));n.rotation_mode='QUATERNION';n.rotation_quaternion=(1,0,0,0);units.append(n)
nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive};targets,_=collect(scene);tp,_=collect(tool);rows=[]
for index,c in enumerate(data['candidates']):
 for n,m in rest.items():n.matrix_basis=m
 worker.location=xyz(c['root'])
 for name,a in c['pose'].items():
  if name.startswith('joint__elbow_swivel_'):nodes[name].rotation_mode='QUATERNION';nodes[name].rotation_quaternion=Matrix.Rotation(a[0],4,xyz(c['twist_axis_runtime'])).to_quaternion()
  else:rotate(nodes[name],a)
 close=(.045-2*.02*math.cos(math.pi/32))/2
 nodes['joint__finger_upper_R'].location=xyz((0,-close,0));nodes['joint__finger_lower_R'].location=xyz((0,close,0));nodes['joint__finger_thumb_R'].location=xyz((0,0,-.005))
 bpy.context.view_layer.update();wp,_=physical_body(worker);by={p['name']:p for p in wp};hits=[]
 for a in wp:
  for b in targets+tp:
   if (hit:=penetration(a,b)):hits.append(hit)
 for a in wp:
  if not a['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R')):continue
  for b in wp:
   if b['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R','upper_sleeve_R')):continue
   if (hit:=penetration(a,b)):hits.append(hit)
 inverse=nodes['joint__hand_R'].matrix_world.inverted();local=[]
 for p in [by['fore_sleeve_R'],by['cuff_R']]:
  vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']];local.append(p|dict(verts=vs,low=[min(v[i] for v in vs) for i in range(3)],high=[max(v[i] for v in vs) for i in range(3)],bvh=BVHTree.FromPolygons([xyz(v) for v in vs],p['triangles'],all_triangles=True)))
 cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0]
 try:empty_box(local,[cx-.038,-.068,.033],[cx+.038,-.032,.06],'own C-mouth')
 except AssertionError:hits.append(dict(kind='own_forearm_cuff_in_C_mouth'))
 links=all(touching(by[a],by[b]) for a,b in [('upper_sleeve_R','fore_sleeve_R'),('cuff_R','mitten_R_spine')])
 rows.append(dict(index=index,collisions=hits,links=links,root=c['root'],torso_x=c['pose']['joint__torso'][0]))
 if not hits and links:
  (OUT/'clear-deposit.json').write_text(json.dumps(c,indent=2)+'\n',encoding='utf8');print('CLEAR_NATIVE_DEPOSIT '+json.dumps(rows[-1]),flush=True);break
 if index%100==0:print('DEPOSIT_PROGRESS '+str(index),flush=True)
report=dict(tested=len(rows),candidate_sha256=hashlib.sha256((OUT/'positive-twist-candidates.json').read_bytes()).hexdigest(),clear=not rows[-1]['collisions'] and rows[-1]['links'],results=rows,scope='Bounded native endpoint candidates with actual tool and original packages17/23; no continuous path, contact-force/capacity or engine acceptance.')
(OUT/'native-deposit-candidates.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('NATIVE_DEPOSIT_PROBE '+json.dumps({k:v for k,v in report.items() if k not in ['results','scope']}))
