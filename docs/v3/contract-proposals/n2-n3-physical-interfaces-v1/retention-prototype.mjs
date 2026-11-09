/** Data-only API proposal. No imports, globals, geometry/actor writes or stock events. */
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const triple=a=>Array.isArray(a)&&a.length===3&&a.every(finite);
const requireValue=(v,m)=>{if(!v)throw Error(m);};
const freeze=v=>{if(v&&typeof v==='object'){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;};
const pair=(a,ranges)=>Array.isArray(a)&&a.length===ranges.length&&a.every((x,i)=>finite(x)&&x>=ranges[i][0]&&x<=ranges[i][1]);
const sourceGuard=d=>requireValue(d?.schema_id==='qoima.n3.long-retention-interfaces.v1'&&d.schema_version==='1.0.0'&&d.source_kind==='visual_fixture'&&d.engine_operation===false&&d.operational_workflow_admitted===false,'UNSUPPORTED_INTERFACE_DEFINITION');

export function sampleLongFrames(definition,pose){
 requireValue(arguments.length===2,'UNSUPPORTED_RELATIVE_VARIANT_SELECTOR');
 sourceGuard(definition);
 requireValue(pose&&triple(pose.vehicle_world_position_m)&&pose.vehicle_world_position_m[1]===0&&finite(pose.vehicle_yaw_rad),'INVALID_FLOOR_VEHICLE_POSE');
 const fields=['vehicle_world_position_m','vehicle_yaw_rad','fork_top_y_m','reach_extension_m','lower_lock_delta_y_m','upper_hinge_delta_x_rad','keeper_delta_x_m'];
 requireValue(Object.keys(pose).every(k=>fields.includes(k)),'UNSUPPORTED_RELATIVE_VARIANT_OR_POSE_FIELD');
 const {fork_top_y_m:top,reach_extension_m:e}=pose;
 requireValue(finite(top)&&finite(e)&&top>=.18&&top<=1.5&&e>=0&&e<=.4,'NATIVE_LIFT_REACH_RANGE');
 requireValue(pair(pose.lower_lock_delta_y_m,[[0,.11],[0,.11]])&&pair(pose.upper_hinge_delta_x_rad,[[-80*Math.PI/180,0],[-80*Math.PI/180,0]])&&pair(pose.keeper_delta_x_m,[[-.35,0],[-.35,0],[0,.35],[0,.35]]),'NATIVE_RETENTION_CONTROL_RANGE');
 const yaw=pose.vehicle_yaw_rad,c=Math.cos(yaw),s=Math.sin(yaw),p=pose.vehicle_world_position_m;
 const world=v=>[p[0]+c*v[0]+s*v[2],p[1]+v[1],p[2]-s*v[0]+c*v[2]];
 const q=[0,Math.sin(yaw/2),0,Math.cos(yaw/2)];
 const frame=v=>({position_m:world(v),quaternion_xyzw:[...q],scale:[1,1,1]});
 const closed=[...pose.lower_lock_delta_y_m,...pose.upper_hinge_delta_x_rad,...pose.keeper_delta_x_m].every(x=>x===0);
 const region=(e===.4&&top>=.2&&top<=1.5)||(top>=.75&&top<=1.5);
 const pressure=definition.upper_restraint.twelve_pressure_contacts_cradle_m.map(v=>{
  const angle=pose.upper_hinge_delta_x_rad[v[0]<0?0:1],ca=Math.cos(angle),sa=Math.sin(angle),dy=v[1]-.62,dz=v[2]+.28;
  return world([v[0],top-.10+.62+ca*dy-sa*dz,1+e-.28+sa*dy+ca*dz]);
 });
 const keepers=definition.upper_restraint.keeper_controls.map((k,i)=>world([k.position_cradle_m[0]+pose.keeper_delta_x_m[i],top-.10+k.position_cradle_m[1],1+e+k.position_cradle_m[2]]));
 return freeze({source_kind:'visual_fixture',engine_operation:false,operational_workflow_admitted:false,cradle_world:frame([0,top-.10,1+e]),HU_bottom_world:frame([0,top+.05,1+e]),lower_support_points_world_m:definition.cradle_interface.four_support_points_cradle_m.map(v=>world([v[0],top-.10+v[1],1+e+v[2]])),upper_pressure_points_world_m:pressure,lower_lock_axis_points_world_m:definition.lower_positive_locks.pin_axes_cradle_m.map((v,i)=>world([v[0],top-.10+v[1]+pose.lower_lock_delta_y_m[i],1+e+v[2]])),keeper_origins_world_m:keepers,native_control_ranges_valid:true,historical_closed_pose_region:region&&closed});
}

export function prepareRetentionEvent(definition,command){
 requireValue(arguments.length===2,'UNSUPPORTED_RELATIVE_VARIANT_SELECTOR');
 sourceGuard(definition);
 requireValue(command?.schema_id==='qoima.n3.long-retention-command.v1'&&command.source_kind==='visual_fixture'&&command.engine_operation===false,'INVALID_RETENTION_COMMAND_SCOPE');
 const fields=['schema_id','source_kind','engine_operation','event_id','event_type','absolute_time_s','actor_id','vehicle_id','from_state','to_state','pose','required_resource_refs','same_HU_instance_ref','source_hashes','geometry_proof_ref','native_continuous_manual_trajectory_proof_ref'];
 requireValue(Object.keys(command).every(k=>fields.includes(k)),'UNSUPPORTED_RELATIVE_VARIANT_OR_COMMAND_FIELD');
 requireValue((command.actor_id==='F01'&&command.vehicle_id==='FL01')||(command.actor_id==='F02'&&command.vehicle_id==='FL02'),'EXISTING_ACTOR_VEHICLE_PAIR_REQUIRED');
 requireValue(typeof command.event_id==='string'&&command.event_id.length>0&&finite(command.absolute_time_s)&&command.absolute_time_s>=0,'INVALID_RETENTION_EVENT_ID_OR_TIME');
 const names=definition.command_interface.event_type.split('|');
 requireValue(names.includes(command.event_type),'UNKNOWN_RETENTION_EVENT');
 const states=[...definition.state_event_interface.known_geometric_states,'upper_rig_stowed_at_proposed_station'];
 requireValue(states.includes(command.from_state)&&states.includes(command.to_state),'UNKNOWN_RETENTION_STATE');
 if(['engage_HU','setdown_HU','release_HU'].includes(command.event_type))requireValue(typeof command.same_HU_instance_ref==='string'&&command.same_HU_instance_ref.length>0,'SAME_EXISTING_WHOLE_HU_REFERENCE_REQUIRED');
 requireValue(command.source_hashes&&Object.entries(definition.source_hashes).every(([path,sha])=>command.source_hashes[path]===sha),'RETENTION_SOURCE_PIN_MISMATCH');
 const r=command.required_resource_refs;
 requireValue(r&&['operator','vehicle','action_space'].every(k=>typeof r[k]==='string'&&r[k].length>0)&&Array.isArray(r.traffic_groups)&&r.traffic_groups.length>0&&r.traffic_groups.every(x=>typeof x==='string'&&x.length>0),'EXCLUSIVE_RESOURCE_REFERENCES_REQUIRED');
 requireValue(r.operator===command.actor_id&&r.vehicle===command.vehicle_id,'ACTOR_VEHICLE_RESOURCE_REFERENCE_MISMATCH');
 requireValue(typeof command.geometry_proof_ref==='string'&&command.geometry_proof_ref.length>0,'NATIVE_GEOMETRY_PROOF_REFERENCE_REQUIRED');
 sampleLongFrames(definition,command.pose);
 // A reference string is not a proof verifier or resource reservation.
 // This offline contract intentionally has no path that executes an operation.
 const conditions=['VERIFY_EXCLUSIVE_SOURCE_RESOURCES','VERIFY_NATIVE_SOURCE_PINNED_TRAJECTORY','BIND_SAME_EXISTING_WHOLE_HU_WHEN_LOADED'];
 if(['mount_upper','extract_keepers','extract_upper','stow_upper'].includes(command.event_type))conditions.push('NATIVE_MANUAL_TRANSPORT_AND_MOUNT_TRAJECTORY_REQUIRED');
 if(command.event_type==='stow_upper'){
  requireValue(r.stow_station===definition.proposed_stow_station.station_id,'EXPLICIT_STOW_STATION_REFERENCE_REQUIRED');
  conditions.push('SOURCE_STATION_RESOURCE_ALLOCATION_REQUIRED');
 }
 return freeze({event_executed:false,operational_workflow_admitted:false,actor_id:command.actor_id,vehicle_id:command.vehicle_id,required_conditions:conditions,refusal_reason:conditions.includes('NATIVE_MANUAL_TRANSPORT_AND_MOUNT_TRAJECTORY_REQUIRED')?'NATIVE_MANUAL_TRANSPORT_AND_MOUNT_TRAJECTORY_REQUIRED':'SOURCE_WORKFLOW_EXECUTION_NOT_IMPLEMENTED'});
}
