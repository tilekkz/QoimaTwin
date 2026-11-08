"""Admit a bounded original-rig receiver contact; no clip acceptance here."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_standard_carton import collect,triangle_box
from native_clearance import penetration,touching,contains

OUT=ROOT/'assets/v3/iterations/receiver/P05.2';EPS=2e-6
assert bpy.app.background
raw=(OUT/'contact-candidates.json').read_bytes();data=json.loads(raw)
sources=['assets/v3/blender/worker-manual.blend','assets/v3/blender/receiver-workcell-fixture.blend',
         'tools/blender/v3/probe_receiver.py','tools/blender/v3/native_clearance.py']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
reset();cell=append_source(sources[1],'receiver_workcell_root',None)
worker=append_source(sources[0],'worker_base_root',None)
nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive}
env,_=collect(cell);screen=next(p for p in env if p['name']==data['surface']);rows=[];admitted=None
for body in data['bodies']:
 for index,c in enumerate(body['sides']['R']):
  for n,m in rest.items():n.matrix_basis=m
  worker.location=xyz(body['root']);rotate(worker,body['root_euler']);rotate(nodes['joint__torso'],[body['lean'],0,0]);rotate(nodes['joint__head'],body['head'])
  for name,a in c['pose'].items():
   if name=='joint__elbow_swivel_R':nodes[name].rotation_mode='QUATERNION';nodes[name].rotation_quaternion=Matrix.Rotation(a[0],4,xyz(c['axis'])).to_quaternion()
   else:rotate(nodes[name],a)
  bpy.context.view_layer.update();wp,_=physical_body(worker);by={p['name']:p for p in wp}
  hits=[h for a in wp for b in env if (h:=penetration(a,b))]
  active=lambda p:p['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R'))
  hits += [h for a in wp if active(a) for b in wp if not active(b) and b['name']!='upper_sleeve_R' if (h:=penetration(a,b))]
  hand=nodes['joint__hand_R'];point=hand.matrix_world@xyz(c['contact_local']);error=math.dist(runtime_xyz(point),body['target'])
  pad=by['mitten_R_lower_pad'];pad_hit,pad_normal,_,pd=pad['bvh'].find_nearest(point);screen_hit,screen_normal,_,sd=screen['bvh'].find_nearest(point)
  opposed=pd<EPS and sd<EPS and pad_normal.dot(screen_normal)<-.99
  links=all(touching(by[a],by[b]) for a,b in [('upper_sleeve_R','fore_sleeve_R'),('cuff_R','mitten_R_spine')])
  floor=[by['boot_'+s]['low'][1] for s in ['L','R']]
  inverse=hand.matrix_world.inverted();cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0];lo=[cx-.038+EPS,-.068+EPS,.033+EPS];hi=[cx+.038-EPS,-.032-EPS,.06-EPS];mouth_clear=True
  for p in [by['fore_sleeve_R'],by['cuff_R']]:
   vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
   if any(triangle_box([vs[i] for i in t],lo,hi) for t in p['triangles']) or contains(p,runtime_xyz(hand.matrix_world@xyz([(a+b)/2 for a,b in zip(lo,hi)]))):mouth_clear=False
  row=dict(root=body['root'],torso_x=body['lean'],candidate=index,penetrations=hits,opposed_contact=opposed,contact_error_m=error,connections=links,boot_minima_m=floor,C_mouth_clear=mouth_clear)
  rows.append(row)
  if not hits and opposed and links and error<EPS and all(abs(y)<EPS for y in floor) and mouth_clear:
   admitted=dict(body={k:v for k,v in body.items() if k!='sides'},candidate=c,native=row);break
 if admitted:break
for p,h in hashes.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
report=dict(passed_endpoint=admitted is not None,source_kind='visual_pose_candidate',engine_operation=False,
            input_hashes=hashes,candidate_sha256=hashlib.sha256(raw).hexdigest(),tested=len(rows),results=rows,
            admitted=admitted,scope='Bounded endpoint and analytical short-approach candidates only. Full interpolation, modes, resource lifecycle and images remain separate.')
(OUT/'native-contact-search.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('RECEIVER_CONTACT_SEARCH '+json.dumps(dict(passed=admitted is not None,tested=len(rows),last=rows[-1] if rows else None)))
assert admitted is not None,'No native endpoint admitted in this bounded query'
