import {createWarehouseCargo} from './warehouseCargo';
import {isWarehouseScenarioPlan, type WarehouseScenarioPlan, type ScenarioExecutionJob} from './warehouseScenarioExecution';
import type {WarehouseBundle, WarehouseRequest, XYZ} from './warehouseTypes';

const N0_INPUTS_SHA256 = '81e7ae0a5289f6d165b4d982f44138565d9313af0c06b24ac72130fa2eb3397c';
const sourceActors = ['P01', 'P02'] as const;
type PendingActor = typeof sourceActors[number];
export type WarehouseStaffingPendingJob = Readonly<{
  task_id: string;
  job_id: string;
  request_id: string;
  handling_unit_id: string;
  assigned_actor_id: PendingActor;
  requested_at_s: number;
  port_id: string;
  archetype_id: string;
  sku_id: string;
  lot_id: string;
  quantity_units: number;
  gross_mass_kg: number;
  dimensions_xyz_m: readonly [number, number, number];
  position_world_m: readonly [number, number, number];
  yaw_rad: number;
  owner: Readonly<{kind: 'storage_slot'; id: string}>;
  remaining_work_s: null;
  origin: 'issued_N0_scenario_pending_job';
  source_snapshot_at_s: 0;
  source_job: Readonly<ScenarioExecutionJob>;
  source_request: Readonly<WarehouseRequest>;
}>;
export type WarehouseStaffingRetainedJob = WarehouseStaffingPendingJob & Readonly<{
  state: 'retained' | 'paused';
  release_state: 'not_released' | 'queued';
  work_executed: false;
  completed: false;
}>;
export type WarehouseStaffingPendingWork = Readonly<{
  source_kind: 'visual_fixture';
  engine_operation: false;
  source_materialized_input_sha256: string;
  source_work_sha256: string;
  source_epoch: WarehouseScenarioPlan['source_epoch'];
  source_snapshot_at_s: 0;
  pending_jobs: readonly WarehouseStaffingPendingJob[];
  outstanding_requests: 2;
  jobs_executed_in_staffing: false;
  source_stock_moved_in_staffing: false;
}>;
const issued = new WeakMap<object, {bundle: WarehouseBundle; actor_ids: ReadonlySet<string>}>();
function need(value: unknown, reason: string): asserts value { if (!value) throw Error(reason); }
function stable(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>;
    return '{' + Object.keys(row).sort().map(k => JSON.stringify(k) + ':' + stable(row[k])).join(',') + '}';
  }
  return JSON.stringify(value);
}
const digest = async(value: unknown) => [...new Uint8Array(await crypto.subtle.digest('SHA-256',
  new TextEncoder().encode(stable(value))))].map(v => v.toString(16).padStart(2, '0')).join('');
function freeze<T>(value: T): T {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
}
export function isWarehouseStaffingPendingWork(value: unknown, bundle?: WarehouseBundle): value is WarehouseStaffingPendingWork {
  if (!value || typeof value !== 'object') return false;
  const record = issued.get(value);
  return !!record && (bundle === undefined || record.bundle === bundle);
}

/** Capture outstanding work BEFORE either source request starts. The N4 episode
 * retains these exact jobs; it never runs their proposed scenario future. */
export async function createWarehouseStaffingPendingWork(
  bundle: WarehouseBundle, plan: WarehouseScenarioPlan,
): Promise<WarehouseStaffingPendingWork> {
  need(isWarehouseScenarioPlan(plan), 'ISSUED_PENDING_SCENARIO_PLAN_REQUIRED');
  need(Object.isFrozen(bundle) && bundle.source_kind === 'visual_fixture' && bundle.engine_operation === false,
    'VALIDATED_PENDING_WORK_BUNDLE_REQUIRED');
  const inputHash = await digest(bundle.fixture.inputs);
  need(inputHash === N0_INPUTS_SHA256 && plan.materialized_input_sha256 === inputHash &&
    plan.visual_extensions.length === 0 && plan.placement.kind === 'explicit_no_op', 'EXACT_N0_PENDING_INPUT_REQUIRED');
  const before = plan.sample(0), stock = createWarehouseCargo(bundle).snapshot();
  need(before.at_s === 0 && before.counts.workers === 24 && before.counts.vehicles === 2 &&
    before.counts.baseline_handling_units === 530 && stock.length === 530 &&
    stable(before.actors.map(a => a.actor_id).sort()) === stable(bundle.registry.workers.map(w => w.actor_id).sort()) &&
    stable(before.vehicles.map(v => v.vehicle_id).sort()) === stable(bundle.registry.vehicles.map(v => v.vehicle_id).sort()),
  'PENDING_WORK_POPULATION_MISMATCH');
  const stockFrames = new Map(before.cargo.filter(c => c.location.kind === 'storage_slot').map(c => [c.handling_unit_id, c]));
  need(stockFrames.size === 530, 'PENDING_WORK_SOURCE_STOCK_CHANGED');
  for (const source of stock) {
    const found = stockFrames.get(source.handling_unit_id);
    need(found && found.visible && !found.attached && source.destination.kind === 'storage_slot' &&
      stable([found.archetype_id, found.position, found.yaw_rad, found.location.id, found.dimensions_xyz_m,
        found.gross_mass_kg, found.quantity_units]) === stable([source.cargo.archetype_id, source.position,
        source.yaw_rad, source.destination.slot_id, source.cargo.dimensions_xyz_m,
        source.cargo.gross_mass_kg, source.cargo.quantity_units]), 'PENDING_WORK_SOURCE_STOCK_CHANGED');
  }
  const pending = sourceActors.map((actor, index): WarehouseStaffingPendingJob => {
    const requestID = 'v3:request:base:outbound:0' + (index + 1);
    const request = bundle.fixture.inputs.requests.find(r => r.request_id === requestID);
    const job = before.jobs.find(j => j.request_id === requestID);
    const cargo = request && stockFrames.get(request.handling_unit_id);
    const source = request && bundle.fixture.inputs.initial_stock.find(h => h.handling_unit_id === request.handling_unit_id);
    need(request && job && cargo && source && request.direction === 'outbound' &&
      request.requested_at_s === (index + 1) * 120 && job.actor_id === actor && job.actor_ids.includes(actor) &&
      job.status === 'not_released' && job.handling_unit_id === request.handling_unit_id &&
      job.port_id === request.port_id && request.quantity_units === cargo.quantity_units &&
      request.archetype_id === (index === 0 ? 'SMALL_CARTON' : 'STANDARD_CARTON'), 'EXACT_PENDING_PICKER_JOBS_REQUIRED');
    const planned = plan.jobs.find(j => j.job_id === job.job_id)!;
    return freeze({task_id: job.job_id, job_id: job.job_id, request_id: request.request_id,
      handling_unit_id: request.handling_unit_id, assigned_actor_id: actor,
      requested_at_s: request.requested_at_s, port_id: request.port_id, archetype_id: request.archetype_id,
      sku_id: source.sku_id, lot_id: source.lot_id, quantity_units: cargo.quantity_units,
      gross_mass_kg: cargo.gross_mass_kg, dimensions_xyz_m: [...cargo.dimensions_xyz_m] as XYZ,
      position_world_m: [...cargo.position!] as XYZ, yaw_rad: cargo.yaw_rad,
      owner: {kind: 'storage_slot' as const, id: cargo.location.id}, remaining_work_s: null,
      origin: 'issued_N0_scenario_pending_job' as const, source_snapshot_at_s: 0 as const,
      source_job: structuredClone(planned), source_request: structuredClone(request)});
  });
  const binding = freeze({source_kind: 'visual_fixture' as const, engine_operation: false as const,
    source_materialized_input_sha256: inputHash, source_work_sha256: await digest(pending),
    source_epoch: structuredClone(plan.source_epoch), source_snapshot_at_s: 0 as const,
    pending_jobs: pending, outstanding_requests: 2 as const,
    jobs_executed_in_staffing: false as const, source_stock_moved_in_staffing: false as const});
  issued.set(binding, {bundle, actor_ids: new Set(bundle.registry.workers.map(w => w.actor_id))});
  return binding;
}

export function sampleWarehouseStaffingPendingWork(
  binding: WarehouseStaffingPendingWork, actor_id: string, seconds: number, paused: boolean,
): WarehouseStaffingRetainedJob | null {
  need(isWarehouseStaffingPendingWork(binding), 'ISSUED_STAFFING_PENDING_WORK_REQUIRED');
  need(Number.isFinite(seconds) && seconds >= 0 && seconds <= 600 && typeof paused === 'boolean', 'INVALID_PENDING_WORK_TIME');
  need(issued.get(binding)!.actor_ids.has(actor_id), 'UNKNOWN_PENDING_WORK_ACTOR');
  const task = binding.pending_jobs.find(j => j.assigned_actor_id === actor_id);
  return task ? freeze({...task, state: paused ? 'paused' as const : 'retained' as const,
    release_state: seconds < task.requested_at_s ? 'not_released' as const : 'queued' as const,
    work_executed: false as const, completed: false as const}) : null;
}
