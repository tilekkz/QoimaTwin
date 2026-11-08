"""P03.5.3.2 metric compact manual gripper; isolated background source/export."""
import json,math,sys,hashlib
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,pivot,anchor,material,finish,xyz,runtime_xyz,cylinder
from build_long_rack import block
from build_standard_carton import collect,empty_box
from native_clearance import connected_parts as connected
from build_small_pick_source import rotate
from small_gripper_drive import add_drive,set_drive
EPS=2e-6
OUT=ROOT/'assets/v3/iterations/small-package-gripper/P03.5.3.2'
Y_CARRIER=.1238;LINK=.05

def plunger_y(opening):
 return Y_CARRIER+math.sqrt(LINK**2-(.036+.007*opening)**2)

def mesh_object(name,verts,faces,mat,parent):
 mesh=bpy.data.meshes.new(name+'_mesh');mesh.from_pydata([xyz(v) for v in verts],[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat);return obj

def bar(mat,root):
 n=32;r=.02;verts=[(x,.148+r*math.cos((i+.5)*math.tau/n),.23+r*math.sin((i+.5)*math.tau/n)) for x in [-.1,.1] for i in range(n)]
 faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 return mesh_object('rubber_Tbar',verts,faces,mat,root)

def spring_vertices(cap_y):
 turns=3;rad=.004;wire=.0006;n=96;sides=8;lo=.1406;hi=cap_y-.0026
 for _ in range(6):
  pitch=(hi-lo)/(turns*math.tau);normal_y=rad/math.hypot(rad,pitch);lo=.14+wire*normal_y;hi=cap_y-.002-wire*normal_y
 verts=[]
 for i in range(n+1):
  a=i/n*turns*math.tau;centre=Vector((rad*math.cos(a),lo+(hi-lo)*i/n,rad*math.sin(a)))
  tangent=Vector((-rad*math.sin(a),(hi-lo)/(turns*math.tau),rad*math.cos(a))).normalized();normal=Vector((math.cos(a),0,math.sin(a)));binormal=tangent.cross(normal).normalized()
  for j in range(sides):verts.append(list(centre+wire*(math.cos(j*math.tau/sides)*normal+math.sin(j*math.tau/sides)*binormal)))
 return verts

def annular_seat(name,mat,root):
 n=16;verts=[(r*math.cos(i*math.tau/n),y,r*math.sin(i*math.tau/n)) for y,r in[(.139,.0032),(.139,.006),(.14,.006),(.14,.0032)] for i in range(n)]
 faces=[]
 for k in range(4):
  for i in range(n):faces.append((k*n+i,k*n+(i+1)%n,((k+1)%4)*n+(i+1)%n,((k+1)%4)*n+i))
 return mesh_object(name,verts,faces,mat,root)

def build():
 root=group('small-package-gripper');root['role']='manual_equipment_template';root['reference_id']='P03_SMALL_GRIPPER_REF';root['preserve_articulation']=True
 root['source_kind']='synthetic_design';root['engine_operation']=False;root['operational_admission']=False;root['mass_kg']=.65;root['stock_instances']=0
 root['design_scope']='Two35g primary packages only. Synthetic spring/linkage concept; no certified capacity/ergonomic or engine admission claim.'
 root['unit_pair_centre_local_m']=[0,.018,0];root['jaw_gap_closed_open_m']=[.04,.054]
 root['mechanism_drive']='Single absolute normalized opening. Opposed Z slides7mm each;50mm pin links; plunger from actual fixed link length; coil morph follows plunger.'
 steel=material('V3_GRIPPER_silver','#B3BDBA',.62,.25);teal=material('V3_GRIPPER_petrol','#2E7376');rubber=material('V3_GRIPPER_rubber','#293D46');orange=material('V3_GRIPPER_lever','#F28C28')
 for m in[steel,teal,rubber,orange]:m.use_backface_culling=True
 top=.148-.02*math.cos(math.pi/32)
 for side,x in [('L',-.075),('R',.075)]:block('fixed_side_arm_'+side,[x-.006,top-.006,-.06],[x+.006,top,.23],steel,root,0)
 bar(rubber,root)
 for side,lo,hi in[('L',-.081,-.007),('R',.007,.081)]:block('crosshead_'+side,[lo,top,-.007],[hi,.139,.007],teal,root,0)
 for label,lo,hi in [('L',[-.007,top,-.007],[-.004,.139,.007]),('R',[.004,top,-.007],[.007,.139,.007]),('F',[-.004,top,.004],[.004,.139,.007]),('B',[-.004,top,-.007],[.004,.139,-.004])]:block('real_centre_guide_'+label,lo,hi,teal,root,0)
 for end,z in [('front',.056),('rear',-.056)]:
  block('fixed_rail_end_'+end,[-.069,.113,z-.004],[.069,.125,z+.004],teal,root,0)
 for side,x in [('L',-.05),('R',.05)]:block('captured_square_rail_'+side,[x-.003,.116,-.052],[x+.003,.122,.052],steel,root,0)
 for end,sign in [('front',1),('rear',-1)]:
  jaw=pivot('joint__jaw_'+end,(0,0,0),root,'Z');jaw['joint_mode']='opposed_jaw_slide';jaw['signed_translation_range_m']=[0,.007*sign]
  z=sign*.036
  block('jaw_crossbar_'+end,[-.045,.1138,z-.006],[.045,.1238,z+.006],steel,jaw,0)
  for side,x in [('L',-.05),('R',.05)]:
   # Real6.4mm square bore around6mm rail. The inner TOP rests on the rail;
   # .4mm is left below, .2mm at each side. No solid fake sleeve.
   for label,lo,hi in [('L',[x-.005,.1138,z-.006],[x-.0032,.1238,z+.006]),('R',[x+.0032,.1138,z-.006],[x+.005,.1238,z+.006]),('top',[x-.0032,.122,z-.006],[x+.0032,.1238,z+.006]),('bottom',[x-.0032,.1138,z-.006],[x+.0032,.1156,z+.006])]:block('jaw_sleeve_'+end+'_'+side+'_'+label,lo,hi,teal,jaw,0)
  for side,x in [('L',-.0325),('R',.0325)]:
   zlo,zhi=sorted([sign*.032,sign*.04]);block('finger_shaft_'+end+'_'+side,[x-.01,0,zlo],[x+.01,.1138,zhi],steel,jaw,0)
   zlo,zhi=sorted([sign*.020,sign*.032]);block('finger_pad_'+end+'_'+side,[x-.01,0,zlo],[x+.01,.036,zhi],rubber,jaw,.0003)
   anchor('anchor_pad_'+end+'_'+side,(x,.018,sign*.02),jaw,'actual_primary_package_face_contact')
  cylinder('jaw_link_pin_'+end,(0,Y_CARRIER,z),.003,.016,orange,jaw,axis='X',vertices=16)
  link=pivot('joint__link_'+end,(0,plunger_y(0),0),root,'X');link['joint_mode']='closed50mm_link';link['link_length_m']=LINK
  block('link_rod_'+end,[-.002,-LINK,-.0015],[.002,0,.0015],steel,link,0)
  rotate(link,(-math.atan2(z,plunger_y(0)-Y_CARRIER),0,0))
 cap=pivot('joint__plunger',(0,plunger_y(0),0),root,'Y');cap['joint_mode']='linkage_plunger';cap['absolute_closed_open_y_m']=[plunger_y(0),plunger_y(1)]
 cylinder('plunger_stem',(0,-.016,0),.003,.028,steel,cap,axis='Y',vertices=16)
 block('plunger_cap',[-.006,-.002,-.006],[.006,.002,.006],teal,cap,0)
 cylinder('plunger_link_pin',(0,0,0),.003,.018,orange,cap,axis='X',vertices=16)
 annular_seat('real_annular_spring_seat',steel,root)
 n=96;sides=8;faces=[tuple(reversed(range(sides))),tuple(n*sides+i for i in range(sides))]
 faces += [(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for i in range(n) for j in range(sides)]
 spring=mesh_object('continuous_compression_spring',spring_vertices(plunger_y(0)),faces,steel,root)
 spring.shape_key_add(name='Basis');key=spring.shape_key_add(name='jaw_open')
 for vertex,point in zip(key.data,spring_vertices(plunger_y(1))):vertex.co=xyz(point)
 lever=pivot('joint__squeeze_lever',(0,.125,.23),root,'X');lever['joint_mode']='synthetic_squeeze_linkage';lever['rotation_delta_range_rad']=[0,.18]
 # Short paddle below the grip, with end bearings on the fixed side arms.
 block('squeeze_paddle',[-.065,-.004,-.007],[.065,0,.007],orange,lever,.0005)
 for side,x in [('L',-.07),('R',.07)]:cylinder('lever_bearing_'+side,(x,.125,.23),.004,.01,teal,root,axis='X',vertices=16)
 anchor('anchor_handle_centre',(0,.148,.23),root,'existing_hand_axis_not_cargo_attachment')
 anchor('anchor_package_pair_centre',(0,.018,0),root,'pair_centre_below_bridge')
 anchor('anchor_tool_tip_origin',(0,0,0),root,'four_finger_tip_plane')
 root['reference_targets_sha256']=hashlib.sha256((ROOT/'assets/references/v3/p03-small-gripper.targets.json').read_bytes()).hexdigest()
 add_drive(root,steel,rubber,teal,orange)
 return root

def opening(root,u):
 assert 0<=u<=1
 nodes={o.name:o for o in root.children_recursive}
 for end,sign in [('front',1),('rear',-1)]:
  nodes['joint__jaw_'+end].location=xyz((0,0,sign*.007*u))
  nodes['joint__link_'+end].location=xyz((0,plunger_y(u),0));rotate(nodes['joint__link_'+end],(-math.atan2(sign*(.036+.007*u),plunger_y(u)-Y_CARRIER),0,0))
 nodes['joint__plunger'].location=xyz((0,plunger_y(u),0));nodes['joint__squeeze_lever'].rotation_mode='QUATERNION';rotate(nodes['joint__squeeze_lever'],(.18*u,0,0))
 nodes['continuous_compression_spring'].data.shape_keys.key_blocks['jaw_open'].value=(plunger_y(0)-plunger_y(u))/(plunger_y(0)-plunger_y(1))
 set_drive(root,u)
 bpy.context.view_layer.update()

def verify(root):
 from native_clearance import penetration as penetrates
 results=[]
 for u in [0,.25,.5,.75,1]:
  opening(root,u);parts,_=collect(root)
  lo=[min(p['low'][i] for p in parts) for i in range(3)];hi=[max(p['high'][i] for p in parts) for i in range(3)]
  dimensions=[hi[i]-lo[i] for i in range(3)]
  assert .2-EPS<=dimensions[0]<=.22+EPS and abs(dimensions[1]-.168)<.0002 and .31-EPS<=dimensions[2]<=.316+EPS,(u,lo,hi)
  bore_parts=[p for p in parts if not p['name'].startswith('captured_square_rail_')]
  for end,sign in [('front',1),('rear',-1)]:
   for x in[-.05,.05]:empty_box(bore_parts,[x-.0031,.1161,sign*(.036+.007*u)-.0059],[x+.0031,.1219,sign*(.036+.007*u)+.0059],'actual hollow sleeve bore excluding captured rail')
  empty_box([p for p in parts if p['name']!='plunger_stem'],[-.0035,.129,-.0035],[.0035,.138,.0035],'actual open central plunger bore')
  named={p['name']:p for p in parts};sheath=named['real_hollow_mechanical_sheath']
  cable_hits=[hit for p in parts if p is not sheath and (hit:=penetrates(sheath,p))];assert not cable_hits,(u,'mechanical sheath/tool penetration',cable_hits)
  assert not penetrates(named['actual_thumb_tab'],named['rubber_Tbar']),(u,'button support leaves actual grip pocket')
  links=connected(parts)
  results.append(dict(opening=u,closed_parts=len(parts),dimensions_xyz_m=[hi[i]-lo[i] for i in range(3)],connected_pairs=len(links),gap_m=.04+.014*u,plunger_y_m=plunger_y(u),actual_sheath_clear_of_other_tool_solids=True,actual_button_support_fits_real_grip_pocket=True))
 opening(root,0)
 return results

if __name__=='__main__':
 assert bpy.app.background
 OUT.mkdir(parents=True,exist_ok=True);reset();root=build();states=verify(root)
 profiles=[]
 for i in range(9):
  opening(root,i/8);parts,_=collect(root);profiles.append(dict(opening=i/8,parts=[dict(name=p['name'],vertices=p['verts']) for p in parts]))
 (OUT/'native-mechanism-profiles.json').write_text(json.dumps(dict(states=profiles,units='m',scope='Actual evaluated native geometry including coil morph and all rigid mechanism parts.'),separators=(',',':'))+'\n',encoding='utf8')
 opening(root,0);stats=finish('small-package-gripper',root,preserve_shape_keys=True)
 report=dict(task_id='P03.5.3.2',geometry_states=states,glb_sha256=stats['sha256'],reference_id='P03_SMALL_GRIPPER_REF',scope='Tool template geometry only. Actual source/worker contact and full motion are separate native gates; no certified or engine equipment admission.')
 (OUT/'geometry-states.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 print('SMALL_GRIPPER_BUILT '+json.dumps(report))
