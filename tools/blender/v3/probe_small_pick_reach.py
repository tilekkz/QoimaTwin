"""Read-only native top-entry reach feasibility; does not accept a clip."""
import json,sys,math
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect
from verify_cart_walk import connected
EPS=2e-6
data=json.loads((ROOT/'assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-search-candidates.json').read_text())
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None,(1.2,0,.74));rotate(worker,(0,math.pi,0))
targets,_=collect(scene);nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive};report=[]
for entry in data:
 for index,c in enumerate(entry['candidates']):
  if index and c['pose']==entry['candidates'][index-1]['pose']:continue
  for n,m in rest.items():n.matrix_basis=m
  worker.location=xyz(c.get('root',[1.2,0,.74]))
  for name,angles in c['pose'].items():
   if name.startswith('joint__elbow_swivel_'):
    node=nodes[name];node.rotation_mode='QUATERNION';node.rotation_quaternion=Matrix.Rotation(angles[0],4,xyz(c['twist_axis_runtime'])).to_quaternion()
   else:rotate(nodes[name],angles)
  nodes['joint__finger_upper_R'].location=xyz((0,-.0025,0));nodes['joint__finger_lower_R'].location=xyz((0,.0025,0));nodes['joint__finger_thumb_R'].location=xyz((0,0,-.005))
  bpy.context.view_layer.update();parts,_=physical_body(worker);byname={p['name']:p for p in parts};collisions=[]
  for a in parts:
   for b in targets:
    if any(a['high'][i]<=b['low'][i]+EPS or a['low'][i]>=b['high'][i]-EPS for i in range(3)):continue
    overlap=a['bvh'].overlap(b['bvh'])
    penetrating=False
    for p,q in [(a,b),(b,a)]:
     for point in p['samples']:
      hit,normal,_,distance=q['bvh'].find_nearest(point)
      if distance>EPS and normal.dot(point-hit)<-EPS:penetrating=True;break
     if penetrating:break
    if penetrating:collisions.append([a['name'],b['name']])
  links={label:connected(byname[a],byname[b]) for label,a,b in [('elbow','upper_sleeve_R','fore_sleeve_R'),('wrist','cuff_R','mitten_R_spine')]}
  hand=runtime_xyz(nodes['anchor_hand_grip_R'].matrix_world.translation)
  report.append(dict(label=entry['label'],candidate=index,collisions=collisions,links=links,hand=hand,error_m=math.dist(hand,entry['target']),pose=c))
  if not collisions and all(links.values()):
   print('CLEAR_PICK_REACH '+json.dumps(report[-1]));break
out=ROOT/'assets/v3/iterations/worker-base/P03.5.3/reach-probe/native-pick-feasibility.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('REACH_CANDIDATES '+json.dumps([dict(label=r['label'],candidate=r['candidate'],collisions=r['collisions'],links=r['links'],error_m=r['error_m']) for r in report if r['candidate']==0]))
