"""P05.1: reuse immutable station/scanner and one already placed pallet HU."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,anchor,finish,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_standard_carton import collect
from native_clearance import penetration

PLAN=ROOT/'assets/v3/specs/receiver-workcell.dimensions.json'
OUT=ROOT/'assets/v3/iterations/receiver/P05.1'
EPS=2e-6


def workcell():
    plan=json.loads(PLAN.read_text(encoding='utf8'))
    for path,expected in plan['source_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    for ref in plan['references']:assert hashlib.sha256((ROOT/ref['path']).read_bytes()).hexdigest()==ref['sha256']
    root=group('receiver_workcell_root')
    for key,value in dict(role='visual_QA_fixture',source_kind='visual_fixture',engine_operation=False,
                          reference_id='R04',component_reference_ids_json=json.dumps(['R04','M08_REF','R05']),
                          contains_worker=False,HU_instances=1,warehouse_headcount_delta=0,
                          scope=plan['scope']).items():root[key]=value
    station=append_source('assets/v3/blender/packing-station.blend','packing-station__MODULE',root)
    bpy.context.view_layer.update()
    pivot=xyz(plan['screen_swivel_pivot_xyz_m'])
    swivel=Matrix.Translation(pivot)@Matrix.Rotation(plan['screen_swivel_yaw_rad'],4,xyz((0,1,0)))@Matrix.Translation(-pivot)
    for name in ['screen__DEVICE','anchor_screen_face']:
        node=next(n for n in station.children_recursive if n.name==name)
        node.matrix_world=swivel@node.matrix_world
    pallet=append_source('assets/v3/blender/pallet-load.blend','pallet-load__HU',root,plan['pallet_root'])
    pallet.name='receiver_existing_pallet';pallet['fixture_HU_ref']='v3:fixture:HU:RECEIVE01'
    pallet['fixture_stock_created']=False
    return root,station,pallet,plan


def floor_contacts(parts):
    result=[]
    for p in parts:
        if abs(p['low'][1])>EPS:continue
        x,z=[(p['low'][i]+p['high'][i])/2 for i in [0,2]]
        point,normal,_,_=p['bvh'].ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.02)
        if point is not None and abs(runtime_xyz(point)[1])<EPS and normal.dot(xyz((0,-1,0)))>.99:
            result.append(dict(part=p['name'],point=runtime_xyz(point)))
    return result


def scan_target(root,pallet,plan):
    origin=xyz(plan['scanner_lens_front_xyz_m']);forward=xyz((0,0,1));deps=bpy.context.evaluated_depsgraph_get();options=[]
    for obj in pallet.children_recursive:
        if obj.type!='MESH' or not obj.name.startswith('unit_body_'):continue
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
        try:
            for face in mesh.polygons:
                if 'offwhite' not in mesh.materials[face.material_index].name:continue
                point=evaluated.matrix_world@(sum((mesh.vertices[i].co for i in face.vertices),Vector())/len(face.vertices))
                normal=(evaluated.matrix_world.to_3x3().inverted().transposed()@face.normal).normalized()
                delta=point-origin
                if runtime_xyz(point)[1]<1.0 or normal.dot(forward)>-.99:continue
                angle=math.degrees(delta.angle(forward))
                if angle<=plan['visual_scan_cone_half_angle_deg']:options.append((angle,delta.length,obj.name,point,normal))
        finally:evaluated.to_mesh_clear()
    assert options,'No real upper label face in the declared visual scan cone'
    _,whole=collect(root)
    for angle,distance,name,point,normal in sorted(options,key=lambda o:(o[0],o[1])):
        direction=(point-origin).normalized();hit,on,_,_=whole.ray_cast(origin+direction*1e-5,direction,distance+.001)
        if hit is None or (hit-point).length>EPS or on.dot(normal)<.99:continue
        return dict(source_part=name,lens_front_xyz_m=runtime_xyz(origin),label_xyz_m=runtime_xyz(point),
                    label_normal_runtime=runtime_xyz(normal),direction_runtime=runtime_xyz(direction),
                    range_m=distance,axis_angle_deg=angle,first_actual_triangle_hit=runtime_xyz(hit),
                    target_error_m=(hit-point).length,visual_assumption=True,actual_decoding=False)
    raise AssertionError('All selected existing labels are occluded from the real lens aperture')


if __name__=='__main__':
    assert bpy.app.background
    reset();root,station,pallet,plan=workcell();sp,_=collect(station);pp,_=collect(pallet)
    screen=next(n for n in station.children_recursive if n.name=='screen__DEVICE');screen_parts,_=collect(screen)
    screen_names={p['name'] for p in screen_parts}
    screen_hits=[h for a in screen_parts for b in sp if b['name'] not in screen_names if (h:=penetration(a,b))]
    assert not screen_hits,screen_hits
    hits=[h for a in sp for b in pp if (h:=penetration(a,b))];assert not hits,hits
    assert min(p['low'][1] for p in sp+pp)>=-EPS
    station_floor=floor_contacts(sp);pallet_floor=floor_contacts(pp)
    assert len(station_floor)>=4 and len(pallet_floor)>=3
    base=next(p for p in sp if p['name']=='screen_base')
    centre=[(base['low'][i]+base['high'][i])/2 for i in range(3)];centre[1]=base['low'][1]
    supports=[]
    for p in sp:
        if p['name']!='worktop_L':continue
        point,normal,_,_=p['bvh'].ray_cast(xyz((centre[0],centre[1]+.001,centre[2])),xyz((0,-1,0)),.002)
        if point is not None and abs(runtime_xyz(point)[1]-centre[1])<EPS and normal.dot(xyz((0,1,0)))>.99:supports.append(runtime_xyz(point))
    assert supports,'Rotated monitor base lost its real table support'
    scan=scan_target(root,pallet,plan)
    anchor('anchor_receiver_scan_lens',scan['lens_front_xyz_m'],root,'actual_scanner_front_lens')
    anchor('anchor_receiver_scan_target',scan['label_xyz_m'],root,'actual_existing_HU_label_face')
    anchor('anchor_receiver_confirm',plan['confirmation_candidate_xyz_m'],root,'candidate_existing_terminal_contact')
    anchor('anchor_receiver_service',plan['receiver_candidate_root'],root,'candidate_service_floor_pose')
    parts,_=collect(root);bounds=dict(min=[min(p['low'][i] for p in parts) for i in range(3)],max=[max(p['high'][i] for p in parts) for i in range(3)])
    assert max(abs(bounds[side][i]-plan['expected_workcell_bounds_m'][side][i]) for side in ['min','max'] for i in range(3))<EPS,bounds
    assert sum(n.get('role')=='HU_content_unit_frame' for n in pallet.children_recursive)==24
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(task_id='P05.1',passed_native=True,source_kind='visual_fixture',engine_operation=False,
                source_hashes=plan['source_hashes'],plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                native_parts=dict(station=len(sp),pallet=len(pp)),bounds_m=bounds,unit_scale=True,
                station_floor_contacts=station_floor,pallet_floor_contacts=pallet_floor,scan=scan,
                screen_base_actual_support=supports,screen_swivel_yaw_rad=plan['screen_swivel_yaw_rad'],
                HU_instances=1,worker_instances=0,scope=plan['scope'])
    stats=finish('receiver-workcell-fixture',root);report['glb_sha256']=stats['sha256']
    for path,expected in plan['source_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    (OUT/'native-workcell.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('RECEIVER_WORKCELL_VERIFIED '+json.dumps(dict(parts=len(parts),station_feet=len(station_floor),pallet_floor_contacts=len(pallet_floor),scan=scan,triangles=stats['triangles'])))
