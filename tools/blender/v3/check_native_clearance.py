"""Analytical positive/negative calibration, no asset export or warehouse data change."""
import sys,json,math
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,material,cylinder
from build_long_rack import block
from build_small_pick_source import rotate
from build_standard_carton import collect
from small_gripper_drive import annulus_y
from native_clearance import penetration,solid_angle,faces,sub,dot,cross,length
from build_small_gripper import bar
from v3_common import group as frame
assert bpy.app.background
reset();mat=material('QA_clearance','#293D46');rows=[]
def case(label,first,second,expected):
 a=collect(first)[0][0];b=collect(second)[0][0];result=penetration(a,b);assert bool(result)==expected,(label,result);rows.append(dict(case=label,expected_penetration=expected,result=result))
a=group('QA_A');block('A',[0,0,0],[1,1,1],mat,a,0)
for label,lo,hi,expected in [('touching',[1,0,0],[2,1,1],False),('ten_mm_overlap',[.99,0,0],[1.99,1,1],True),('half_um_contact_budget',[.9999995,0,0],[1.9999995,1,1],False),('ten_um_penetration',[.99999,0,0],[1.99999,1,1],True),('identical',[0,0,0],[1,1,1],True),('contained',[.2,.2,.2],[.4,.4,.4],True),('outside',[1.01,0,0],[2.01,1,1],False)]:
 b=group('QA_'+label);block(label,lo,hi,mat,b,0);case(label,a,b,expected)
h=group('QA_cross_horizontal');block('cross_horizontal',[-1,-.01,-.01],[1,.01,.01],mat,h,0);v=group('QA_cross_vertical');block('cross_vertical',[-.01,-1,-.01],[.01,1,.01],mat,v,0);case('crossing_thin_slabs_without_contained_vertices',h,v,True)
p=group('QA_diagonal');block('diagonal',[-1,-.05,-.05],[1,.05,.05],mat,p,0);rotate(p,(0,math.pi/4,0));q=group('QA_far_edge');block('far_edge',[.60,-.04,.60],[.68,.04,.68],mat,q,0);case('overlapping_AABBs_but_separate_solids',p,q,False)
t=group('QA_hollow');annulus_y('real_hollow_pipe',(0,0,0),.1,.2,0,.2,mat,t);r=group('QA_bore_rod');cylinder('rod',(0,.1,0),.05,.1,mat,r,axis='Y',vertices=16);case('rod_inside_real_bore_without_metal_contact',t,r,False)
barroot=group('QA_actual_faceted_bar');bar(mat,barroot)
angle=math.pi*.75-.002;support=.02*max(math.cos(angle-(i+.5)*math.pi/16) for i in range(32))
for depth,expected in[(0,False),(.00001,True)]:
 root=frame('QA_tangent_pad_'+str(depth),loc=(0,.148,.23));rotate(root,(angle,0,0));block('tangent_pad',[-.04,support-depth,-.008],[.04,support+.02-depth,.008],mat,root,0);case('actual_faceted_bar_tangent_pad_'+str(depth),barroot,root,expected)
maximum_angle_error=0;angle_comparisons=0
for root in[a,t,barroot]:
 part=collect(root)[0][0]
 for i in range(1,65):
  point=[part['low'][j]+(part['high'][j]-part['low'][j])*(((i*(17+6*j))%67+.17)/67) for j in range(3)];total=0
  for verts,_ in faces(part):
   va,vb,vc=[sub(v,point) for v in verts];la,lb,lc=map(length,[va,vb,vc]);total+=2*math.atan2(dot(va,cross(vb,vc)),la*lb*lc+dot(va,vb)*lc+dot(vb,vc)*la+dot(vc,va)*lb)
  error=abs(total-solid_angle(part,point));maximum_angle_error=max(maximum_angle_error,error);angle_comparisons+=1;assert error<1e-10,(point,total,error)
report=dict(passed=True,vectorized_scalar_angle_comparisons=angle_comparisons,maximum_solid_angle_difference_rad=maximum_angle_error,cases=rows,method='Transverse native triangle segments and closed-mesh solid angle,2um gate. Nearest-edge signed normal alone is never an inside test.',scope='Analytical calibration fixtures only, not an engine run.')
out=ROOT/'assets/v3/iterations/small-package-gripper/P03.5.3.2';(out/'clearance-calibration.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('NATIVE_CLEARANCE_CALIBRATION '+json.dumps(report))
