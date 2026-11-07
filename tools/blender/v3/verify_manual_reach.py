"""P03.5.1.1 native articulation continuity; not action collision admission."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from verify_cart_walk import connected
reset();worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None)
nodes={n.name:n for n in worker.children_recursive};rest={n:n.matrix_basis.copy() for n in worker.children_recursive};frames=[]
for side in ('L','R'):
 for elevation,swivel,upper,elbow in [(0,0,0,0),(-.4,0,-1, -1),(-.8,math.pi,-1.6,-.5),(-.8,-math.pi,-1.5,-1),(0,math.pi/2,-1.2,-1.2),(0,-math.pi/2,-1.2,-1.2)]:
  for n,m in rest.items():n.matrix_basis=m
  rotate(nodes['joint__shoulder_lift_'+side],(elevation,0,0));rotate(nodes['joint__upper_arm_'+side],(upper,0,0));rotate(nodes['joint__forearm_'+side],(elbow,0,0))
  node=nodes['joint__elbow_swivel_'+side];node.rotation_mode='QUATERNION';node.rotation_quaternion=Matrix.Rotation(swivel,4,xyz(node['custom_axis_runtime'])).to_quaternion()
  parts,_=physical_body(worker);byname={p['name']:p for p in parts};links={label:connected(byname[a],byname[b]) for label,a,b in [('shoulder','connected_shoulder_band','upper_sleeve_'+side),('elbow','upper_sleeve_'+side,'fore_sleeve_'+side),('wrist','cuff_'+side,'mitten_'+side+'_spine')]}
  assert all(links.values()),(side,elevation,swivel,links)
  frames.append(dict(side=side,additional_elevation_rad=elevation,upper_arm_swivel_rad=swivel,original_upper_x=upper,original_elbow_x=elbow,actual_native_connections=links))
out=ROOT/'assets/v3/iterations/worker-base/P03.5.1.1';out.mkdir(parents=True,exist_ok=True)
report=dict(task_id='P03.5.1.1',actual_native_connection_poses=frames,source_sha256=hashlib.sha256((ROOT/'assets/v3/blender/worker-manual.blend').read_bytes()).hexdigest(),glb_sha256=hashlib.sha256((ROOT/'frontend/public/models/v3/worker-manual.glb').read_bytes()).hexdigest(),scope='Explicit manual articulation and native joint continuity only. Sampled reaches are not action collision approvals. All action poses must pass their own source/body/cargo clearance gate.')
(out/'actual-native-reach-controls.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('MANUAL_REACH_CONTROLS_VERIFIED '+json.dumps(dict(native_connection_poses=len(frames),connections=3*len(frames))))
