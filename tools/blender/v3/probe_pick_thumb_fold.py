"""Bounded raw-mesh-preserving thumb hinge feasibility; no rig/action acceptance."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,pivot,runtime_xyz
from build_small_pick_source import rotate,parent_at_rest
from build_sealed_parcel import append_source
from build_picker_figure import physical_body
from build_standard_carton import collect
from verify_cart_walk import connected
EPS=2e-6
assert bpy.app.background
from native_clearance import penetration as penetrates
source='assets/v3/blender/worker-manual.blend';before=hashlib.sha256((ROOT/source).read_bytes()).hexdigest();reset()
worker=append_source(source,'worker_base_root',None);rotate(worker,(0,math.pi,0));nodes={o.name:o for o in worker.children_recursive}
c=json.loads((ROOT/'assets/v3/iterations/worker-base/P03.5.3/gripper-raised-reach-probe/clear-candidate.json').read_text(encoding='utf8'));worker.location=xyz(c['root'])
for name,angles in c['pose'].items():
 if name.startswith('joint__elbow_swivel_'):
  nodes[name].rotation_mode='QUATERNION';nodes[name].rotation_quaternion=Matrix.Rotation(angles[0],4,xyz(c['twist_axis_runtime'])).to_quaternion()
 else:rotate(nodes[name],angles)
close=(.045-2*.02*math.cos(math.pi/32))/2
nodes['joint__finger_upper_R'].location=xyz((0,-close,0));nodes['joint__finger_lower_R'].location=xyz((0,close,0));nodes['joint__finger_thumb_R'].location=xyz((0,0,-.005))
tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None,(.945,1.2645,.32));bpy.context.view_layer.update();tp,_=collect(tool)
thumb=bpy.data.objects['mitten_R_thumb'];finger=nodes['joint__finger_thumb_R'];original=thumb.matrix_world.copy();hinge=pivot('QA_thumb_fold',(0,0,0),finger,'Y');parent_at_rest(thumb,hinge)
rows=[]
for z in[-.015,0,.015]:
 for axis in[0,1,2]:
  for a in[0,-.2,.2,-.4,.4,-.6,.6]:
   rotate(hinge,(0,0,0));hinge.location=xyz((-.032,-.006,z));bpy.context.view_layer.update();thumb.matrix_world=original;bpy.context.view_layer.update();v=[0,0,0];v[axis]=a;rotate(hinge,v)
   parts,_=physical_body(worker);by={p['name']:p for p in parts};p=by['mitten_R_thumb'];hits=[q['name'] for q in tp if penetrates(p,q)]
   linked=connected(p,by['mitten_R_spine']);distal=[];inverse=nodes['joint__hand_R'].matrix_world.inverted()
   for q in[by['mitten_R_upper_pad'],by['mitten_R_lower_pad']]:
    for point in p['samples']:
     if runtime_xyz(inverse@point)[2]<.03:continue
     hit,n,_,d=q['bvh'].find_nearest(point)
     if d>EPS and n.dot(point-hit)<-EPS:distal.append(q['name']);break
   rows.append(dict(pivot_hand_local=[-.032,-.006,z],axis='XYZ'[axis],angle=a,tool_collisions=hits,spine_connected=linked,distal_finger_collisions=distal))
clear=[r for r in rows if not r['tool_collisions'] and r['spine_connected'] and not r['distal_finger_collisions']];clear.sort(key=lambda r:abs(r['angle']))
out=ROOT/'assets/v3/iterations/worker-base/P03.5.3/thumb-fold-probe';out.mkdir(parents=True,exist_ok=True)
report=dict(tested=len(rows),clear=clear,results=rows,original_body_file_unchanged=hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==before,scope='Original raised135deg handle pose and actual refined tool. Thumb geometry only reparented/rotated temporarily. No body scaling, wrist-range extension, accepted derivative or action.')
(out/'native-thumb-fold.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('THUMB_FOLD_PROBE '+json.dumps({k:v for k,v in report.items() if k not in['results','scope']}))
