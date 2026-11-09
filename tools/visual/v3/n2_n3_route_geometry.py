"""Independent continuous planar bounds and kinematic checks for terminal joins."""
from __future__ import annotations

import json
import math


def require(value, reason):
    if not value:
        raise ValueError(reason)


def near(a,b,epsilon=1e-8):
    return len(a)==len(b) and all(abs(x-y)<=epsilon for x,y in zip(a,b))


def wrap(value):
    return math.atan2(math.sin(value),math.cos(value))


def same_json(a,b):
    if isinstance(a,bool) or isinstance(b,bool):
        return type(a) is type(b) and a==b
    if isinstance(a,dict) or isinstance(b,dict):
        return isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys() and all(same_json(a[k],b[k]) for k in a)
    if isinstance(a,list) or isinstance(b,list):
        return isinstance(a,list) and isinstance(b,list) and len(a)==len(b) and all(same_json(x,y) for x,y in zip(a,b))
    return a==b


def trig_range(a,b,start,end):
    low,high=sorted((start,end));points=[low,high]
    phase=math.atan2(b,a)
    for k in range(math.floor((low-phase)/math.pi)-1,math.ceil((high-phase)/math.pi)+2):
        t=phase+k*math.pi
        if low<=t<=high:
            points.append(t)
    values=[a*math.cos(t)+b*math.sin(t) for t in points]
    return min(values),max(values)


def root_at(segment,u):
    geometry=segment['geometry'];a,b=segment['start_pose'],segment['end_pose']
    yaw=a['yaw_rad']+(b['yaw_rad']-a['yaw_rad'])*u
    if geometry['kind']=='line':
        p=[x+(y-x)*u for x,y in zip(a['position_m'],b['position_m'])]
    else:
        cx,cz=geometry['icr_world_xz_m'];r=geometry['icr_vehicle_local_x_m']
        p=[cx-r*math.cos(yaw)-.4*math.sin(yaw),0,cz+r*math.sin(yaw)-.4*math.cos(yaw)]
    return p,yaw


def interval_bounds(segment,component,lo,hi,padding):
    xs,zs=[],[]
    corners=[(x,z) for x in (component['min'][0],component['max'][0]) for z in (component['min'][2],component['max'][2])]
    geometry=segment['geometry']
    if geometry['kind']=='line':
        for u in (lo,hi):
            p,yaw=root_at(segment,u);c,s=math.cos(yaw),math.sin(yaw)
            for x,z in corners:
                xs.append(p[0]+c*x+s*z);zs.append(p[2]-s*x+c*z)
    else:
        cx,cz=geometry['icr_world_xz_m'];r=geometry['icr_vehicle_local_x_m']
        a=segment['start_pose']['yaw_rad'];dy=segment['end_pose']['yaw_rad']-a
        for x,z in corners:
            xr=trig_range(x-r,z-.4,a+dy*lo,a+dy*hi)
            zr=trig_range(z-.4,-(x-r),a+dy*lo,a+dy*hi)
            xs.extend(cx+v for v in xr);zs.extend(cz+v for v in zr)
    return min(xs)-padding,max(xs)+padding,min(zs)-padding,max(zs)+padding


def separated(a,b):
    return a[1]<=b[0]+1e-10 or b[1]<=a[0]+1e-10 or a[3]<=b[2]+1e-10 or b[3]<=a[2]+1e-10


def verify_route_geometry(packet,repo,n2,n3):
    cache={}
    def source(path):
        require(path in packet['source_hashes'],'UNPINNED_ROUTE_SOURCE:'+path)
        if path not in cache:
            cache[path]=json.loads((repo/path).read_text(encoding='utf-8'))
        return cache[path]
    def pointer(ref):
        value=source(ref['repo_path'])
        for key in ref['json_pointer'].split('/')[1:]:
            key=key.replace('~1','/').replace('~0','~')
            value=value[int(key)] if isinstance(value,list) else value[key]
        return value
    cells={r['cell_id']:r for r in packet['staging_cells']}
    cell_bounds={k:v['floor_bounds_xz_m'] for k,v in cells.items()}
    for cell in n2['staging_cells']:
        require(cell['cell_id'] in cells and cell_bounds[cell['cell_id']]==cell['floor_bounds_xz_m'],'N2_ROUTE_CELL_FRAME_MISMATCH')
    storage_path='docs/v3/contract-proposals/storage-layout-v3.json'
    conveyor_path='docs/v3/contract-proposals/conveyor-v3.json'
    modules=source(storage_path)['modules'];conveyor=source(conveyor_path)
    canonical={m['module_id']:(storage_path,f'/modules/{i}/operating_bounds_world') for i,m in enumerate(modules)}
    canonical.update({m['module_id']:(conveyor_path,f'/physical_modules/{i}/floor_bounds_xz') for i,m in enumerate(conveyor['physical_modules'])})
    canonical.update({m['pack_id']:(conveyor_path,f'/packing_stations/{i}') for i,m in enumerate(conveyor['packing_stations'])})
    obstacles=[];source_ids=set()
    for row in packet['geometry_obstacles']:
        box=row['bounds'];identifier=row['id']
        require(identifier not in source_ids,'DUPLICATE_ROUTE_OBSTACLE')
        source_ids.add(identifier)
        if 'source' in row:
            require(identifier in canonical and (row['source']['repo_path'],row['source']['json_pointer'])==canonical[identifier],'SOURCE_OBSTACLE_ID_REFERENCE_MISMATCH:'+identifier)
            require(row['source']['sha256']==packet['source_hashes'][row['source']['repo_path']],'SOURCE_OBSTACLE_PIN_MISMATCH')
            original=pointer(row['source'])
            if 'min' in original and 'max' in original:
                indices=(0,2) if len(original['min'])==3 else (0,1)
                expected=[original['min'][indices[0]],original['max'][indices[0]],original['min'][indices[1]],original['max'][indices[1]]]
            else:
                x,_,z=original['table_origin'];dx,_,dz=original['table_dimensions_m']
                expected=[x-dx/2,x+dx/2,z-dz/2,z+dz/2]
        elif identifier in cell_bounds:
            original=cell_bounds[identifier]
            expected=[original['min'][0],original['max'][0],original['min'][1],original['max'][1]]
        else:
            require(identifier==n3['proposed_stow_station']['station_id'],'UNKNOWN_PROPOSED_ROUTE_OBSTACLE:'+identifier)
            original=n3['proposed_stow_station']['allocation_world_m']
            expected=[original['min'][0],original['max'][0],original['min'][2],original['max'][2]]
        actual=[box['min'][0],box['max'][0],box['min'][2],box['max'][2]]
        require(near(actual,expected),'SOURCE_ROUTE_OBSTACLE_BOUNDS_CHANGED:'+identifier)
        obstacles.append((identifier,tuple(actual)))
    require(all(identifier in source_ids for identifier in canonical),'SOURCE_STORAGE_OBSTACLE_OMITTED')
    require(len(packet['geometry_obstacles'])==len(modules)+len(conveyor['physical_modules'])+len(conveyor['packing_stations'])+len(cells)+1,'ROUTE_OBSTACLE_COVERAGE_CHANGED')
    profiles={p['archetype_id']:p for p in packet['loaded_profiles']}
    for profile in profiles.values():
        original=pointer(profile['source'])
        require(same_json({k:v for k,v in profile.items() if k!='source'},original),'SOURCE_LOADED_PROFILE_CHANGED')
    counts={'connectors':0,'segments':0,'continuous_intervals':0}
    for connection in packet['connectors']:
        require(connection['analytic_profile_clear'] is True and connection['source_existing_connector'] is False,'UNPROVED_CONNECTOR')
        require(connection['source_arc_reuse']==[] and connection['normal_travel_reach_extension_m']==0,'UNSUPPORTED_TRAVEL_OVERRIDE')
        require(connection['padding_m']==.25,'PADDED_PROFILE_MARGIN_CHANGED')
        require(connection['excluded_intended_terminal_id']==connection['cell_id'],'WRONG_TARGET_EXCLUSION')
        profile=profiles[connection['archetype_id']]
        target=cell_bounds[connection['cell_id']]
        cargo_z=(profile['cargo_bounds_local_m']['min'][2]+profile['cargo_bounds_local_m']['max'][2])/2
        terminal_z=(target['min'][1]+target['max'][1])/2-cargo_z-.4
        if 'empty' in connection['purpose']:
            terminal_z-=abs(n3['rack_removal_geometry']['withdrawal_delta_rack_m'][2]) if connection['archetype_id']=='LONG_BUNDLE' else 1.05
        terminal=connection['end'] if connection['purpose'].endswith('arrival') else connection['start']
        require(near(terminal['pose']['position_m'],[(target['min'][0]+target['max'][0])/2,0,terminal_z]) and abs(wrap(terminal['pose']['yaw_rad']))<1e-9,'WRONG_HANDLING_TARGET_FRAME')
        expected=profile['component_bounds_local_m']
        if 'empty' in connection['purpose']:
            expected=expected[:1]
            if connection['archetype_id']=='LONG_BUNDLE':
                expected=expected+[{'min':[-1.6,.65,.575],'max':[1.6,.8,1.425]}]
        require(connection['geometry_profile_components_local_m']==expected,'CONNECTOR_PROFILE_UNDERESTIMATED')
        for endpoint in (connection['start'],connection['end']):
            ref=endpoint.get('source_node_reference')
            if ref:
                node=pointer(ref)
                require(endpoint['node_id']==node['node_id'] and near(endpoint['pose']['position_m'],node['world_pos']) and abs(wrap(endpoint['pose']['yaw_rad']-node['yaw_rad']))<1e-9,'SOURCE_JOIN_POSE_CHANGED')
        previous=connection['start']['pose']
        for segment in connection['segments']:
            a,b=segment['start_pose'],segment['end_pose'];geometry=segment['geometry']
            require(near(a['position_m'],previous['position_m']) and abs(wrap(a['yaw_rad']-previous['yaw_rad']))<1e-9,'DISCONTINUOUS_CONNECTOR')
            for endpoint in (a,b):
                yaw=endpoint['yaw_rad'];q=endpoint['quaternion_xyzw'];wanted=[0,math.sin(yaw/2),0,math.cos(yaw/2)]
                require(all(type(v) in (int,float) and math.isfinite(v) for v in endpoint['position_m']+q+endpoint['scale']+[yaw]),'NONNUMERIC_CONNECTOR_POSE')
                require(near(q,wanted) or near(q,[-v for v in wanted]),'YAW_QUATERNION_MISMATCH')
                require(endpoint['position_m'][1]==0 and endpoint['scale']==[1,1,1],'CONNECTOR_FRAME_SCALE_OR_FLOOR')
            require(geometry['kind'] in ('line','rear_steer_arc'),'UNKNOWN_CONNECTOR_GEOMETRY')
            require(near(root_at(segment,0)[0],a['position_m']) and near(root_at(segment,1)[0],b['position_m']),'ARC_ROOT_KINEMATICS_MISMATCH')
            if geometry['kind']=='line':
                require(abs(a['yaw_rad']-b['yaw_rad'])<1e-10,'IN_PLACE_YAW_ON_LINE')
                yaw=a['yaw_rad'];dx=b['position_m'][0]-a['position_m'][0];dz=b['position_m'][2]-a['position_m'][2]
                require(abs(dx*math.cos(yaw)-dz*math.sin(yaw))<1e-8,'LATERAL_VEHICLE_SLIDE')
                require((dx*math.sin(yaw)+dz*math.cos(yaw))*segment['motion_direction']>=-1e-9,'WRONG_TRAVEL_DIRECTION')
                length=math.hypot(dx,dz)
            else:
                radius=geometry['icr_vehicle_local_x_m'];dy=b['yaw_rad']-a['yaw_rad']
                require(abs(radius)>=.8082903768654762-1e-10 and radius*dy*segment['motion_direction']>0,'INVALID_REAR_STEER_CURVATURE')
                length=math.hypot(radius,.4)*abs(dy)
            require(abs(length-segment['root_path_length_m'])<1e-8,'CONNECTOR_DISTANCE_CHANGED')
            relevant=[o for identifier,o in obstacles if identifier!=connection['cell_id']]
            for component in expected:
                def clear(lo,hi,depth):
                    counts['continuous_intervals']+=1
                    bounds=interval_bounds(segment,component,lo,hi,.25)
                    require(bounds[0]>=-1e-8 and bounds[1]<=144+1e-8 and bounds[2]>=-1e-8 and bounds[3]<=72+1e-8,'PADDED_PROFILE_OUTSIDE_FLOOR')
                    if all(separated(bounds,o) for o in relevant):
                        return
                    require(depth<24,'PADDED_PROFILE_COLLISION_OR_UNRESOLVED_INTERVAL')
                    middle=(lo+hi)/2;clear(lo,middle,depth+1);clear(middle,hi,depth+1)
                clear(0,1,0)
            previous=b;counts['segments']+=1
        require(near(previous['position_m'],connection['end']['pose']['position_m']) and abs(wrap(previous['yaw_rad']-connection['end']['pose']['yaw_rad']))<1e-9,'WRONG_TERMINAL_POSE')
        counts['connectors']+=1
    require(counts['connectors']>=80,'TERMINAL_CONNECTOR_COVERAGE_INCOMPLETE')
    return counts
