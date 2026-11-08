"""Bounded native fine-grid standing body candidates for the unchanged SMALL source."""
import json,sys,math,itertools
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect
assert bpy.app.background
EPS=2e-6
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);rotate(worker,(0,math.pi,0));nodes={n.name:n for n in worker.children_recursive};targets,_=collect(scene)
from native_clearance import penetration as penetrates
clear=[];failed={};tested=0
for x,z,head_y in itertools.product([1.22,1.24,1.26,1.28],[.82,.84,.86,.88],[0,-.3,-.6]):
 worker.location=xyz((x,0,z));rotate(nodes['joint__torso'],(.15,0,0));rotate(nodes['joint__upper_arm_L'],(.6,0,0));rotate(nodes['joint__head'],(-.25,head_y,0));parts,_=physical_body(worker)
 parts=[p for p in parts if not p['name'].startswith(('upper_sleeve_R','fore_sleeve_R','cuff_R','mitten_R'))];tested+=1
 hit=next(([a['name'],b['name']] for a in parts for b in targets if penetrates(a,b)),None)
 if hit:failed['/'.join(hit)]=failed.get('/'.join(hit),0)+1
 else:clear.append(dict(root=[x,0,z],torso_x=.15,head=[-.25,head_y,0],idle_left_upper=[.6,0,0]))
out=ROOT/'assets/v3/iterations/worker-base/P03.5.3/tool-fine-bodies';out.mkdir(parents=True,exist_ok=True)
(out/'bodies.json').write_text(json.dumps(dict(clear=clear,tested=tested,failed=failed,scope='Fine4x4standing root grid,3existing head yaw values; right arm excluded. No source, dimensions, body, joint limit or action change.'),indent=2)+'\n',encoding='utf8')
print('TOOL_FINE_BODY_CANDIDATES '+json.dumps(dict(tested=tested,clear=len(clear))))
