"""P06.2: current runtime replay on original closed body/cargo/support geometry."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_small_pick_source import rotate
from build_picker_figure import physical_body
from build_standard_carton import collect,triangle_box
from build_shipper_workcell import parcel_support
from native_clearance import penetration,touching,contains

assert bpy.app.background
OUT=ROOT/'assets/v3/iterations/shipper/P06.2';EPS=2e-6;C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
pose_bytes=(OUT/'runtime-native-poses.json').read_bytes();data=json.loads(pose_bytes)
inputs=data['input_hashes']|{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/blender/v3/verify_shipper.py','tools/blender/v3/build_shipper_workcell.py','tools/blender/v3/native_clearance.py','tools/blender/v3/build_picker_figure.py','tools/blender/v3/build_standard_carton.py','tools/blender/v3/v3_common.py']}
for p,h in inputs.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
reset();cell=append_source('assets/v3/blender/shipper-workcell-fixture.blend','shipper_workcell_root',None)
worker=append_source('assets/v3/blender/worker-manual.blend','worker_base_root',None);nodes={n.name:n for n in worker.children_recursive};rotate(worker,[0,data['body_yaw_rad'],0])
parcel=next(n for n in cell.children_recursive if n.name=='shipper_existing_parcel');belt=next(n for n in cell.children_recursive if n.name=='shipper_outbound_belt');pallet=next(n for n in cell.children_recursive if n.name=='shipper_existing_pallet');bpy.context.view_layer.update();pallet_matrix=pallet.matrix_world.copy()
scan=json.loads((ROOT/'assets/v3/iterations/shipper/P06.1/native-workcell.json').read_text(encoding='utf8'))['scan'];origin=xyz(scan['lens_front_xyz_m']);target=xyz(scan['label_xyz_m']);direction=(target-origin).normalized();distance=(target-origin).length


def mouth_clear(side,by):
    hand=nodes['joint__hand_'+side];inverse=hand.matrix_world.inverted();cx=runtime_xyz(nodes['anchor_hand_grip_'+side].location)[0];lo=[cx-.038+EPS,-.068+EPS,.033+EPS];hi=[cx+.038-EPS,-.032-EPS,.06-EPS]
    for p in [by['fore_sleeve_'+side],by['cuff_'+side]]:
        vs=[runtime_xyz(inverse@xyz(v)) for v in p['verts']]
        assert not any(triangle_box([vs[i] for i in t],lo,hi) for t in p['triangles']),('own C-mouth triangle',side,p['name'])
        assert not contains(p,runtime_xyz(hand.matrix_world@xyz([(a+b)/2 for a,b in zip(lo,hi)]))),('own C-mouth solid',side,p['name'])


rows=[];failure=None
try:
 for f in data['frames']:
    worker.location=xyz(f['state']['body_root_workcell_m']);parcel.location=xyz(f['state']['parcel_root_workcell_m'])
    for name,p in f['joints'].items():
        node=nodes[name];node.location=xyz(p['position']);q=p['quaternion'];node.rotation_mode='QUATERNION';node.rotation_quaternion=(C@Quaternion((q[3],q[0],q[1],q[2])).to_matrix()@C.transposed()).to_quaternion()
    bpy.context.view_layer.update();wp,_=physical_body(worker);by={p['name']:p for p in wp};env,_=collect(cell);pp,_=collect(parcel);bp,_=collect(belt);parcel_names={p['name'] for p in pp}
    hit=next((h for a in wp for b in env if (h:=penetration(a,b))),None);assert hit is None,('worker/workcell penetration',hit)
    hit=next((h for a in pp for b in env if b['name'] not in parcel_names if (h:=penetration(a,b))),None);assert hit is None,('parcel/environment penetration',hit)
    supports=parcel_support(bp,parcel);assert len(supports)==9
    for side in ['L','R']:
        active=lambda p:p['name'].startswith(('fore_sleeve_'+side,'cuff_'+side,'mitten_'+side))
        hit=next((h for a in wp if active(a) for b in wp if not active(b) and b['name']!='upper_sleeve_'+side if (h:=penetration(a,b))),None);assert hit is None,('own body penetration',hit)
        mouth_clear(side,by)
    links=[]
    for side in ['L','R']:
        for a,b in [('upper_sleeve','fore_sleeve'),('cuff','mitten_spine'),('trouser_thigh','trouser_shin'),('trouser_shin','boot')]:
            left=a+'_'+side;right='mitten_'+side+'_spine' if b=='mitten_spine' else b+'_'+side
            assert touching(by[left],by[right]),('body connection',left,right);links.append([left,right])
    floor=[by['boot_'+side]['low'][1] for side in ['L','R']];assert min(abs(y) for y in floor)<EPS and min(p['low'][1] for p in wp)>=-EPS,('floor support',floor)
    stance=[abs(by['boot_'+foot['side']]['low'][1]) for foot in f['state']['actualFeet'] if foot['target']['stance']];assert stance and max(stance)<EPS,('stance sole not floor',stance)
    gap=None
    if f['state']['contact']['active']:
        point=nodes['joint__hand_R'].matrix_world@xyz(data['contact']['local_m']);pad=by['mitten_R_lower_pad'];wall=next(p for p in pp if p['name']==data['contact']['surface']);_,pn,_,pd=pad['bvh'].find_nearest(point);_,wn,_,wd=wall['bvh'].find_nearest(point)
        assert pd<EPS and wd<EPS and pn.dot(wn)<-.99,('missing opposed native parcel contact',pd,wd,pn.dot(wn))
        assert math.dist(runtime_xyz(point),f['state']['contact']['target_workcell_m'])<EPS;gap=max(pd,wd)
    optical=None
    if f['state']['displacement_m']==0:
        hits=[]
        for p in env+wp:
            point,normal,_,_=p['bvh'].ray_cast(origin+direction*1e-5,direction,distance+.001)
            if point is not None:hits.append(((point-origin).length,p['name'],point))
        _,part,first=min(hits,key=lambda h:h[0]);assert (first-target).length<EPS,('scanner line occluded',part,runtime_xyz(first));optical=True
    assert not f['state']['scanning'] or optical is True
    if f['mode'] in ['idle','blocked']:
        inverse=worker.matrix_world.inverted().to_3x3()
        for side,sign in [('L',1),('R',-1)]:
            normal=runtime_xyz(inverse@(nodes['joint__hand_'+side].matrix_world.to_3x3()@xyz((0,0,1))).normalized());assert normal[0]*sign>.98,('rest palm not inward',side,normal)
    assert pallet.matrix_world==pallet_matrix and pallet['declared_gross_mass_kg']==455 and parcel['complete_gross_kg']==1.02,'Heavy pallet matrix or original cargo mass changed'
    rows.append(dict(mode=f['mode'],time=f['time'],native_parts=dict(worker=len(wp),workcell=len(env)),connections=len(links),C_mouth_gauges=2,maximum_stance_boot_floor_error_m=max(stance),boot_floor_heights_m=floor,opposed_parcel_contact=gap is not None,contact_gap_m=gap,parcel_actual_support_rays=len(supports),scan_line_clear=optical,heavy_pallet_unmoved=True,parcel_displacement_m=f['state']['displacement_m']))
    if len(rows)%50==0:print('SHIPPER_NATIVE_PROGRESS '+str(len(rows)),flush=True)
except Exception as error:
    failure=dict(mode=f['mode'],time=f['time'],error=str(error));print('SHIPPER_NATIVE_REJECTED '+json.dumps(failure),flush=True)
for p,h in inputs.items():
    if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:failure=dict(error='Input changed during native validation',path=p)
if hashlib.sha256((OUT/'runtime-native-poses.json').read_bytes()).hexdigest()!=hashlib.sha256(pose_bytes).hexdigest():failure=dict(error='Runtime poses changed during native validation')
report=dict(passed=failure is None,source_kind='visual_fixture',engine_operation=False,accepted_action=False,input_hashes=inputs,runtime_pose_sha256=hashlib.sha256(pose_bytes).hexdigest(),native_frames=len(rows),frames=rows,failure=failure,scope='Current actual closed native geometry at50ms across all modes;2um calibrated gate, opposed real hand-wall contact,9actual moving parcel/belt support rays each frame, grounded physical legs/soles, clear scan line while scanning. Heavy pallet static. Bounded samples, not continuous collision certification or actual shipment.')
if failure:
    p=OUT/'native-rejections.json';history=json.loads(p.read_text(encoding='utf8')) if p.exists() else [];history.append(dict(failure=failure,exact_runtime_frame=f,input_hashes=inputs));p.write_text(json.dumps(history,indent=2)+'\n',encoding='utf8')
(OUT/'native-path-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
assert failure is None,failure
print('SHIPPER_NATIVE_VERIFIED '+json.dumps(dict(frames=len(rows),contacts=sum(r['opposed_parcel_contact'] for r in rows),supports=sum(r['parcel_actual_support_rays'] for r in rows))))
