"""Native thumb control candidates at a rejected transition frame; no action acceptance."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz
from build_small_pick_source import rotate
from build_sealed_parcel import append_source
from build_standard_carton import collect
from build_picker_figure import physical_body
from build_small_gripper import opening
from native_clearance import penetration,touching
assert bpy.app.background
OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.3.3';d=json.loads((OUT/'runtime-native-poses.json').read_text(encoding='utf8'));f=next(f for f in d['frames'] if f['time']==.6);s=f['state'];C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
reset();w=append_source('assets/v3/blender/worker-small-pick.blend','worker_base_root',None,s['body']);rotate(w,(0,math.pi,0));tool=append_source('assets/v3/blender/small-package-gripper.blend','small-package-gripper',None,s['tool']);opening(tool,s['opening']);nodes={n.name:n for n in w.children_recursive}
for name,p in f['joints'].items():
 n=nodes[name];n.location=xyz(p['position']);a=p['quaternion'];n.rotation_mode='QUATERNION';n.rotation_quaternion=(C@Quaternion((a[3],a[0],a[1],a[2])).to_matrix()@C.transposed()).to_quaternion()
tp,_=collect(tool);rows=[]
for slide in[0,-.001,-.002,-.003,-.004,-.005]:
 for press in[0,.01,.02,.03,.04,.05,.06]:
  nodes['joint__finger_thumb_R'].location=xyz((0,0,slide));rotate(nodes['joint__thumb_press_R'],(press,0,0));bpy.context.view_layer.update();wp,_=physical_body(w);by={p['name']:p for p in wp};thumb=by['mitten_R_thumb'];hits=[p['name'] for p in tp+[by['mitten_R_upper_pad'],by['mitten_R_lower_pad']] if penetration(thumb,p)];rows.append(dict(slide_m=slide,press_rad=press,collisions=hits,connected=touching(thumb,by['mitten_R_spine'])))
clear=[r for r in rows if not r['collisions'] and r['connected']];(OUT/'thumb-transition-probe.json').write_text(json.dumps(dict(time=.6,candidates=rows,clear=clear,scope='Single rejected transition frame. Existing slide/press controls only; no full action or joint-limit expansion.'),indent=2)+'\n',encoding='utf8');print('THUMB_TRANSITION_CLEAR '+json.dumps(clear))
