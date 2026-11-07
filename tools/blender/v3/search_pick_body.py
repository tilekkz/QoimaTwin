"""Native candidate search for a clear same-scale standing top-pick body."""
import json,sys,math,itertools
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_sealed_parcel import append_source
from build_standard_carton import collect
EPS=2e-6
reset();scene=append_source('assets/v3/blender/picker-pick-source-fixture.blend','picker_pick_source_fixture_root',None)
worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);rotate(worker,(0,math.pi,0));nodes={n.name:n for n in worker.children_recursive}
targets,_=collect(scene);clear=[];tested=0;failed={}
def penetrates(a,b):
 if any(a['high'][i]<=b['low'][i]+EPS or a['low'][i]>=b['high'][i]-EPS for i in range(3)):return False
 for p,q in [(a,b),(b,a)]:
  for point in p['samples']:
   hit,normal,_,distance=q['bvh'].find_nearest(point)
   if distance>EPS and normal.dot(point-hit)<-EPS:return True
 return False
for x,z,lean in itertools.product([1.04,1.12,1.20,1.28,1.36,1.44,1.48],[.74,.80,.88],[.15,.3,.45,.6,.75,.9]):
 worker.location=xyz((x,0,z));rotate(nodes['joint__torso'],(lean,0,0));rotate(nodes['joint__upper_arm_L'],(.6,0,0))
 for head_y in [0,-.6,.6]:
  rotate(nodes['joint__head'],(-.25,head_y,0));parts,_=physical_body(worker)
  parts=[p for p in parts if not p['name'].startswith(('upper_sleeve_R','fore_sleeve_R','cuff_R','mitten_R'))]
  hit=next(([a['name'],b['name']] for a in parts for b in targets if penetrates(a,b)),None);tested+=1
  if hit:failed['/'.join(hit)]=failed.get('/'.join(hit),0)+1
  else:
   clear.append(dict(root=[x,0,z],torso_x=lean,head=[-.25,head_y,0],idle_left_upper=[.6,0,0]));break
out=dict(tested=tested,clear=clear,failed_pairs=failed,scope='Native clear body candidates only; right arm excluded and no pick-action acceptance.')
(ROOT/'assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-clear-bodies.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
print('BODY_CANDIDATES '+json.dumps(dict(tested=tested,clear=len(clear),examples=clear[:8])))
