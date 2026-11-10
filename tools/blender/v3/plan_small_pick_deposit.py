"""Select nearby native-clear arm poses for a bounded visual deposit candidate."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_sealed_parcel import append_source
from build_standard_carton import collect,triangle_box
from build_picker_figure import physical_body
from build_small_gripper import opening
from native_clearance import penetration,touching,contains
assert bpy.app.background
OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.3/tool-deposit-path-reach';POSES=ROOT/'assets/v3/iterations/worker-base/P03.5.3.3/runtime-native-poses.json';EPS=2e-6
raw=(OUT/'candidates.json').read_bytes();candidates=json.loads(raw)['candidates'];profile=json.loads(POSES.read_bytes())
for p,h in profile['input_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
frames=[f for f in profile['frames'] if f['time']>=31.6 and abs(f['time']*10-round(f['time']*10))<1e-7]
bytime={round(f['time'],6):[] for f in frames}
for c in candidates:
 if c['pose']['joint__elbow_swivel_R'][0]>0:bytime[round(c['motion_time_s'],6)].append(c)
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-small-pick.blend','worker_base_root',None);rotate(worker,(0,math.pi,0));tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None)
nodes={n.name:n for n in worker.children_recursive};C=Matrix(((1,0,0),(0,0,-1),(0,1,0)));units=[next(n for n in scene.children_recursive if n.name=='primary_unit__'+str(i)) for i in[17,23]];tote=next(n for n in scene.children_recursive if n.name=='order-tote')
arm_names=['joint__shoulder_lift_R','joint__upper_arm_R','joint__forearm_R','joint__elbow_swivel_R','joint__palm_roll_R','joint__hand_R']
previous=frames[0]['state']['arm_pose'];guides=[];results=[];failure=None

def gap_proxy(a,b):
 distance=math.sqrt(sum(max(0,a['low'][i]-b['high'][i],b['low'][i]-a['high'][i])**2 for i in range(3)))
 if distance>=.003:return distance
 return min(target['bvh'].find_nearest(v)[3] for source,target in[(a,b),(b,a)] for v in source['samples'])

def c_mouth_clear(by):
 inverse=nodes['joint__hand_R'].matrix_world.inverted();cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0];lo=[cx-.038+EPS,-.068+EPS,.033+EPS];hi=[cx+.038-EPS,-.032-EPS,.06-EPS]
 for p in[by['fore_sleeve_R'],by['cuff_R']]:
  vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
  if any(triangle_box([vs[i] for i in t],lo,hi) for t in p['triangles']):return False
  if contains(p,runtime_xyz(nodes['joint__hand_R'].matrix_world@xyz([(a+b)/2 for a,b in zip(lo,hi)]))):return False
 return True

def score(c):return sum((x-previous[n][i])**2 for n in arm_names for i,x in enumerate(c['pose'][n]))

for f in frames:
 s=f['state'];time=f['time'];worker.location=xyz(s['body']);tool.location=xyz(s['tool']);opening(tool,s['opening'])
 for name,p in f['joints'].items():
  n=nodes[name];n.location=xyz(p['position']);a=p['quaternion'];n.rotation_mode='QUATERNION';n.rotation_quaternion=(C@Quaternion((a[3],a[0],a[1],a[2])).to_matrix()@C.transposed()).to_quaternion()
 for i,n in enumerate(units):
  n.parent=tool if s['attached'] else tote;n.matrix_basis=Matrix.Translation(xyz((-.0325 if i==0 else .0325,-.002 if s['attached'] else s['package_bottom_m']-.62,0)))
 bpy.context.view_layer.update();ep,_=collect(scene);pp=[p for n in units for p in collect(n)[0]];tp=[p for p in collect(tool)[0] if not p['name'].startswith('primary_unit__')];env=[p for p in ep if not p['name'].startswith(('primary_unit__17__','primary_unit__23__'))]
 tool_hit=next((hit for a in tp for b in env+pp if (hit:=penetration(a,b))),None)
 if tool_hit:failure=dict(time=time,kind='tool_or_package_environment',hit=tool_hit);break
 base={'joint__torso':[s['torso'],0,0],'joint__head':[-.25,0,.12],'joint__upper_arm_L':[.6,0,0]}
 reuse=dict(root=s['body'],pose=base|previous,twist_axis_runtime=[.2422508594940587,-.9690031491907751,.04845015926444788],reuse_previous=True)
 ordered=sorted(bytime[round(time,6)],key=score);ordered.insert(0,reuse)
 selected=None;rejected=[];clear_without_margin=0;best_margin=0
 for index,c in enumerate(ordered):
  for name,a in c['pose'].items():
   if name.startswith('joint__elbow_swivel_'):nodes[name].rotation_mode='QUATERNION';nodes[name].rotation_quaternion=Matrix.Rotation(a[0],4,xyz(c['twist_axis_runtime'])).to_quaternion()
   else:rotate(nodes[name],a)
  bpy.context.view_layer.update()
  error=math.dist(runtime_xyz(nodes['anchor_hand_grip_R'].matrix_world.translation),[v+w for v,w in zip(s['tool'],[0,.148,.23])])
  if error>EPS:continue
  wp,_=physical_body(worker);by={p['name']:p for p in wp}
  hit=next((hit for a in wp for b in env+pp+tp if (hit:=penetration(a,b))),None)
  if not hit:
   hit=next((hit for a in wp if a['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R')) for b in wp if not b['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R','upper_sleeve_R')) if (hit:=penetration(a,b))),None)
  if hit:
   if len(rejected)<8:rejected.append(hit)
   continue
  if not c_mouth_clear(by):continue
  if not all(touching(by[a],by[b]) for a,b in [('upper_sleeve_R','fore_sleeve_R'),('cuff_R','mitten_R_spine')]):continue
  clearance=min(gap_proxy(by[n],p) for n in['fore_sleeve_R','cuff_R'] for p in tp)
  clear_without_margin+=1;best_margin=max(best_margin,clearance)
  if clearance<.00025:continue
  selected=c;results.append(dict(time=time,tested=index+1,available=len(ordered),joint_score=score(c),clear_without_margin=clear_without_margin,best_sample_margin_m=best_margin,sampled_forearm_tool_clearance_proxy_m=clearance,rejected_examples=rejected,reused_previous=c.get('reuse_previous',False)));break
 if selected is None:failure=dict(time=time,kind='no_clear_nearby_positive_twist_candidate_with_0p25mm_sample_margin',tested=len(ordered),clear_without_margin=clear_without_margin,best_sample_margin_m=best_margin,rejected_examples=rejected);break
 previous={n:selected['pose'][n] for n in arm_names};guides.append(dict(t=time,pose=previous));print('NATIVE_DEPOSIT_PLAN '+json.dumps(results[-1]),flush=True)
report=dict(passed=failure is None,source_kind='visual_pose_planning_candidate',engine_operation=False,candidate_sha256=hashlib.sha256(raw).hexdigest(),runtime_pose_sha256=hashlib.sha256(POSES.read_bytes()).hexdigest(),input_hashes=profile['input_hashes'],guides=guides,results=results,failure=failure,scope='Greedy bounded native-clear positive-twist arm samples.0.25mm selection proxy is not an exact global clearance. Dense interpolation, thumb/bar/package/tote contacts and browser gates remain separate; no continuous clip or engine admission.')
(OUT/'native-plan.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
if failure is None:
 p=ROOT/'frontend/public/models/v3/small-pick-v3.json';timeline=json.loads(p.read_text(encoding='utf8'));timeline['arm_guides']=guides;timeline.pop('arm_waypoints',None);p.write_text(json.dumps(timeline,ensure_ascii=False)+'\n',encoding='utf8')
print('NATIVE_DEPOSIT_PLAN_RESULT '+json.dumps(dict(passed=failure is None,poses=len(guides),failure=failure)),flush=True)
assert failure is None,failure
