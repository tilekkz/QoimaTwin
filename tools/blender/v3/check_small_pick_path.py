"""Replay actual runtime transforms on unchanged native solids; bounded visual QA."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import closest_point_on_tri
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_sealed_parcel import append_source
from build_standard_carton import collect,triangle_box
from build_picker_figure import physical_body
from build_small_gripper import opening
from native_clearance import penetration,touching,contains
assert bpy.app.background
EPS=2e-6;OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.3.3';C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
pose_bytes=(OUT/'runtime-native-poses.json').read_bytes();pose_sha256=hashlib.sha256(pose_bytes).hexdigest();data=json.loads(pose_bytes)
native_dependencies={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/blender/v3/check_small_pick_path.py','tools/blender/v3/native_clearance.py','tools/blender/v3/build_small_gripper.py','tools/blender/v3/small_gripper_drive.py','tools/blender/v3/build_picker_figure.py','tools/blender/v3/build_standard_carton.py','tools/blender/v3/v3_common.py']}
for p,h in data['input_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-small-pick.blend','worker_base_root',None);rotate(worker,(0,math.pi,0))
tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None)
nodes={n.name:n for n in worker.children_recursive};units=[next(n for n in scene.children_recursive if n.name=='primary_unit__'+str(i)) for i in [17,23]];unit_rest={n:(n.parent,n.matrix_basis.copy()) for n in units};tote=next(n for n in scene.children_recursive if n.name=='order-tote')

def opposed(a,b,point):
 candidates=[]
 for part in [a,b]:
  hits=[]
  for tri in part['triangles']:
   v=[xyz(part['verts'][i]) for i in tri];hit=closest_point_on_tri(point,*v)
   if (hit-point).length<EPS:hits.append((hit,(v[1]-v[0]).cross(v[2]-v[0]).normalized()))
  candidates.append(hits)
 good=[(p,q) for p in candidates[0] for q in candidates[1] if p[1].dot(q[1])<-.99 and (p[0]-q[0]).length<EPS]
 assert good,('missing opposed native contact',a['name'],b['name'],runtime_xyz(point))
 return min((p[0]-q[0]).length for p,q in good)

def mouth(by):
 inverse=nodes['joint__hand_R'].matrix_world.inverted();cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0];lo=[cx-.038+EPS,-.068+EPS,.033+EPS];hi=[cx+.038-EPS,-.032-EPS,.06-EPS]
 for part in [by['fore_sleeve_R'],by['cuff_R']]:
  vs=[runtime_xyz(inverse@xyz(v)) for v in part['verts']]
  assert not any(triangle_box([vs[i] for i in t],lo,hi) for t in part['triangles']),('own C-mouth triangle intrusion',part['name'])
  centre=nodes['joint__hand_R'].matrix_world@xyz([(a+b)/2 for a,b in zip(lo,hi)])
  assert not contains(part,runtime_xyz(centre)),('own C-mouth solid interior',part['name'])

rows=[];failure=None
try:
 for f in data['frames']:
  s=f['state'];worker.location=xyz(s['body']);tool.location=xyz(s['tool']);opening(tool,s['opening'])
  for name,p in f['joints'].items():
   n=nodes[name];n.location=xyz(p['position']);a=p['quaternion'];q=Quaternion((a[3],a[0],a[1],a[2]));n.rotation_mode='QUATERNION';n.rotation_quaternion=(C@q.to_matrix()@C.transposed()).to_quaternion()
  for i,n in enumerate(units):
   if s['attached']:n.parent=tool;n.matrix_basis=Matrix.Translation(xyz((-.0325 if i==0 else .0325,-.002,0)))
   elif s['fall']:n.parent=tote;n.matrix_basis=Matrix.Translation(xyz((-.0325 if i==0 else .0325,s['package_bottom_m']-.62,0)))
   else:n.parent=unit_rest[n][0];n.matrix_basis=unit_rest[n][1]
  bpy.context.view_layer.update();wp,_=physical_body(worker);by={p['name']:p for p in wp};ep,_=collect(scene);tp,_=collect(tool);pp=[p for n in units for p in collect(n)[0]];tp=[p for p in tp if not p['name'].startswith('primary_unit__')];env=[p for p in ep if not p['name'].startswith(('primary_unit__17__','primary_unit__23__'))]
  hits=[]
  for a in tp:
   for b in env+pp+wp:
    if (hit:=penetration(a,b)):hits.append(hit)
  for a in wp+pp:
   for b in env:
    if (hit:=penetration(a,b)):hits.append(hit)
  for a in wp:
   if not a['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R')):continue
   for b in wp:
    if b['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R','upper_sleeve_R')):continue
    if (hit:=penetration(a,b)):hits.append(hit)
  if hits:
   inv=nodes['joint__hand_R'].matrix_world.inverted();print('GRIP_DEBUG '+json.dumps({name:[[min(runtime_xyz(inv@xyz(v))[i] for v in part['verts']),max(runtime_xyz(inv@xyz(v))[i] for v in part['verts'])] for i in range(3)] for name,part in dict(bar=next(p for p in tp if p['name']=='rubber_Tbar'),upper=by['mitten_R_upper_pad'],lower=by['mitten_R_lower_pad']).items()}),flush=True)
  assert not hits,('native penetration',hits)
  mouth(by);links=[]
  for a,b in [('upper_sleeve_R','fore_sleeve_R'),('cuff_R','mitten_R_spine'),('mitten_R_thumb','mitten_R_spine')]+[(a+'_'+side,b+'_'+side) for side in ['L','R'] for a,b in [('trouser_thigh','trouser_shin'),('trouser_shin','boot')]]:
   assert touching(by[a],by[b]),('body connection gap',a,b);links.append([a,b])
  hand=nodes['joint__hand_R'];bar=next(p for p in tp if p['name']=='rubber_Tbar');contact_gaps=[]
  for label,sign in [('upper',1),('lower',-1)]:
   theta=s['angle']+(math.pi if sign<0 else 0);phi=max([(i+.5)*math.pi/16 for i in range(32)],key=lambda a:math.cos(theta-a));point=tool.matrix_world@xyz((0,.148+.02*math.cos(phi),.23+.02*math.sin(phi)));contact_gaps.append(opposed(bar,by['mitten_R_'+label+'_pad'],point))
  if s['attached']:
   for i,n in enumerate(units):
    parts,_=collect(n);x=-.0325 if i==0 else .0325
    for end,sign in [('front',1),('rear',-1)]:
     point=tool.matrix_world@xyz((x,.03,sign*.02));pad=next(p for p in tp if p['name']=='finger_pad_'+end+('_L' if i==0 else '_R'));other=next(p for p in parts if p['bvh'].find_nearest(point)[3]<EPS);contact_gaps.append(opposed(pad,other,point))
  thumb_contact=False
  if s['opening']>1e-6:
   tab=next(p for p in tp if p['name']=='actual_thumb_tab');thumb=by['mitten_R_thumb']
   for v in tab['verts']:
    point=xyz(v)
    if thumb['bvh'].find_nearest(point)[3]>=EPS:continue
    try:gap=opposed(tab,thumb,point)
    except AssertionError:continue
    contact_gaps.append(gap);thumb_contact=True;break
   assert thumb_contact,'thumb does not actually press the button'
  support_contacts=0
  if s['fall'] and s['package_bottom_m']==.64:
   for n in units:
    point=n.matrix_world.translation;up,_=collect(n);candidates=[]
    for a in up:
     h,normal,_,distance=a['bvh'].find_nearest(point)
     if distance>=EPS or normal.dot(xyz((0,-1,0)))<.99:continue
     for b in env:
      hit,on,_,d=b['bvh'].find_nearest(point)
      if d<EPS and on.dot(xyz((0,1,0)))>.99:candidates.append((a,b))
    assert candidates,('no actual tote floor support',n.name,runtime_xyz(point))
    contact_gaps.append(min(opposed(a,b,point) for a,b in candidates));support_contacts+=1
  floor_errors=[]
  for side in ['L','R']:
   lift=s['gait']['feet'][side]['lift'] if s.get('gait') else 0;error=abs(by['boot_'+side]['low'][1]-lift);assert error<EPS,('boot/floor mismatch',side,error);floor_errors.append(error)
  assert min(p['low'][1] for p in wp)>=-EPS
  assert any((not s.get('gait') or s['gait']['feet'][side]['stance']) and abs(by['boot_'+side]['low'][1])<EPS for side in ['L','R']), 'no real supporting foot'
  rows.append(dict(time=f['time'],native_parts=dict(worker=len(wp),tool=len(tp),primary_packages=len(pp),environment=len(env)),actual_contact_checks=len(contact_gaps),thumb_button_contact=thumb_contact,actual_tote_support_contacts=support_contacts,maximum_contact_gap_m=max(contact_gaps),maximum_boot_floor_error_m=max(floor_errors),body_connections=len(links),central_C_mouth_clear=True,source_packages_conserved=True))
  if len(rows)%40==0:print('SMALL_PICK_NATIVE_PROGRESS '+str(f['time']),flush=True)
except Exception as e:
 failure=dict(time=f['time'],error=str(e));print('SMALL_PICK_NATIVE_REJECTED '+json.dumps(failure),flush=True)
for p,h in data['input_hashes'].items():
 if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:failure=dict(error='Input changed during native validation',path=p)
if hashlib.sha256((OUT/'runtime-native-poses.json').read_bytes()).hexdigest()!=pose_sha256:failure=dict(error='Runtime pose file changed during native validation')
for p,h in native_dependencies.items():
 if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:failure=dict(error='Native check dependency changed',path=p)
report=dict(passed=failure is None,native_dependency_sha256=native_dependencies,source_kind='visual_fixture',engine_operation=False,input_hashes=data['input_hashes'],runtime_source_sha256=pose_sha256,actual_native_frames=len(rows),failure=failure,frames=rows,scope='Bounded actual native poses at100ms spacing plus20ms deposit/withdraw and10ms gravity-release samples on closed solids, calibrated2um gate. Not a continuous collision certificate, certified tool capacity, complete warehouse scene or actual engine run. Actual thumb/button and final tote floor contacts are checked when active; whole-clip browser/identity and guide continuity acceptance remain separate.')
if failure:
 history=OUT/'native-rejections.json';records=json.loads(history.read_text(encoding='utf8')) if history.exists() else [];records.append(dict(input_hashes=data['input_hashes'],failure=failure,exact_runtime_frame=f));history.write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
(OUT/'native-path-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
assert failure is None,failure
print('SMALL_PICK_NATIVE_PATH_VERIFIED '+json.dumps(dict(frames=len(rows),contacts=sum(r['actual_contact_checks'] for r in rows))))
