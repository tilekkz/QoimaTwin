"""Read-only actual native hand contact interface for P04."""
import sys,json,hashlib
from pathlib import Path
import bpy
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).resolve().parent));assert bpy.app.background
from v3_common import reset,xyz,runtime_xyz
from build_sealed_parcel import append_source
reset();worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);bpy.context.view_layer.update();out={}
for side in ['L','R']:
 h=bpy.data.objects['joint__hand_'+side];o=bpy.data.objects['mitten_'+side+'_thumb'];ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();points=[runtime_xyz(h.matrix_world.inverted()@ev.matrix_world@v.co) for v in m.vertices];ev.to_mesh_clear()
 lo=[min(v[i] for v in points) for i in range(3)];hi=[max(v[i] for v in points) for i in range(3)]
 out[side]=dict(thumb_bounds_hand_local_m=dict(min=lo,max=hi),thumb_face_contact_local_m=[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,hi[2]])
 o=bpy.data.objects['mitten_'+side+'_lower_pad'];ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();points=[runtime_xyz(h.matrix_world.inverted()@ev.matrix_world@v.co) for v in m.vertices];ev.to_mesh_clear();lo=[min(v[i] for v in points) for i in range(3)];hi=[max(v[i] for v in points) for i in range(3)]
 out[side].update(lower_pad_bounds_hand_local_m=dict(min=lo,max=hi),lower_pad_contact_local_m=[(lo[0]+hi[0])/2,lo[1],(lo[2]+hi[2])/2])
out['source_hashes']={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in ['assets/v3/blender/worker-manual.blend','frontend/public/models/v3/worker-manual.glb']};(R/'assets/v3/iterations/packer/P04.1/hand-interface.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print('MEASURED '+json.dumps(out))
