"""Recheck the saved native tool without re-exporting or changing source hashes."""
import sys,json,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset
from build_sealed_parcel import append_source
from build_small_gripper import verify
assert bpy.app.background
paths=['assets/v3/blender/small-package-gripper.blend','frontend/public/models/v3/small-package-gripper.glb']
before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
reset();root=append_source(paths[0],'small-package-gripper',None);states=verify(root)
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in before.items())
report=dict(passed=True,source_kind='synthetic_tool_geometry_QA',engine_operation=False,input_sha256=before,checker_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/blender/v3/recheck_small_gripper.py','tools/blender/v3/build_small_gripper.py','tools/blender/v3/native_clearance.py']},states=states,source_files_unchanged=True,scope='Saved native mechanism and physical connections at five openings. No action or certified equipment admission.')
(ROOT/'assets/v3/iterations/small-package-gripper/P03.5.3.2/saved-native-recheck.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('SAVED_TOOL_RECHECKED '+json.dumps(dict(states=len(states),source_files_unchanged=True)))
