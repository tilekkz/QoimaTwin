"""Synthetic mechanical drive refinement: real thumb tab, hollow sheath and pull wire."""
import math
import bpy,bmesh
from mathutils import Vector
from v3_common import xyz,runtime_xyz,cylinder,group,beam
from build_long_rack import block
from build_small_pick_source import rotate

HORN=.10;PIVOT_Y=.123;MOUTH_GAP=.016;CABLE_X=-.11
def cap_y(u):return .1238+math.sqrt(.05**2-(.036+.007*u)**2)
def lever_angle(u):
 target=MOUTH_GAP+cap_y(0)-cap_y(u);lo=0;hi=.18
 for _ in range(44):
  a=(lo+hi)/2;length=math.hypot(HORN*(1-math.cos(a)),MOUTH_GAP+HORN*math.sin(a))
  if length<target:lo=a
  else:hi=a
 return 0 if u==0 else (lo+hi)/2

def mesh_obj(name,verts,faces,mat,parent):
 mesh=bpy.data.meshes.new(name+'_mesh');mesh.from_pydata([xyz(v) for v in verts],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat);return obj

def annulus_y(name,centre,inner,outer,lo,hi,mat,parent,n=16):
 x,_,z=centre;verts=[(x+r*math.cos(i*math.tau/n),y,z+r*math.sin(i*math.tau/n)) for y,r in[(lo,inner),(lo,outer),(hi,outer),(hi,inner)] for i in range(n)]
 faces=[(j*n+i,j*n+(i+1)%n,((j+1)%4)*n+(i+1)%n,((j+1)%4)*n+i) for j in range(4) for i in range(n)]
 return mesh_obj(name,verts,faces,mat,parent)

def boolean(obj,operand,kind):
 bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
 mod=obj.modifiers.new('Actual fitted drive bore' if kind=='DIFFERENCE' else 'Welded fixed bearing','BOOLEAN');mod.operation=kind;mod.solver='EXACT';mod.object=operand;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(operand,do_unlink=True)

def path_points():
 a=PIVOT_Y-HORN
 segments=[
  [(CABLE_X,a,.214),(CABLE_X,a,.20),(CABLE_X,.10,.20),(CABLE_X,.13,.19)],
  [(CABLE_X,.13,.19),(CABLE_X,.13,.14),(CABLE_X,.13,.08),(CABLE_X,.13,.03)],
  [(CABLE_X,.13,.03),(CABLE_X,.13,.01),(-.06,.11,-.015),(-.03,.11,-.015)],
  [(-.03,.11,-.015),(-.01,.11,-.015),(-.01,.112,0),(-.01,.124,0)],
  [(-.01,.124,0),(-.01,.131,0),(-.01,.138,0),(-.01,.145,0)]]
 result=[]
 for k,segment in enumerate(segments):
  p=[Vector(v) for v in segment]
  for i in range(9):
   if k and i==0:continue
   t=i/8;result.append(p[0]*(1-t)**3+3*p[1]*t*(1-t)**2+3*p[2]*t*t*(1-t)+p[3]*t**3)
 return result

def path_tube(name,points,outer,inner,mat,parent,sides=8):
 tangent=[(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized() for i in range(len(points))];tangent[0]=Vector((0,0,-1));tangent[-1]=Vector((0,1,0));normal=Vector((1,0,0));prev=tangent[0];verts=[]
 radii=[outer] if inner is None else [outer,inner]
 for i,p in enumerate(points):
  normal=prev.rotation_difference(tangent[i])@normal;normal=(normal-tangent[i]*normal.dot(tangent[i])).normalized();binormal=tangent[i].cross(normal).normalized();prev=tangent[i]
  for r in radii:
   for j in range(sides):verts.append(list(p+r*(math.cos(j*math.tau/sides)*normal+math.sin(j*math.tau/sides)*binormal)))
 stride=sides*len(radii);faces=[]
 for i in range(len(points)-1):
  for k in range(len(radii)):
   for j in range(sides):faces.append((i*stride+k*sides+j,i*stride+k*sides+(j+1)%sides,(i+1)*stride+k*sides+(j+1)%sides,(i+1)*stride+k*sides+j))
 if inner is None:faces += [tuple(reversed(range(sides))),tuple((len(points)-1)*stride+j for j in range(sides))]
 else:
  for i in[0,len(points)-1]:
   for j in range(sides):faces.append((i*stride+j,i*stride+(j+1)%sides,i*stride+sides+(j+1)%sides,i*stride+sides+j))
 return mesh_obj(name,verts,faces,mat,parent)

def bare_vertices(rear,angle=0,drop=0):
 points=[(CABLE_X,PIVOT_Y-HORN*math.cos(angle),.23+HORN*math.sin(angle)),(CABLE_X,PIVOT_Y-HORN,.214)] if rear else [(-.01,.1458,0),(-.01,cap_y(0)-.002-drop,0)]
 return [(p[0]+.0005*math.cos(i*math.tau/8),p[1]+(.0005*math.sin(i*math.tau/8) if rear else 0),p[2]+(0 if rear else .0005*math.sin(i*math.tau/8))) for p in points for i in range(8)]

def add_drive(root,steel,rubber,teal,orange):
 nodes={o.name:o for o in root.children_recursive};lever=nodes['joint__squeeze_lever'];lever.location=xyz((0,PIVOT_Y,.23))
 for side in['L','R']:
  bearing=nodes['lever_bearing_'+side];bearing.location.z-=.002;bearing.data.materials[0]=steel
  arm=nodes['fixed_side_arm_'+side];boolean(arm,bearing,'UNION')
  x=-.075 if side=='L' else .075;cut=cylinder('QA_cut_axle_'+side,(x,PIVOT_Y,.23),.0021,.022,steel,None,axis='X',vertices=32);boolean(arm,cut,'DIFFERENCE')
 cylinder('actual_lever_axle',(-.0155,0,0),.002,.193,steel,lever,axis='X',vertices=32)
 for sign in[-1,1]:cylinder('lever_thrust_cap_'+str(sign),(sign*.0825,0,0),.0035,.003,orange,lever,axis='X',vertices=16)
 block('lever_pull_horn',[CABLE_X-.002,-HORN,-.002],[CABLE_X+.002,0,.002],steel,lever,0)
 # Radial button stays outside the two finger pads; its support fits a real
 # rubber-grip pocket, instead of occupying the thumb/cuff space on release.
 grip=Vector((.007,-.05,.05));thumb=Vector((-.040,-.026,.050));theta=math.pi*5/8
 delta=thumb-grip;point=Vector((delta.x,.148+delta.y*math.cos(theta)-delta.z*math.sin(theta),.23+delta.y*math.sin(theta)+delta.z*math.cos(theta)))
 normal=Vector((0,math.cos(theta),math.sin(theta)));centre=point-normal*.0005
 tab=group('thumb_tab_frame',lever,tuple(centre-Vector((0,PIVOT_Y,.23))));rotate(tab,(theta,0,0));plate=block('actual_thumb_tab',[-.002,-.0005,-.003],[.002,.0005,.003],orange,tab,0)
 base=Vector((-.047,0,0));end=point-normal*.001-Vector((0,PIVOT_Y,.23))
 support=beam('QA_thumb_button_stem',base,end,.0012,orange,lever);boolean(plate,support,'UNION')
 cut=block('QA_actual_button_pocket',[-.051,.118,.218],[-.043,.158,.260],steel,None,0);boolean(nodes['rubber_Tbar'],cut,'DIFFERENCE')
 eye=nodes['joint__plunger'];block('cable_cap_eye',[-.011,-.002,-.002],[-.006,.002,.002],steel,eye,0)
 cut=cylinder('QA_cut_crosshead',(-.01,.134,0),.002,.022,steel,None,axis='Y',vertices=24);boolean(nodes['crosshead_L'],cut,'DIFFERENCE')
 annulus_y('captured_cable_ferrule',(-.01,0,0),.00155,.004,.139,.145,teal,root)
 annulus_y('actual_cable_terminal_washer',(-.01,0,0),.0008,.004,.145,.1458,steel,root)
 points=path_points();path_tube('real_hollow_mechanical_sheath',points,.0015,.0008,rubber,root)
 path_tube('captured_continuous_inner_wire',points,.0005,None,steel,root,6)
 cylinder('wire_through_terminal_washer',(-.01,.1454,0),.0005,.0008,steel,root,axis='Y',vertices=8)
 for index,z in enumerate([.16,.10]):
  x=CABLE_X;bottom=.148-.02*math.cos(math.pi/32)
  block('cable_standoff_'+str(index),[x-.003,.124,z-.002],[-.081,bottom,z+.002],teal,root,0)
  for label,lo,hi in [('L',[x-.003,bottom,z-.002],[x-.0015,.1319,z+.002]),('R',[x+.0015,bottom,z-.002],[x+.003,.1319,z+.002]),('bottom',[x-.0015,bottom,z-.002],[x+.0015,.1285,z+.002]),('top',[x-.0015,.1315,z-.002],[x+.0015,.1319,z+.002])]:block('real_cable_clip_'+str(index)+'_'+label,lo,hi,teal,root,0)
 faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
 rear=mesh_obj('exposed_rear_pull_wire',bare_vertices(True),faces,steel,root);rear.shape_key_add(name='Basis')
 a=lever_angle(1)
 for keyname,angle in [('pull_y',a),('pull_z',a)]:
  key=rear.shape_key_add(name=keyname);vertices=bare_vertices(True,angle)
  for i,(v,p) in enumerate(zip(key.data,vertices)):
   base=list(bare_vertices(True)[i]);axis=1 if keyname=='pull_y' else 2;base[axis]=p[axis];v.co=xyz(base)
 front=mesh_obj('exposed_front_pull_wire',bare_vertices(False),faces,steel,root);front.shape_key_add(name='Basis');key=front.shape_key_add(name='plunger_down')
 for v,p in zip(key.data,bare_vertices(False,drop=cap_y(0)-cap_y(1))):v.co=xyz(p)
 root['manual_drive_version']='v3_radial_button_Bowden';root['rear_horn_radius_m']=HORN;root['lever_axis_y_m']=PIVOT_Y;root['maximum_lever_angle_rad']=a;lever['rotation_delta_range_rad']=[-.18,0]
 root['extended_drive_envelope_max_xyz_m']=[.22,.168,.316];root['force_transmission_scope']='Synthetic cable/spring kinematics only; no certified capacity or engine equipment admission.'

def set_drive(root,u):
 nodes={o.name:o for o in root.children_recursive};a=lever_angle(u);rotate(nodes['joint__squeeze_lever'],(-a,0,0));maximum=lever_angle(1)
 rear=nodes['exposed_rear_pull_wire'].data.shape_keys.key_blocks;rear['pull_y'].value=(1-math.cos(a))/(1-math.cos(maximum));rear['pull_z'].value=math.sin(a)/math.sin(maximum)
 nodes['exposed_front_pull_wire'].data.shape_keys.key_blocks['plunger_down'].value=(cap_y(0)-cap_y(u))/(cap_y(0)-cap_y(1))
