"""Independently verify source epochs, native support triangles and API frames."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from n2_n3_native_geometry import GLB, add, closest, distance, dot, normal
from n2_n3_route_geometry import verify_route_geometry

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / 'docs/v3/contract-proposals/n2-n3-physical-interfaces-v1'
EPS = 2e-6


def read(path):
    def reject(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject)


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pointer(document, value):
    for part in value.split('/')[1:]:
        key = part.replace('~1', '/').replace('~0', '~')
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def verify_sources(section, require_units=True):
    need(section.get('source_kind') == 'visual_fixture', 'SOURCE_KIND_REQUIRED')
    if require_units:
        need(section.get('units') in ('m_s_kg', {'length':'m','time':'s','mass':'kg','angle':'rad'}), 'METRIC_UNITS_REQUIRED')
    for name, expected in section['source_hashes'].items():
        path = (REPO / name).resolve(strict=True)
        need(path.is_relative_to(REPO) and path.relative_to(REPO).as_posix() == name, 'NONCANONICAL_SOURCE_PATH')
        need(not name.startswith('work/'), 'SCRATCH_DEPENDENCY')
        need(sha(path) == expected, 'SOURCE_DRIFT:' + name)


def verify_native(n2, n3):
    models = {}
    counts = {'N2_HU_support': 0, 'N2_HU_fork': 0, 'N2_support_floor': 0, 'N3_loaded': 0, 'N3_stow': 0}
    maximum_triangle_error = 0.0

    def model(path):
        pins = {**n2['source_hashes'], **n3['source_hashes']}
        need(path in pins, 'DEREFERENCED_MODEL_NOT_PINNED:' + path)
        need(sha(REPO/path) == pins[path], 'DEREFERENCED_MODEL_DRIFT:' + path)
        if path not in models:
            models[path] = GLB(REPO / path)
        return models[path]

    def identity_frame(frame):
        q=frame.get('quaternion',frame.get('quaternion_xyzw'))
        need(isinstance(q,list) and len(q)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in q), 'NATIVE_IDENTITY_QUATERNION_REQUIRED')
        need(all(abs(v)<1e-12 for v in q[:3]) and abs(abs(q[3])-1)<1e-12, 'UNVERIFIED_FRAME_ROTATION')
        need(len(frame.get('scale',[]))==3 and all(type(v) in (int,float) and v==1 for v in frame['scale']), 'UNVERIFIED_FRAME_SCALE')
        if 'matrix_column_major' in frame:
            x,y,z=frame['position_m'];expected=[1,0,0,0,0,1,0,0,0,0,1,0,x,y,z,1]
            need(len(frame['matrix_column_major'])==16 and all(abs(a-b)<1e-12 for a,b in zip(frame['matrix_column_major'],expected)), 'NATIVE_FRAME_MATRIX_MISMATCH')

    def face(path, node, index, point, offsets=((0,0,0),), primitive=0):
        nonlocal maximum_triangle_error
        tri = model(path).triangle(node, index, primitive)
        candidates = [tuple(add(v, offset) for v in tri) for offset in offsets]
        errors = [distance(point, closest(point, t)) for t in candidates]
        chosen = candidates[errors.index(min(errors))]
        error = min(errors)
        need(error <= EPS, f'POINT_NOT_ON_NATIVE_TRIANGLE:{path}:{node}:{index}:{error}')
        maximum_triangle_error = max(maximum_triangle_error, error)
        return normal(chosen)

    def pair(a, b, target):
        need(distance(a, target) <= EPS and distance(b, target) <= EPS, 'NATIVE_SUPPORT_TARGET_GAP')
        need(distance(a, b) <= EPS, 'NATIVE_OPPOSED_SUPPORT_GAP')

    support_path = n2['support_templates'][0]['asset_ref']['path']
    forklift_path = 'frontend/public/models/v3/forklift.glb'
    forklift = model(forklift_path)
    carriage = forklift.doc['nodes'][forklift.names['joint__carriage']]['translation']
    for cargo in n2['cargo_interfaces']:
        ref = cargo['source_ref']
        need(ref['path'] in n2['source_hashes'], 'DEREFERENCED_CARGO_SOURCE_NOT_PINNED')
        source = pointer(read(REPO / ref['path']), ref['json_pointer'])
        need(cargo['whole_handling_unit'] == source['handling_unit'], 'N2_WHOLE_HU_CHANGED')
        need(type(cargo['scale_factor']) in (int,float) and cargo['scale_factor'] == 1, 'N2_SCALE_CHANGED')
        need(cargo['ground_pickup_permitted'] is False, 'N2_UNPROVEN_GROUND_PICKUP')
        offset = cargo['HU_root_in_proposed_support_frame']['position_m']
        identity_frame(cargo['HU_root_in_proposed_support_frame'])
        need(offset == [0,.18,.05], 'N2_STAGING_SUPPORT_FRAME_CHANGED')
        need(cargo['actual_support_contact_area_sum_m2'] > .01, 'N2_SUPPORT_AREA_MISSING')
        for w in cargo['native_support_patch_witnesses']:
            a,b = w['HU_native'],w['support_native']
            na = face(cargo['asset_ref']['path'], a['node'], a['triangle'], a['point_m'], (offset,))
            nb = face(support_path, b['node'], b['triangle'], b['point_m'])
            pair(a['point_m'], b['point_m'], w['point_support_local_m'])
            need(dot(na,nb) < -.99999, 'N2_SUPPORT_NORMALS_NOT_OPPOSED')
            counts['N2_HU_support'] += 1
        interface = cargo['fork_interface']
        root = interface['vehicle_root_in_support_frame_at_low_engagement']
        need(interface['handling_fork_top_y_m'] == .18 and interface['travel_fork_top_y_m'] == .7, 'N2_HANDLING_TRAVEL_HEIGHT_CHANGED')
        for w in interface['native_contact_witnesses']:
            a,b = w['HU_native'],w['fork_native']
            side = w['side']
            joint = forklift.doc['nodes'][forklift.names['joint__fork_'+side]]['translation']
            centre = interface['fork_centres_x_m'][0 if side == 'L' else 1]
            delta = [root[0] + centre-joint[0], root[1]+.18-carriage[1], root[2]+.4]
            na = face(cargo['asset_ref']['path'], a['node'], a['triangle'], a['point_m'], (offset,))
            nb = face(forklift_path, b['node'], b['triangle'], b['point_m'], (delta,))
            pair(a['point_m'], b['point_m'], w['point_support_local_m'])
            need(dot(na,nb) < -.99999, 'N2_FORK_NORMALS_NOT_OPPOSED')
            counts['N2_HU_fork'] += 1
    need(len(n2['staging_cells']) == 2, 'N2_FINITE_CAPACITY_CHANGED')
    for cell in n2['staging_cells']:
        need(cell['max_handling_units'] == 1 and cell['stacking_allowed'] is False, 'N2_STACKING_OR_CAPACITY_CHANGED')
        root = cell['support_root_world']['position_m']
        identity_frame(cell['support_root_world']);identity_frame(cell['HU_root_world'])
        need(root[1] == 0 and all(abs(x-y)<1e-12 for x,y in zip(cell['HU_root_world']['position_m'],add(root,(0,.18,.05)))), 'N2_WORLD_FRAME_CHANGED')
        for w in cell['native_support_floor_witnesses']:
            a = w['point_world_m']; b=w['floor_native']
            na = face(support_path,w['support_node'],w['support_triangle'],a,(root,))
            floor_path = next(p for p in n2['source_hashes'] if p.endswith('/environment-shell.glb'))
            nb = face(floor_path,b['node'],b['triangle'],b['point_m'])
            pair(a,b['point_m'],a)
            need(dot(na,nb) < -.99999, 'N2_FLOOR_NORMALS_NOT_OPPOSED')
            counts['N2_support_floor'] += 1

    design_path='docs/v3/contract-proposals/vehicle-handling-v3.json'
    need(design_path in n3['source_hashes'], 'DEREFERENCED_LOAD_SOURCE_NOT_PINNED')
    source_load=next(r for r in read(REPO/design_path)['loads'] if r['archetype_id']=='LONG_BUNDLE')
    need(n3['load']['HU_gross_mass_kg']==source_load['HU_gross_mass_kg'] and n3['load']['attachment_total_including_upper_rig_kg']==source_load['attachment_mass_kg'], 'N3_COMPONENT_MASS_CHANGED')
    need(n3['load']['total_lifted_mass_kg'] == n3['load']['HU_gross_mass_kg'] + n3['load']['attachment_total_including_upper_rig_kg'] == 240, 'N3_MASS_CHANGED')
    need(n3['load']['HU_instances'] == 1 and n3['load']['quantity_units'] == 24, 'N3_HU_IDENTITY_CHANGED')
    need(n3['load']['dimensions_xyz_m'] == [4.2,.52,.65], 'N3_DIMENSIONS_CHANGED')
    need(n3['frames']['cradle_to_vehicle_travel']['position_m'] == [0,.65,1], 'N3_MOUNT_FRAME_CHANGED')
    identity_frame(n3['frames']['cradle_to_vehicle_travel'])
    for path, rows in n3['native_witnesses'].items():
        for w in rows:
            a,b = w['down'],w['up']
            refs = [a['native_ref'],b['native_ref']]
            na = face(path,refs[0]['node_index'],refs[0]['triangle_index'],a['point_asset_m'],primitive=refs[0]['primitive_index'])
            nb = face(path,refs[1]['node_index'],refs[1]['triangle_index'],b['point_asset_m'],primitive=refs[1]['primitive_index'])
            pair(a['point_asset_m'],b['point_asset_m'],w['expected_vehicle_m'])
            need(dot(na,nb) < -.99999, 'N3_LOADED_NORMALS_NOT_OPPOSED')
            counts['N3_loaded'] += 1
    station=n3['proposed_stow_station']
    need(type(station['rig_yaw_rad']) in (int,float) and station['rig_yaw_rad']==0, 'UNVERIFIED_STOW_RIG_YAW')
    need(station['rig_scale']==[1,1,1] and all(type(v) in (int,float) for v in station['rig_scale']), 'UNVERIFIED_STOW_RIG_SCALE')
    need(station['upper_hinge_delta_rad']==[0,0] and station['keeper_delta_local_x_m']==[0,0,0,0], 'UNVERIFIED_STOW_CONTROL_POSE')
    for support in station['support_instances']:
        need(support['yaw_rad']==0 and support['scale']==[1,1,1] and all(type(v) in (int,float) for v in support['scale']), 'UNVERIFIED_STOW_SUPPORT_FRAME')
    need(station['capacity_rig_assemblies'] == 1 and station['HU_capacity'] == 0, 'N3_STOW_CAPACITY_CHANGED')
    def offsets(path):
        if path == support_path:
            return [s['root_world_position_m'] for s in station['support_instances']]
        if path.endswith('/long-restraint-rig.glb'):
            return [station['rig_root_world_position_m']]
        return [(0,0,0)]
    for w in station['contacts']:
        a,b=w['down'],w['up']; normals=[]
        for v in (a,b):
            ref=v['native_ref']
            normals.append(face(ref['path'],ref['node_index'],ref['triangle_index'],v['point_asset_m'],offsets(ref['path']),ref['primitive_index']))
        pair(a['point_asset_m'],b['point_asset_m'],w['expected_world_m'])
        need(dot(*normals) < -.99999, 'N3_STOW_NORMALS_NOT_OPPOSED')
        counts['N3_stow'] += 1
    need(counts['N2_HU_support'] >= 27 and counts['N2_HU_fork'] >= 18 and counts['N2_support_floor'] >= 12, 'N2_CONTACT_COVERAGE_INCOMPLETE')
    need(counts['N3_loaded'] >= 40 and counts['N3_stow'] >= 10, 'N3_CONTACT_COVERAGE_INCOMPLETE')
    return {'counts':counts,'maximum_native_triangle_error_m':maximum_triangle_error,'threshold_m':EPS}


def negative_controls(n2, n3):
    mutations = [
        ('N2 wrong support height', lambda a,b: a['cargo_interfaces'][0]['HU_root_in_proposed_support_frame']['position_m'].__setitem__(1,.19)),
        ('N2 point off actual triangle', lambda a,b: a['cargo_interfaces'][0]['native_support_patch_witnesses'][0]['HU_native']['point_m'].__setitem__(1,.19)),
        ('N2 wrong native face', lambda a,b: a['cargo_interfaces'][0]['native_support_patch_witnesses'][0]['HU_native'].__setitem__('triangle',0)),
        ('N2 wrong actual fork spread', lambda a,b: a['cargo_interfaces'][0]['fork_interface'].__setitem__('fork_centres_x_m',[-.25,.25])),
        ('N2 excess finite capacity', lambda a,b: a['staging_cells'].append(deepcopy(a['staging_cells'][0]))),
        ('N3 changed whole HU dimensions', lambda a,b: b['load']['dimensions_xyz_m'].__setitem__(0,4.19)),
        ('N3 missing attachment mass', lambda a,b: b['load'].__setitem__('total_lifted_mass_kg',200)),
        ('N3 wrong mount height', lambda a,b: b['frames']['cradle_to_vehicle_travel']['position_m'].__setitem__(1,.64)),
        ('N3 floating stow geometry', lambda a,b: b['proposed_stow_station']['rig_root_world_position_m'].__setitem__(1,.08)),
        ('N2 upside-down HU quaternion', lambda a,b: a['cargo_interfaces'][0]['HU_root_in_proposed_support_frame'].__setitem__('quaternion',[0,0,1,0])),
        ('N2 rescaled support frame', lambda a,b: a['staging_cells'][0]['support_root_world'].__setitem__('scale',[1,2,1])),
        ('N3 rotated stow assembly', lambda a,b: b['proposed_stow_station'].__setitem__('rig_yaw_rad',math.pi/2)),
        ('N3 exchanged component masses', lambda a,b: (b['load'].__setitem__('HU_gross_mass_kg',201),b['load'].__setitem__('attachment_total_including_upper_rig_kg',39))),
        ('Missing actual GLB source pin', lambda a,b: (a['source_hashes'].pop('frontend/public/models/v3/pallet-load.glb',None),b['source_hashes'].pop('frontend/public/models/v3/pallet-load.glb',None))),
    ]
    results=[]
    for name, mutate in mutations:
        a,b=deepcopy(n2),deepcopy(n3);mutate(a,b)
        try:
            verify_native(a,b)
        except (ValueError, KeyError, IndexError) as error:
            results.append({'case':name,'rejected':True,'reason':str(error)})
        else:
            raise ValueError('Negative control unexpectedly accepted: '+name)
    return results


def verify_current_input():
    current=read(PACKAGE/'n3-current-input.json');pair=read(PACKAGE/'n3-current-pair.json')
    verify_sources(current,require_units=False)
    historical=read(REPO/current['historical_input_ref']['path'])
    fixture=read(REPO/current['base_fixture_ref']['path'])
    need(current['inputs']==historical['inputs'],'N3_INPUT_PHYSICAL_ROWS_CHANGED')
    need(current['long_requirements']==historical['long_requirements'] and current['upstream_handling_units']==historical['upstream_handling_units'],'N3_LONG_REQUIREMENTS_CHANGED')
    for key,count in [('initial_stock',530),('skus',200),('workers',24),('vehicles',2),('ports',6)]:
        need(len(current['inputs'][key])==count and current['inputs'][key]==fixture['inputs'][key],'CURRENT_N3_BASE_MISMATCH:'+key)
    need(len(current['inputs']['requests'])==20 and len(current['upstream_handling_units'])==12 and len(current['long_requirements'])==6,'N3_REQUEST_CONSERVATION_FAILED')
    need(all(current[key] is False for key in ['engine_operation','actual_engine_run','execution_ready','operational_admission']),'N3_FABRICATED_EXECUTION_FLAG')
    need(current['actions']==[] and current['completion_events']==[],'N3_FABRICATED_ACTIONS')
    refs=[r['input_ref'] for r in pair['paired_runs']]
    need(len(refs)==2 and refs[0]==refs[1],'N3_BASELINE_ADAPTIVE_BYTES_DIFFER')
    path=REPO/refs[0]['path']
    need(path.resolve()==(PACKAGE/'n3-current-input.json').resolve() and refs[0]['sha256']==sha(path) and refs[0]['bytes']==path.stat().st_size and refs[0]['inputs_sha256']==current['inputs_sha256'],'N3_PAIR_SOURCE_MISMATCH')
    need(sha(REPO/current['base_fixture_ref']['path'])==current['base_fixture_ref']['sha256'],'N3_CURRENT_FIXTURE_EPOCH_MISMATCH')
    return {'physical_rows_equal_historical':True,'physical_rows_equal_current_base':True,'same_pair_bytes':True,'initial_HUs':530,'actors':24,'vehicles':2,'requests':20}


def verify_bundle():
    from jsonschema import Draft202012Validator
    bundle=read(PACKAGE/'bundle.json')
    Draft202012Validator(read(PACKAGE/'bundle.schema.json')).validate(bundle)
    verify_sources(bundle)
    members={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p.name!='bundle.json' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    need(members==set(bundle['artifacts']),'PACKET_ARTIFACT_MEMBERSHIP_DRIFT')
    for name,pin in bundle['artifacts'].items():
        path=(PACKAGE/name).resolve(strict=True)
        need(path.is_relative_to(PACKAGE) and path.relative_to(PACKAGE).as_posix()==name,'PACKET_ARTIFACT_PATH_ESCAPE')
        need(sha(path)==pin['sha256'] and path.stat().st_size==pin['bytes'],'PACKET_ARTIFACT_DRIFT:'+name)
    for pin in [*bundle['sections'].values(),*bundle.get('extensions',{}).values()]:
        path=PACKAGE/pin['path'];need(sha(path)==pin['sha256'] and read(path)['schema_id']==pin['schema_id'],'PACKET_SECTION_DRIFT')
    return {'sha256':sha(PACKAGE/'bundle.json'),'artifacts':len(members),'source_count':len(bundle['source_hashes'])}


def route_negative_controls(routes,n2,n3):
    mutations=[
        ('jump between segments',lambda p:p['connectors'][0]['segments'][1]['start_pose']['position_m'].__setitem__(0,130)),
        ('wrong native turn radius',lambda p:p['connectors'][0]['segments'][0]['geometry'].__setitem__('icr_vehicle_local_x_m',.1)),
        ('bare profile substituted for loaded HU',lambda p:p['connectors'][0].__setitem__('geometry_profile_components_local_m',p['connectors'][0]['geometry_profile_components_local_m'][:1])),
        ('source obstacle omitted',lambda p:p['geometry_obstacles'].pop(0)),
        ('fake source join position',lambda p:p['connectors'][0]['start']['pose']['position_m'].__setitem__(0,130)),
        ('zero clearance padding',lambda p:p['connectors'][0].__setitem__('padding_m',0)),
        ('copied C08 fork height changed',lambda p:p['loaded_profiles'][0].__setitem__('fork_top_travel_y_m',.1)),
        ('packing obstacle identity swapped',lambda p:p['geometry_obstacles'].__setitem__(224,{**deepcopy(p['geometry_obstacles'][223]),'id':'PK06'})),
    ]
    results=[]
    for name,mutate in mutations:
        data=deepcopy(routes);mutate(data)
        try:
            verify_route_geometry(data,REPO,n2,n3)
        except (ValueError,KeyError,IndexError) as error:
            results.append({'case':name,'rejected':True,'reason':str(error)})
        else:
            raise ValueError('Invalid route accepted: '+name)
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging',type=Path,default=PACKAGE/'n2-staging.json')
    parser.add_argument('--retention',type=Path,default=PACKAGE/'n3-retention.json')
    parser.add_argument('--routes',type=Path,default=PACKAGE/'route-terminal-interfaces.json')
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--negative-controls',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();n2,n3=read(args.staging),read(args.retention)
    verify_sources(n2);verify_sources(n3)
    native=verify_native(n2,n3)
    packet=current=route_geometry=route_report=None
    negatives=negative_controls(n2,n3) if args.negative_controls else []
    if not args.native_only:
        routes=read(args.routes);verify_sources(routes)
        need(routes.get('ready') is True,'ROUTE_INTERFACE_NOT_READY')
        need(routes.get('connectors') and routes.get('route_examples'),'ROUTE_JOIN_EXAMPLES_REQUIRED')
        route_geometry=verify_route_geometry(routes,REPO,n2,n3)
        current=verify_current_input();packet=verify_bundle()
        child=subprocess.run([sys.executable,str(PACKAGE/'verify_route_packet.py'),'--repo',str(REPO)],cwd=REPO,capture_output=True,text=True,timeout=60)
        need(child.returncode==0,'SOURCE_GRAPH_ROUTE_GUARD_FAILED:'+child.stdout[-2000:]+child.stderr[-1000:])
        route_report=json.loads(child.stdout.splitlines()[0])
        if args.negative_controls:
            negatives+=route_negative_controls(routes,n2,n3)
    result={'passed':True,'complete_packet_verified':not args.native_only,'scope':'Source-pinned physical API handoff; no operational workflow admission','bundle':packet,'current_input':current,'native':native,'continuous_route_geometry':route_geometry,'source_graph_route_checks':route_report,'negative_controls':negatives}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
