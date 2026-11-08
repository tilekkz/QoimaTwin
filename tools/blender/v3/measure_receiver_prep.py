"""Read-only conservative table-edge envelope for actual sampled receiver poses."""
import sys,json,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_standard_carton import collect
from native_clearance import penetration
assert bpy.app.background
OUT=ROOT/'assets/v3/iterations/receiver/P05.2';raw=(OUT/'runtime-native-poses.json').read_bytes();data=json.loads(raw)
reset();cell=append_source('assets/v3/blender/receiver-workcell-fixture.blend','receiver_workcell_root',None);table=next(p for p in collect(cell)[0] if p['name']=='worktop_L');worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);worker.location=xyz(data['body_root_m']);rotate(worker,[0,data['body_yaw_rad'],0]);nodes={n.name:n for n in worker.children_recursive};C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))

def clipped(poly,axis,bound,sign):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        x=(a[axis]-bound)*sign;y=(b[axis]-bound)*sign
        if x>=0:result.append(a)
        if (x<0)!=(y<0):result.append([a[i]+(b[i]-a[i])*x/(x-y) for i in range(3)])
    return result

rows=[]
for f in data['frames']:
 if f['mode']!='receive':continue
 for name,p in f['joints'].items():
    n=nodes[name];n.location=xyz(p['position']);a=p['quaternion'];n.rotation_mode='QUATERNION';n.rotation_quaternion=(C@Quaternion((a[3],a[0],a[1],a[2])).to_matrix()@C.transposed()).to_quaternion()
 bpy.context.view_layer.update()
 for p in physical_body(worker)[0]:
    if not penetration(p,table):continue
    points=[]
    for tri in p['triangles']:
        poly=[p['verts'][i] for i in tri]
        for axis in [0,1]:
            poly=clipped(poly,axis,table['low'][axis],1);poly=clipped(poly,axis,table['high'][axis],-1)
            if not poly:break
        points+=poly
    if points:rows.append(dict(time=f['time'],part=p['name'],clipped_max_z_m=max(v[2] for v in points),conservative_rear_shift_m=max(v[2] for v in points)-table['low'][2]+2e-6))
report=dict(source_kind='visual_geometry_diagnostic',engine_operation=False,runtime_pose_sha256=hashlib.sha256(raw).hexdigest(),table_bounds_m=dict(min=table['low'],max=table['high']),intersecting_sample_parts=rows,maximum_conservative_rear_shift_m=max((r['conservative_rear_shift_m'] for r in rows),default=0),scope='Actual penetrating sampled parts clipped to table XY AABB. Conservative envelope estimate for an explicit service/monitor layout revision, not a clearance certificate or accepted motion.')
(OUT/'prep-table-envelope.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('RECEIVER_PREP_ENVELOPE '+json.dumps({k:v for k,v in report.items() if k not in ['intersecting_sample_parts','scope']}))
