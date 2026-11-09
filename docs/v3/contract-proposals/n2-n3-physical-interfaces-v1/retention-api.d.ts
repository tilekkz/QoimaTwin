/** Additive data interface proposal. No Scene mutation or source operation. */
export type Vec3 = readonly [number, number, number];
export type Quat = readonly [number, number, number, number];
export type SidePair = readonly [number, number];
export type KeeperFour = readonly [number, number, number, number];
export type Pair = {actor_id:'F01'; vehicle_id:'FL01'} | {actor_id:'F02'; vehicle_id:'FL02'};
export type SourceHashes = Readonly<Record<string, string>>;
export interface FramePose {position_m:Vec3; quaternion_xyzw:Quat; scale:readonly [1,1,1]}
/** Current sampler supports original relativeyaw0 only. Relative-pi is separate
 * endpoint data for a future explicitly selected consumer, never an extra field. */
export interface LongPose {
  vehicle_world_position_m:Vec3;
  vehicle_yaw_rad:number;
  fork_top_y_m:number;
  reach_extension_m:number;
  /** Native cradle Y translations, closed0/open.11m. */
  lower_lock_delta_y_m:SidePair;
  /** Native upper-bar X deltas, closed0/open−80deg. */
  upper_hinge_delta_x_rad:SidePair;
  /** Lfront,Lrear,Rfront,Rrear. Outward L−.35m,R+.35m. */
  keeper_delta_x_m:KeeperFour;
}
export type RetentionState =
  | 'detached_empty_native_source'
  | 'installed_empty_pins_closed_upper_rig_stowed_required'
  | 'loaded_supported_lower_pins_closed_upper_bars_closed_keepers_closed'
  | 'stopped_handling_open_locks'
  | 'stopped_upper_keeper_extraction'
  | 'stopped_upper_rig_lift'
  | 'rack_supported_HU_cradle_lowered'
  | 'upper_rig_stowed_at_proposed_station';
export type RetentionEvent = 'prepare' | 'engage_cradle' | 'lock_lower'
  | 'engage_HU' | 'mount_upper' | 'lock_upper' | 'unlock_upper'
  | 'extract_keepers' | 'extract_upper' | 'stow_upper'
  | 'setdown_HU' | 'release_HU' | 'prepare_empty_travel';
export interface ResourceRefs {
  /** Must equal RetentionCommand.actor_id exactly. */
  operator:string;
  /** Must equal RetentionCommand.vehicle_id exactly. */
  vehicle:string;
  action_space:string;
  traffic_groups:readonly string[];
  stow_station?:'proposed:LONG-upper-rig-stow:IN_W:01';
}
export type RetentionCommand = Pair & {
  schema_id:'qoima.n3.long-retention-command.v1';
  source_kind:'visual_fixture';
  engine_operation:false;
  event_id:string;
  event_type:RetentionEvent;
  absolute_time_s:number;
  from_state:RetentionState;
  to_state:RetentionState;
  pose:LongPose;
  required_resource_refs:ResourceRefs;
  /** Existing complete200kg/24-unit HU identity; never creates stock. */
  same_HU_instance_ref?:string;
  source_hashes:SourceHashes;
  geometry_proof_ref:string;
  /** Required for mount/extract/stow; static endpoint support is insufficient. */
  native_continuous_manual_trajectory_proof_ref?:string;
};
export interface FrameSample {
  source_kind:'visual_fixture';
  engine_operation:false;
  operational_workflow_admitted:false;
  cradle_world:FramePose;
  HU_bottom_world:FramePose;
  lower_support_points_world_m:readonly Vec3[];
  upper_pressure_points_world_m:readonly Vec3[];
  lower_lock_axis_points_world_m:readonly Vec3[];
  keeper_origins_world_m:readonly Vec3[];
  native_control_ranges_valid:true;
  historical_closed_pose_region:boolean;
}
/** Data-only prototype; definition is the source-pinned handoff JSON. */
export function sampleLongFrames(definition:unknown, pose:LongPose):FrameSample;
/** Always reports an unexecuted proposal; external proof/resources are never forged. */
export function prepareRetentionEvent(definition:unknown, command:RetentionCommand):{
  event_executed:false;
  operational_workflow_admitted:false;
  actor_id:'F01'|'F02';
  vehicle_id:'FL01'|'FL02';
  required_conditions:readonly string[];
  refusal_reason:string;
};
