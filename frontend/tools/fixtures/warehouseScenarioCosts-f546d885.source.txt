import {isWarehouseScenarioPlan, type WarehouseScenarioPlan} from './warehouseScenarioExecution';

type Frozen<T> = T extends object ? {readonly [K in keyof T]: Frozen<T[K]>} : T;

export type WarehouseScenarioCostSnapshot = Frozen<{
  source_kind: 'visual_fixture';
  engine_operation: false;
  operational_admission: false;
  source_label: string;
  duration_unit: 'seconds';
  scenario_id: string;
  variant: WarehouseScenarioPlan['variant'];
  materialized_input_sha256: string;
  source_epoch: WarehouseScenarioPlan['source_epoch'];
  placement: WarehouseScenarioPlan['placement'];
  at_s: number;
  duration_s: number;
  request_wait_s: number;
  person_reservation_s: number;
  vehicle_reservation_s: number;
  post_reservation_s: number;
  empty_forklift_route_s?: number;
  empty_forklift_route_components_s?: {
    top_level: number;
    native_pallet: number;
    native_additional_heavy: number;
    native_long: number;
  };
  empty_forklift_route_scope: 'confirmed_route_schedule_phases';
  active_labor_s: null;
  paid_labor_s: null;
  inventory_relocation_s: 0 | null;
  counts: {
    requests: number;
    not_released: number;
    queued: number;
    travelling: number;
    completed_visual: number;
    refused: number;
    blocked: number;
  };
}>;

function freeze<T>(value: T): Frozen<T> {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value as Frozen<T>;
}

function dataKey(value: unknown): string {
  if (typeof value === 'function') return 'function';
  if (Array.isArray(value)) return '[' + value.map(dataKey).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return '{' + Object.keys(record).sort()
      .map(key => JSON.stringify(key) + ':' + dataKey(record[key])).join(',') + '}';
  }
  return JSON.stringify(value) ?? 'undefined';
}

const intersection = (start: number, end: number, at: number): number =>
  Math.max(0, Math.min(end, at) - Math.max(start, 0));

type NativeRoutePhase = {
  start_s: number; end_s: number; attached: boolean; path: {kind: string};
};
/** Native forks-only routes live inside issued episodes, separately from the
 * scheduler's empty return leg. Count their absolute local prefix once.
 * Explicit native hold/handling phases are excluded. A canonical W03 route
 * retains its published schedule duration, including internal steering dwells;
 * this is neither distance/speed nor a claim about active or paid labor. */
function nativeEmptyRouteSeconds(phases: readonly NativeRoutePhase[], at: number): number {
  if (!Number.isFinite(at) || at < 0) throw Error('INVALID_NATIVE_COST_TIME');
  let seconds = 0;
  for (const phase of phases) {
    if (!Number.isFinite(phase.start_s) || !Number.isFinite(phase.end_s) ||
        phase.end_s <= phase.start_s ||
        !['line', 'vehicle_arc', 'source_route', 'arc', 'route'].includes(phase.path.kind)) {
      throw Error('INVALID_NATIVE_COST_PHASE');
    }
    if (!phase.attached && phase.path.kind !== 'line') {
      seconds += intersection(phase.start_s, phase.end_s, at);
    }
  }
  return seconds;
}

/** Read-only schedule accounting. Reservations are neither labor nor throughput. */
export function summarizeWarehouseScenarioCosts(
  plan: WarehouseScenarioPlan,
  at_s?: number,
): WarehouseScenarioCostSnapshot {
  if (!isWarehouseScenarioPlan(plan)) throw Error('ISSUED_SCENARIO_PLAN_REQUIRED');
  if (!Number.isFinite(plan.duration_s) || plan.duration_s < 0) {
    throw Error('INVALID_SCENARIO_HORIZON');
  }
  const requested = at_s === undefined ? plan.duration_s : at_s;
  if (!Number.isFinite(requested)) throw Error('INVALID_SCENARIO_TIME');
  const at = Math.max(0, Math.min(plan.duration_s, requested));
  const jobIds = new Set(plan.jobs.map(job => job.job_id));
  if (jobIds.size !== plan.jobs.length) throw Error('DUPLICATE_SCENARIO_JOB');

  const resources = new Map<string, WarehouseScenarioPlan['leases']>();
  let person = 0, vehicle = 0, post = 0;
  for (const lease of plan.leases) {
    if (!jobIds.has(lease.job_id) || !lease.resource_id ||
        !Number.isFinite(lease.start_s) || !Number.isFinite(lease.end_s) ||
        lease.end_s < lease.start_s || lease.quantity !== 1 ||
        lease.capacity !== 1 || lease.semantics !== 'planned_half_open') {
      throw Error('INVALID_SCENARIO_COST_LEASE');
    }
    const group = resources.get(lease.resource_id) ?? [];
    group.push(lease);
    resources.set(lease.resource_id, group);
    const seconds = intersection(lease.start_s, lease.end_s, at) * lease.quantity;
    if (lease.resource_id.startsWith('actor:')) person += seconds;
    else if (lease.resource_id.startsWith('vehicle:')) vehicle += seconds;
    else if (lease.resource_id.startsWith('post:')) post += seconds;
  }
  // Sort private arrays; even duplicate claims within one job must not overlap.
  for (const [resource, leases] of resources) {
    leases.sort((a, b) => a.start_s - b.start_s || a.end_s - b.end_s);
    let previousEnd = -Infinity;
    for (const lease of leases) {
      if (lease.start_s === lease.end_s) continue;
      if (lease.start_s < previousEnd) {
        throw Error('OVERLAPPING_SCENARIO_LEASE:' + resource);
      }
      previousEnd = lease.end_s;
    }
  }

  const sample = plan.sample(at);
  if (sample.at_s !== at || sample.duration_s !== plan.duration_s ||
      sample.source_kind !== plan.source_kind || sample.engine_operation !== false ||
      sample.operational_admission !== false) {
    throw Error('SCENARIO_COST_SAMPLE_MISMATCH');
  }
  let waiting = 0;
  for (const job of sample.jobs) {
    // Runtime refusals occur at release; they do not remain waiting requests.
    if (job.status === 'not_released' || job.status === 'refused') continue;
    if (!Number.isFinite(job.requested_at_s) ||
        (job.start_s !== null && !Number.isFinite(job.start_s))) {
      throw Error('INVALID_SCENARIO_WAIT_TIME');
    }
    waiting += intersection(job.requested_at_s, job.start_s ?? at, at);
  }

  const confirmed = plan.routes.filter(route =>
    route.mode === 'forklift' && route.native_timing_confirmed);
  // Missing cargo metadata makes this total unavailable, rather than zero.
  const nativeCasesKnown = !!plan.native_heavy_plan ||
    !!plan.native_additional_heavy_plans?.length || !!plan.native_long_crossdock_plan;
  const cargoKnown = (confirmed.length > 0 || nativeCasesKnown) && confirmed.every(route =>
    'cargo_archetype_id' in route.plan &&
    (route.plan.cargo_archetype_id === null ||
      typeof route.plan.cargo_archetype_id === 'string'));
  let emptyRoute: number | undefined;
  let emptyComponents: WarehouseScenarioCostSnapshot['empty_forklift_route_components_s'];
  if (cargoKnown) {
    const components = {top_level: 0, native_pallet: 0, native_additional_heavy: 0, native_long: 0};
    const routes = new Map(confirmed.map(route => [route.route_id, route]));
    for (const job of sample.jobs) {
      if (!job.route_id || job.start_s === null ||
          job.status === 'not_released' || job.status === 'refused') continue;
      const route = routes.get(job.route_id);
      if (!route || !('cargo_archetype_id' in route.plan) ||
          route.plan.cargo_archetype_id !== null) continue;
      const end = job.start_s + route.duration_s;
      if (!Number.isFinite(route.duration_s) || route.duration_s < 0 ||
          !Number.isFinite(end)) throw Error('INVALID_CONFIRMED_ROUTE_TIME');
      // A zero-length preparation may adjust fork spacing but is not a route.
      if (route.length_m > 0) components.top_level += intersection(job.start_s, end, at);
    }
    if (sample.native_heavy_local_s !== null) {
      if (!plan.native_heavy_plan) throw Error('NATIVE_PALLET_COST_BINDING_REQUIRED');
      components.native_pallet = nativeEmptyRouteSeconds(
        plan.native_heavy_plan.fixture.phases, sample.native_heavy_local_s);
    }
    const additional = new Map(plan.native_additional_heavy_plans?.map(p => [p.case.case_id, p]));
    const seen = new Set<string>();
    for (const row of sample.native_additional_heavy) {
      const native = additional.get(row.case_id);
      if (!native || seen.has(row.case_id)) throw Error('NATIVE_ADDITIONAL_COST_BINDING_REQUIRED');
      seen.add(row.case_id);
      components.native_additional_heavy += nativeEmptyRouteSeconds(native.phases, row.local_s);
    }
    if (sample.native_long_local_s !== null) {
      if (!plan.native_long_crossdock_plan) throw Error('NATIVE_LONG_COST_BINDING_REQUIRED');
      components.native_long = nativeEmptyRouteSeconds(
        plan.native_long_crossdock_plan.phases, sample.native_long_local_s);
    }
    emptyComponents = components;
    emptyRoute = Object.values(components).reduce((total, value) => total + value, 0);
  }

  const snapshot: WarehouseScenarioCostSnapshot = {
    source_kind: 'visual_fixture',
    engine_operation: false,
    operational_admission: false,
    source_label: 'Визуальный повтор · резервы',
    duration_unit: 'seconds',
    scenario_id: plan.scenario_id,
    variant: plan.variant,
    materialized_input_sha256: plan.materialized_input_sha256,
    source_epoch: structuredClone(plan.source_epoch),
    placement: structuredClone(plan.placement),
    at_s: at,
    duration_s: plan.duration_s,
    request_wait_s: waiting,
    person_reservation_s: person,
    vehicle_reservation_s: vehicle,
    post_reservation_s: post,
    ...(emptyRoute === undefined ? {} : {
      empty_forklift_route_s: emptyRoute,
      empty_forklift_route_components_s: emptyComponents,
    }),
    empty_forklift_route_scope: 'confirmed_route_schedule_phases',
    active_labor_s: null,
    paid_labor_s: null,
    inventory_relocation_s: plan.placement.kind === 'explicit_no_op' &&
      plan.placement.inventory_relocations === 0 ? 0 : null,
    counts: {
      requests: sample.counts.requests,
      not_released: sample.counts.not_released,
      queued: sample.counts.queued,
      travelling: sample.counts.travelling,
      completed_visual: sample.counts.completed_visual,
      refused: sample.counts.refused,
      blocked: sample.counts.native_join_required,
    },
  };
  return freeze(snapshot);
}

export function compareWarehouseScenarioCosts(
  planA: WarehouseScenarioPlan,
  planB: WarehouseScenarioPlan,
  at_s?: number,
) {
  if (!isWarehouseScenarioPlan(planA) || !isWarehouseScenarioPlan(planB)) {
    throw Error('ISSUED_SCENARIO_PLAN_REQUIRED');
  }
  for (const key of [
    'materialized_input_sha256', 'source_epoch', 'duration_s', 'scenario_id',
  ] as const) {
    if (dataKey(planA[key]) !== dataKey(planB[key])) {
      throw Error('INCOMPARABLE_SCENARIO_COSTS:' + key);
    }
  }
  // Sampler closures are issuance-specific; all materialized public data must match.
  if (dataKey({...planA, variant: null, sample: null}) !==
      dataKey({...planB, variant: null, sample: null})) {
    throw Error('INCOMPARABLE_SCENARIO_MATERIALIZATION');
  }
  const a = summarizeWarehouseScenarioCosts(planA, at_s);
  const b = summarizeWarehouseScenarioCosts(planB, at_s);
  const seconds = {
    request_wait_s: b.request_wait_s - a.request_wait_s,
    person_reservation_s: b.person_reservation_s - a.person_reservation_s,
    vehicle_reservation_s: b.vehicle_reservation_s - a.vehicle_reservation_s,
    post_reservation_s: b.post_reservation_s - a.post_reservation_s,
    ...(a.empty_forklift_route_s === undefined || b.empty_forklift_route_s === undefined ? {} :
      {empty_forklift_route_s: b.empty_forklift_route_s - a.empty_forklift_route_s}),
    inventory_relocation_s: a.inventory_relocation_s === null ||
      b.inventory_relocation_s === null ? null :
      b.inventory_relocation_s - a.inventory_relocation_s,
    active_labor_s: null,
    paid_labor_s: null,
  };
  const counts = {
    completed_visual: b.counts.completed_visual - a.counts.completed_visual,
    refused: b.counts.refused - a.counts.refused,
    blocked: b.counts.blocked - a.counts.blocked,
    queued: b.counts.queued - a.counts.queued,
    travelling: b.counts.travelling - a.counts.travelling,
    not_released: b.counts.not_released - a.counts.not_released,
  };
  const tie = Object.values(seconds).every(value => value === null || value === 0) &&
    Object.values(counts).every(value => value === 0);
  return freeze({
    basis: 'known_schedule_seconds_and_visual_counts' as const,
    a, b, delta_b_minus_a: {seconds, counts},
    result: tie ? 'tie' as const : 'different' as const,
    winner: null, gain_declared: false as const,
  });
}

export type WarehouseScenarioCostComparison = ReturnType<typeof compareWarehouseScenarioCosts>;
