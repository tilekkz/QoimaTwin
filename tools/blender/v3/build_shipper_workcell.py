"""P06.1: frozen source outbound post, supported parcel and staged pallet."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,anchor,finish,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_small_pick_source import rotate
from build_standard_carton import collect
from native_clearance import penetration

PLAN=ROOT/'assets/v3/specs/shipper-workcell.dimensions.json'
OUT=ROOT/'assets/v3/iterations/shipper/P06.1';EPS=2e-6


def floor_contacts(parts):
    contacts=[]
    for p in parts:
        if abs(p['low'][1])>EPS:continue
        for u,v in [(.5,.5),(.37,.31),(.63,.69),(.31,.61)]:
            x=p['low'][0]+(p['high'][0]-p['low'][0])*u;z=p['low'][2]+(p['high'][2]-p['low'][2])*v
            hit,n,_,_=p['bvh'].ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.02)
            if hit is not None and abs(runtime_xyz(hit)[1])<EPS and n.dot(xyz((0,-1,0)))>.99:
                contacts.append(dict(part=p['name'],point=runtime_xyz(hit)));break
    return contacts


def workcell():
    plan=json.loads(PLAN.read_text(encoding='utf8'))
    for p,h in plan['source_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    for r in plan['references']:assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256']
    root=group('shipper_workcell_root')
    for k,v in dict(role='visual_QA_fixture',source_kind='visual_fixture',engine_operation=False,reference_id='R04',component_reference_ids_json=json.dumps(['R04','R05','M07.2_REF','M08_REF']),contains_worker=False,HU_instances=2,warehouse_headcount_delta=0,scope=plan['scope']).items():root[k]=v
    station=append_source('assets/v3/blender/packing-station.blend','packing-station__MODULE',root,plan['station_root'])
    belt=append_source('assets/v3/blender/conveyor-straight.blend','conveyor_straight_root',root,plan['belt_root']);belt.name='shipper_outbound_belt'
    parcel=append_source('assets/v3/blender/sealed-parcel.blend','sealed-parcel',root,plan['parcel_root']);parcel.name='shipper_existing_parcel';rotate(parcel,[0,plan['parcel_yaw_rad'],0])
    parcel['fixture_package_id']='v3:fixture:package:SMALL001';parcel['fixture_contents_HU_ref']='v3:fixture:HU:SMALL001';parcel['fixture_stock_created']=False
    pallet=append_source('assets/v3/blender/pallet-load.blend','pallet-load__HU',root,plan['pallet_root']);pallet.name='shipper_existing_pallet';pallet['fixture_HU_ref']='v3:fixture:HU:OUTBOUND01';pallet['fixture_stock_created']=False
    return root,station,belt,parcel,pallet,plan


def scan_line(root,station,parcel,plan):
    origin=xyz(plan['scanner_lens_front_xyz_m']);target=xyz(plan['scan_target_xyz_m']);delta=target-origin;direction=delta.normalized();distance=delta.length
    station_parts,_=collect(station);lens=next(p for p in station_parts if p['name']=='scanner_recessed_lens');near,normal,_,gap=lens['bvh'].find_nearest(origin)
    assert gap<EPS and normal.dot(xyz((0,0,1)))>.99,('declared actual lens point',gap,runtime_xyz(normal))
    pp,whole=collect(root);hit,on,_,_=whole.ray_cast(origin+direction*1e-5,direction,distance+.001)
    assert hit is not None and (hit-target).length<EPS and on.dot(xyz((0,0,-1)))>.99,('actual label first hit',runtime_xyz(hit) if hit else None,runtime_xyz(target))
    parcel_parts,_=collect(parcel);face=next(p for p in parcel_parts if p['name']=='front_paper_and_print');point,_,_,gap=face['bvh'].find_nearest(target);assert gap<EPS
    angle=math.degrees(direction.angle(xyz((0,0,1))));assert angle<=plan['visual_scan_cone_half_angle_deg']
    local=runtime_xyz(parcel.matrix_world.inverted()@target);assert -.155<local[0]<-.035 and .145<local[1]<.166,local
    return dict(lens_front_xyz_m=runtime_xyz(origin),label_xyz_m=runtime_xyz(target),label_local_xyz_m=local,first_actual_triangle_hit=runtime_xyz(hit),range_m=distance,axis_angle_deg=angle,target_error_m=(hit-target).length,actual_decoding=False,visual_assumption=True)


def parcel_support(belt_parts,parcel_root):
    supports=[]
    for x in [-.15,0,.15]:
        for z in [-.12,0,.12]:
            world=runtime_xyz(parcel_root.matrix_world@xyz((x,0,z)))
            hits=[p['bvh'].ray_cast(xyz((world[0],world[1]+.005,world[2])),xyz((0,-1,0)),.01) for p in belt_parts]
            assert any(h is not None and abs(runtime_xyz(h)[1]-world[1])<EPS and n.dot(xyz((0,1,0)))>.99 for h,n,_,_ in hits),world
            supports.append(world)
    return supports


if __name__=='__main__':
    assert bpy.app.background
    reset();root,station,belt,parcel,pallet,plan=workcell();sp,_=collect(station);bp,_=collect(belt);pp,_=collect(parcel);hp,_=collect(pallet)
    groups=[sp,bp,pp,hp];hits=[h for i,a in enumerate(groups) for b in groups[i+1:] for p in a for q in b if (h:=penetration(p,q))];assert not hits,hits
    floors=[floor_contacts(p) for p in [sp,bp,hp]];assert all(len(f)>=n for f,n in zip(floors,[4,4,3])),([len(f) for f in floors],[(p['name'],p['low']) for p in bp if p['low'][1]<.01])
    initial=parcel_support(bp,parcel);initial_location=parcel.location.copy();parcel.location+=xyz(plan['placement_displacement_xyz_m']);bpy.context.view_layer.update();final=parcel_support(bp,parcel)
    moved,_=collect(parcel);assert not [h for a in moved for b in sp+bp+hp if (h:=penetration(a,b))]
    parcel.location=initial_location;bpy.context.view_layer.update();scan=scan_line(root,station,parcel,plan)
    for name,point,kind in [('anchor_shipper_scan_lens',scan['lens_front_xyz_m'],'actual_lens_front'),('anchor_shipper_scan_target',scan['label_xyz_m'],'actual_package_barcode'),('anchor_shipper_service',plan['shipper_candidate_root'],'candidate_floor_service'),('anchor_shipper_contact',[-.69,1.17,1.39],'candidate_existing_parcel_wall'),('anchor_shipper_place_end',[-.69,.92,1.09],'supported_package_root')]:anchor(name,point,root,kind)
    assert sum(o.get('role')=='HU_content_unit_frame' for o in pallet.children_recursive)==24
    assert abs(parcel['complete_gross_kg']-1.02)<1e-8 and pallet['declared_gross_mass_kg']==455
    OUT.mkdir(parents=True,exist_ok=True);stats=finish('shipper-workcell-fixture',root)
    report=dict(task_id='P06.1',passed_native=True,source_kind='visual_fixture',engine_operation=False,source_hashes=plan['source_hashes'],plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),native_parts=dict(station=len(sp),belt=len(bp),parcel=len(pp),pallet=len(hp)),station_floor_contacts=floors[0],belt_floor_contacts=floors[1],pallet_floor_contacts=floors[2],parcel_initial_actual_supports=initial,parcel_final_actual_supports=final,scan=scan,glb_sha256=stats['sha256'],bounds_m=stats['bounds_runtime'],triangles=stats['triangles'],worker_instances=0,HU_instances=2,scope=plan['scope'])
    for p,h in plan['source_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    (OUT/'native-workcell.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('SHIPPER_WORKCELL_VERIFIED '+json.dumps(dict(parts=sum(map(len,groups)),scan=scan,triangles=stats['triangles'])))
