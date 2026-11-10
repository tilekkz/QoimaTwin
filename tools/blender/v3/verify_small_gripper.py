"""P03.5.3.2 native guides, real package/hand contacts and prepared source clearance."""
import json,sys,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import closest_point_on_tri
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz,group,finish
from build_small_gripper import opening,plunger_y,Y_CARRIER,LINK
from build_small_pick_source import rotate,parent_at_rest
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect,empty_box
from native_clearance import touching as connected
assert bpy.app.background
EPS=2e-6;OUT=ROOT/'assets/v3/iterations/small-package-gripper/P03.5.3.2'
SOURCES=['assets/v3/blender/worker-manual.blend','assets/v3/blender/picker-pick-source-fixture.blend','assets/v3/blender/small-case-open-partial.blend','docs/v3/contract-proposals/cargo-catalog-v3.json']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}

from native_clearance import penetration as penetrates

def opposed(a,b,point):
 candidates=[]
 for part in[a,b]:
  hits=[]
  for tri in part['triangles']:
   v=[xyz(part['verts'][i]) for i in tri];hit=closest_point_on_tri(point,*v)
   if (hit-point).length<EPS:hits.append((hit,(v[1]-v[0]).cross(v[2]-v[0]).normalized()))
  assert hits,(part['name'],'contact gap',runtime_xyz(point));candidates.append(hits)
 good=[(p,q) for p in candidates[0] for q in candidates[1] if p[1].dot(q[1])<-.99 and (p[0]-q[0]).length<EPS]
 assert good,('normals not opposed',a['name'],b['name']);p,q=min(good,key=lambda h:(h[0][0]-h[1][0]).length)
 return dict(a=a['name'],b=b['name'],point=runtime_xyz(point),gap_m=(p[0]-q[0]).length,normal_dot=p[1].dot(q[1]))

reset();scene=append_source(SOURCES[1],'picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-small-pick.blend','worker_base_root',None);rotate(worker,(0,math.pi,0));nodes={o.name:o for o in worker.children_recursive};rest={o:o.matrix_basis.copy() for o in worker.children_recursive}
tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None,(.945,1.1245,.32))
bpy.context.view_layer.update()
source_nodes={o.name:o for o in scene.children_recursive};units=[source_nodes['primary_unit__17'],source_nodes['primary_unit__23']];unit_rest={o:o.matrix_world.copy() for o in units}
rows=[]
for label,raised,u in [('open_pick',False,1),('quarter_pick',False,.75),('half_pick',False,.5),('near_closed_pick',False,.25),('closed_pick',False,0),('closed_raised',True,0),('closed_pick_fixture',False,0)]:
 for o,m in rest.items():o.matrix_basis=m
 folder='gripper-raised-reach-probe' if raised else 'gripper-reach-probe';filename='clear-candidate.json' if raised else 'clear-candidate-body5.json'
 pose=json.loads((ROOT/'assets/v3/iterations/worker-base/P03.5.3'/folder/filename).read_text(encoding='utf8'))
 assert pose['body_index']==5
 worker.location=xyz(pose['root'])
 for name,angles in pose['pose'].items():
  if name.startswith('joint__elbow_swivel_'):
   nodes[name].rotation_mode='QUATERNION';nodes[name].rotation_quaternion=Matrix.Rotation(angles[0],4,xyz(pose['twist_axis_runtime'])).to_quaternion()
  else:rotate(nodes[name],angles)
 # Actual32-facet bar apothem, rather than a guessed circular envelope.
 close=(.045-2*.02*math.cos(math.pi/32))/2
 nodes['joint__finger_upper_R'].location=xyz((0,-close,0));nodes['joint__finger_lower_R'].location=xyz((0,close,0));nodes['joint__finger_thumb_R'].location=xyz((0,0,0))
 tool.location=xyz((.945,1.1245+(.14 if raised else 0),.32));opening(tool,u)
 for unit,m in unit_rest.items():unit.matrix_world=Matrix.Translation(xyz((0,.14 if raised else 0,0)))@m
 nodes['joint__finger_thumb_R'].location=xyz((0,0,-.005));rotate(nodes['joint__thumb_press_R'],(0,0,0))
 bpy.context.view_layer.update();tp,_=collect(tool);wp,_=physical_body(worker);bytool={p['name']:p for p in tp};hand=nodes['joint__hand_R'];inverse=hand.matrix_world.inverted();thumb_contact=None;thumb_press=0
 if not raised:
  tab=bytool['actual_thumb_tab'];tab_points=[(Vector(runtime_xyz(inverse@xyz(v))),xyz(v)) for v in tab['verts']]
  thumb=next(p for p in wp if p['name']=='mitten_R_thumb');minimum=min(runtime_xyz(inverse@xyz(v))[1] for v in thumb['verts']);origin=Vector(runtime_xyz(inverse@nodes['joint__thumb_press_R'].matrix_world.translation));offset=minimum-origin.y
  def gap(a):return max((v.y-origin.y)*math.cos(a)+(v.z-origin.z)*math.sin(a)-offset for v,_ in tab_points)
  assert gap(0)<=EPS and gap(.06)>=-EPS,('thumb press range',gap(0),gap(.06))
  lo=0;hi=.06
  if gap(0)>=0:hi=0
  else:
   for _ in range(44):
    a=(lo+hi)/2
    if gap(a)<0:lo=a
    else:hi=a
  thumb_press=(lo+hi)/2
 rotate(nodes['joint__thumb_press_R'],(thumb_press,0,0));thumb_travel=-.005
 bpy.context.view_layer.update();wp,_=physical_body(worker);ep,_=collect(scene);byworker={p['name']:p for p in wp}
 if not raised:
  vals=[(v.y-origin.y)*math.cos(thumb_press)+(v.z-origin.z)*math.sin(thumb_press)-offset for v,_ in tab_points];maximum=max(vals);contact_points=[p for (_,p),v in zip(tab_points,vals) if v>maximum-EPS];thumb_point=sum(contact_points,Vector())/len(contact_points);thumb_contact=opposed(tab,byworker['mitten_R_thumb'],thumb_point)
 collisions=[]
 for a in tp:
  for b in ep+wp:
   if penetrates(a,b):collisions.append([a['name'],b['name']])
 for a in wp:
  for b in ep:
   if penetrates(a,b):collisions.append([a['name'],b['name']])
 for a in wp:
  if not a['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R')):continue
  for b in wp:
   if b['name'].startswith(('fore_sleeve_R','cuff_R','mitten_R','upper_sleeve_R')):continue
   if penetrates(a,b):collisions.append([a['name'],b['name']])
 contacts=[]
 if u==0:
  for unit,x in zip(units,[-.0325,.0325]):
   pp,_=collect(unit)
   for end,sign in [('front',1),('rear',-1)]:
    point=tool.matrix_world@xyz((x,.030,sign*.02));pad=bytool['finger_pad_'+end+('_L' if x<0 else '_R')]
    candidates=[]
    for p in pp:
     h,n,_,d=p['bvh'].find_nearest(point)
     if d<EPS:candidates.append(p)
    assert candidates,('missing actual package face',unit.name,end,runtime_xyz(point),[(p['name'],p['bvh'].find_nearest(point)[3],runtime_xyz(p['bvh'].find_nearest(point)[0])) for p in pp])
    contacts.append(opposed(pad,candidates[0],point))
 centre=nodes['anchor_hand_grip_R'].matrix_world.translation;bar=bytool['rubber_Tbar'];hand_contacts=[]
 for pad_label,sign in[('upper',1),('lower',-1)]:
  direction=(hand.matrix_world.to_3x3()@xyz((0,sign,0))).normalized()
  point=tool.matrix_world@xyz((0,.148,.23))+direction*(.02*math.cos(math.pi/32))
  hand_contacts.append(opposed(bar,byworker['mitten_R_'+pad_label+'_pad'],point))
 links={joint_label:connected(byworker[a],byworker[b]) for joint_label,a,b in[('elbow','upper_sleeve_R','fore_sleeve_R'),('wrist','cuff_R','mitten_R_spine')]}
 links['thumb']=connected(byworker['mitten_R_thumb'],byworker['mitten_R_spine'])
 inverse=hand.matrix_world.inverted();local=[]
 for p in[byworker['fore_sleeve_R'],byworker['cuff_R']]:
  vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
  local.append(p|dict(verts=vs,low=[min(v[i] for v in vs) for i in range(3)],high=[max(v[i] for v in vs) for i in range(3)],bvh=BVHTree.FromPolygons([xyz(v) for v in vs],p['triangles'],all_triangles=True)))
 cx=runtime_xyz(nodes['anchor_hand_grip_R'].location)[0];empty_box(local,[cx-.038,-.068,.033],[cx+.038,-.032,.06],'actual cuff/forearm outside central C opening')
 floor_error=max(abs(byworker['boot_'+side]['low'][1]) for side in ['L','R']);assert floor_error<EPS
 lengths=[]
 for name in['exposed_rear_pull_wire','exposed_front_pull_wire']:
  vs=[Vector(v) for v in bytool[name]['verts']];ends=[sum(vs[i:i+8],Vector())/8 for i in[0,8]];lengths.append((ends[0]-ends[1]).length)
 cable_sum=sum(lengths);assert abs(cable_sum-(.016+plunger_y(0)-.002-.1458))<EPS,('cable continuity',cable_sum)
 rows.append(dict(label=label,raised=raised,opening=u,collisions=collisions,actual_package_contacts=contacts,actual_hand_bar_contacts=hand_contacts,actual_thumb_trigger_contact=thumb_contact,manual_thumb_translation_m=thumb_travel,manual_thumb_press_rad=thumb_press,exposed_cable_length_sum_m=cable_sum,body_links=links,maximum_boot_floor_error_m=floor_error,own_forearm_cuff_clear_of_central_hand_opening=True,hand_closing_travel_m=close,grip_error_m=math.dist(runtime_xyz(centre),pose['target'])))
 print('GRIPPER_NATIVE_STATE '+json.dumps(rows[-1]),flush=True)
 assert not collisions,(label,'native penetration',collisions)
 assert all(links.values())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
report=dict(task_id='P03.5.3.2',passed=True,source_hashes=hashes,original_source_files_unchanged=True,worker_derivative='assets/v3/blender/worker-small-pick.blend',worker_derivative_sha256=hashlib.sha256((ROOT/'assets/v3/blender/worker-small-pick.blend').read_bytes()).hexdigest(),states=rows,body_index=5,actor_count=1,tool_count=1,primary_contents=4,picked_source_ids=['primary_unit__17','primary_unit__23'],scope='Native prepared pose geometry/contact including actual thumb-driven cable refinement and separate raw-body-preserving thumb derivative. Tool starts held at the external bar; no acquisition, transition path, carry, release, actual engine admission or clip completion asserted.')
fixture=group('small_gripper_contact_fixture_root');fixture['reference_id']='P03_SMALL_GRIPPER_REF';fixture['source_kind']='visual_fixture';fixture['engine_operation']=False;fixture['operational_admission']=False
fixture['scope']='Prepared static geometry/contact QA only, starts with one tool held and four original source packages. No pick clip or engine operation.'
fixture['fixture_actor_id']='P01';fixture['employee_count']=1;fixture['primary_package_count']=4
for obj in[scene,worker,tool]:parent_at_rest(obj,fixture)
stats=finish('small-gripper-contact-fixture',fixture,preserve_shape_keys=True);report['contact_fixture_glb_sha256']=stats['sha256']
(OUT/'native-contacts.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('SMALL_GRIPPER_CONTACTS_VERIFIED '+json.dumps(dict(states=len(rows),package_contacts=sum(len(r['actual_package_contacts']) for r in rows),hand_contacts=sum(len(r['actual_hand_bar_contacts']) for r in rows))))
