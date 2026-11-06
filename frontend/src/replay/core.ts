import { proceduralPose } from './motion';
import type { ActorDefinition, CargoState, Vec3, VisualAction, VisualActor, VisualEvent, VisualFrame, VisualRun, Waypoint } from './types';

export function upperBound<T>(items: readonly T[], value: number, key: (item: T) => number): number {
  let low = 0, high = items.length;
  while (low < high) { const mid = (low + high) >>> 1; if (key(items[mid]) <= value) low = mid + 1; else high = mid; }
  return low;
}
const copy = (p: readonly number[]): Vec3 => [p[0], p[1], p[2]];
const lerp = (a: Vec3, b: Vec3, t: number): Vec3 => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const easeYaw = (from: number, to: number, progress: number) => { const t = Math.max(0, Math.min(1, progress)); return from + Math.atan2(Math.sin(to - from), Math.cos(to - from)) * t * t * (3 - 2 * t); };
export const eventOrder = (a: VisualEvent, b: VisualEvent) => a.at_s - b.at_s || a.phase - b.phase || a.seq - b.seq;
export function samplePath(points: Waypoint[], time: number): { pos: Vec3; yaw: number } {
  if (!points.length) throw new Error('Empty visual path');
  let index = Math.min(points.length - 2, Math.max(0, upperBound(points, time, p => p.at_s) - 1));
  if (points.length === 1) return { pos: copy(points[0].pos), yaw: 0 };
  // Repeated points encode a stationary interval (for example a blocked belt).
  const a = points[index], b = points[index + 1];
  const t = Math.min(1, Math.max(0, (time - a.at_s) / (b.at_s - a.at_s || 1)));
  let dx = b.pos[0] - a.pos[0], dz = b.pos[2] - a.pos[2];
  if (Math.hypot(dx, dz) < 1e-9) {
    while (index > 0 && Math.hypot(dx, dz) < 1e-9) { index--; dx = points[index + 1].pos[0] - points[index].pos[0]; dz = points[index + 1].pos[2] - points[index].pos[2]; }
  }
  return { pos: lerp(a.pos, b.pos, t), yaw: Math.atan2(dx, dz) };
}
const labels: Record<string, string> = { pick: 'Отбор', pack: 'Упаковка', scan: 'Сканирование', handoff: 'Сдача tote', receiving: 'Приёмка', loading: 'Погрузка', unloading: 'Разгрузка', putaway: 'Резервная площадка', walk: 'Переход', drive: 'Перевозка', tote_wait: 'Ожидание линии', idle: 'Ожидание', blocked: 'Линия заблокирована' };
const pulseKinds = new Set(['sku_picked', 'tote_inducted', 'pack_started', 'order_packed', 'parcel_scanned', 'pallet_sealed', 'order_dispatched', 'receipt_accepted', 'pallet_putaway']);

export function compileVisualRun(input: VisualRun) {
  if (!Number.isFinite(input.duration_s) || input.duration_s < 0) throw new Error('Invalid duration');
  const actors = input.actors.map(a => ({ ...a, initial_pos: copy(a.initial_pos) }));
  if (actors.length !== 24 || new Set(actors.map(a => a.actor_id)).size !== 24) throw new Error('Replay requires 24 unique actors');
  const ids = new Set(actors.map(a => a.actor_id));
  const byActor = new Map<string, VisualAction[]>();
  const parkedCartYaws = new Map<string, number[]>();
  const distanceBefore = new Map<string, number[]>();
  const pathDistances = new Map<VisualAction, number[]>();
  const travelYawPlans = new Map<VisualAction, { at_s: number; blend_s: number; from: number; to: number }[]>();
  for (const a of input.actions) {
    if (!ids.has(a.actor_id) || !Number.isFinite(a.start_s) || !Number.isFinite(a.end_s) || a.start_s < 0 || a.end_s <= a.start_s) throw new Error('Invalid actor action ' + a.action_id);
    if (a.state === 'TRAVEL' ? !a.waypoints?.length || !!a.pos : !a.pos || !!a.waypoints) throw new Error('Action geometry mismatch ' + a.action_id);
    if (a.waypoints) {
      if (a.waypoints.some(p => !Number.isFinite(p.at_s) || p.pos.length !== 3 || p.pos.some(v => !Number.isFinite(v)))) throw new Error('Non-finite waypoint');
      if (Math.abs(a.waypoints[0].at_s - a.start_s) > 1e-7 || Math.abs(a.waypoints.at(-1)!.at_s - a.end_s) > 1e-7) throw new Error('Path time boundaries ' + a.action_id);
      for (let i = 1; i < a.waypoints.length; i++) if (a.waypoints[i].at_s <= a.waypoints[i - 1].at_s) throw new Error('Non-monotonic waypoints');
    }
    if (a.pos?.some(v => !Number.isFinite(v))) throw new Error('Non-finite service position');
    const list = byActor.get(a.actor_id) || []; list.push(a); byActor.set(a.actor_id, list);
  }
  for (const list of byActor.values()) { list.sort((a, b) => a.start_s - b.start_s); for (let i = 1; i < list.length; i++) if (list[i].start_s < list[i - 1].end_s - 1e-8) throw new Error('Overlapping actor actions'); }
  for (const [id, list] of byActor) {
    const actor = actors.find(actor => actor.actor_id === id);
    const isForklift = actor?.role === 'forklift_driver';
    let heading = actor?.role === 'packer' ? Math.PI : 0, parkedHeading = heading, distance = 0;
    const headings: number[] = [], distances: number[] = [];
    for (const action of list) {
      distances.push(distance);
      if (action.waypoints) {
        const cumulative = [0];
        const turns: { at_s: number; blend_s: number; from: number; to: number }[] = [];
        for (let i = 1; i < action.waypoints.length; i++) {
          const a = action.waypoints[i - 1].pos, b = action.waypoints[i].pos;
          const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
          const projection = action.yaw === undefined ? 1 : dx * Math.sin(action.yaw) + dz * Math.cos(action.yaw);
          const direction = isForklift && action.yaw !== undefined
            ? Math.abs(projection) < 1e-9 ? 0 : Math.sign(projection)
            : 1;
          cumulative.push(cumulative[i - 1] + Math.hypot(dx, dy, dz) * direction);
          const to = action.yaw ?? (Math.hypot(dx, dz) > 1e-9 ? Math.atan2(dx, dz) : heading);
          const duration = action.waypoints[i].at_s - action.waypoints[i - 1].at_s;
          turns.push({ at_s: action.waypoints[i - 1].at_s, blend_s: action.yaw === undefined ? Math.min(i === 1 ? .4 : .25, duration) : 0, from: heading, to });
          heading = to;
        }
        travelYawPlans.set(action, turns);
        pathDistances.set(action, cumulative); distance += cumulative.at(-1)!;
        heading = action.endYaw ?? heading;
        parkedHeading = heading;
      } else if (action.endYaw !== undefined) heading = action.endYaw;
      else if (action.operation === 'pick') heading = parkedHeading;
      else if (action.yaw !== undefined) heading = action.yaw;
      headings.push(parkedHeading);
    }
    parkedCartYaws.set(id, headings); distanceBefore.set(id, distances);
  }
  const events = [...input.events].sort(eventOrder);
  if (events.some(e => !Number.isFinite(e.at_s) || e.at_s < 0 || !Number.isInteger(e.seq) || !Number.isInteger(e.phase))) throw new Error('Invalid event time/sequence');
  if (new Set(events.map(e => e.seq)).size !== events.length) throw new Error('Duplicate event seq');
  const run = { ...input, actors, events };
  const orderTimelines = new Map<string, { at_s: number; stage: string }[]>();
  for (const event of events) {
    const orderId = event.payload.order_id;
    if (typeof orderId !== 'string' || ['cell_entered', 'cell_exited', 'actor_state_changed', 'stock_reserved'].includes(event.kind)) continue;
    const timeline = orderTimelines.get(orderId) || []; timeline.push({ at_s: event.at_s, stage: event.kind }); orderTimelines.set(orderId, timeline);
  }
  function actorFrame(actor: ActorDefinition, time: number, reducedMotion: boolean): VisualActor {
    const list = byActor.get(actor.actor_id) || [];
    const actionIndex = upperBound(list, time, a => a.start_s) - 1;
    const previous = list[actionIndex];
    const active = previous && time < previous.end_s ? previous : undefined;
    let pos = copy(actor.initial_pos), yaw = actor.role === 'packer' ? Math.PI : 0;
    if (previous) {
      const path = previous.waypoints;
      if (path) {
        ({ pos, yaw } = samplePath(path, Math.min(time, previous.end_s)));
        const turns = travelYawPlans.get(previous)!;
        const turn = turns[Math.max(0, upperBound(turns, Math.min(time, previous.end_s), turn => turn.at_s) - 1)];
        yaw = turn.blend_s ? easeYaw(turn.from, turn.to, (time - turn.at_s) / turn.blend_s) : turn.to;
      }
      else { pos = copy(previous.pos!); yaw = previous.yaw ?? yaw; }
    }
    const phase = active ? (time - active.start_s) / (active.end_s - active.start_s) : 0;
    if (previous?.endYaw !== undefined) {
      const start = previous.yaw ?? yaw;
      const delta = Math.atan2(Math.sin(previous.endYaw - start), Math.cos(previous.endYaw - start));
      yaw = start + delta * (active ? phase : 1);
    } else if (previous?.operation === 'pick') {
      const parked = parkedCartYaws.get(actor.actor_id)?.[actionIndex] ?? yaw;
      const fade = Math.min(.3, (previous.end_s - previous.start_s) / 2);
      const weight = active ? Math.min(1, (time - previous.start_s) / fade, (previous.end_s - time) / fade) : 0;
      yaw = easeYaw(parked, previous.yaw ?? parked, weight);
    } else if (!previous?.waypoints) yaw = active?.yaw ?? yaw;
    const base = { id: actor.actor_id, role: actor.role, vehicleId: actor.vehicle_id, pos, yaw, cartYaw: active?.state === 'TRAVEL' ? yaw : parkedCartYaws.get(actor.actor_id)?.[actionIndex] ?? yaw, state: active?.state ?? 'IDLE' as const, operation: active?.operation ?? 'idle', phase, actionId: active?.action_id, entityId: active?.entity_id ?? undefined };
    const pose = proceduralPose(base, time, reducedMotion);
    let travelled = distanceBefore.get(actor.actor_id)?.[actionIndex] ?? 0;
    if (previous?.waypoints) {
      const points = previous.waypoints, cumulative = pathDistances.get(previous)!;
      const index = Math.max(0, Math.min(points.length - 2, upperBound(points, Math.min(time, previous.end_s), p => p.at_s) - 1));
      const fraction = Math.min(1, Math.max(0, (time - points[index].at_s) / (points[index + 1].at_s - points[index].at_s)));
      travelled += cumulative[index] + (cumulative[index + 1] - cumulative[index]) * fraction;
    }
    pose.wheelAngle = travelled / (actor.role === 'forklift_driver' ? .30 : .068);
    return { ...base, pose };
  }
  return {
    run,
    sample(time: number, crossed: VisualEvent[] = [], reducedMotion = false): VisualFrame {
      const t = Math.max(0, Math.min(run.duration_s, time));
      const actorFrames = Object.fromEntries(actors.map(a => [a.actor_id, actorFrame(a, t, reducedMotion)]));
      const cargo: VisualFrame['cargo'] = {};
      for (const track of run.cargo) {
        const state: CargoState | undefined = track.states[upperBound(track.states, t, s => s.at_s) - 1];
        if (!state) continue;
        let pos = copy(state.pos), yaw = state.yaw, stage = state.stage;
        const attachment = { ...state.attachment };
        const motion = track.motions[upperBound(track.motions, t, m => m.start_s) - 1];
        if (motion && t >= motion.start_s && t < motion.end_s) { ({ pos, yaw } = samplePath(motion.waypoints, t)); stage = motion.stage; }
        else if ((attachment.kind === 'actor' || attachment.kind === 'vehicle') && attachment.id) {
          const owner = actorFrames[attachment.id] || Object.values(actorFrames).find(a => a.vehicleId === attachment.id);
          if (owner) { const p = attachment.offset ?? [0, 0, 0]; const anchorYaw = attachment.anchor === 'cart' ? owner.cartYaw : owner.yaw; const s = Math.sin(anchorYaw), c = Math.cos(anchorYaw); const height = track.kind === 'pallet' && attachment.kind === 'vehicle' && run.fitting ? Math.max(0, owner.pose.lift - run.fitting.forkContactLift) : p[1]; pos = [owner.pos[0] + p[0] * c + p[2] * s, owner.pos[1] + height, owner.pos[2] - p[0] * s + p[2] * c]; yaw = anchorYaw; }
        }
        cargo[track.cargo_id] = { id: track.cargo_id, kind: track.kind, orderIds: [...track.order_ids], pos, yaw, visible: state.visible, stage, attachment };
      }
      // Resolve parents after all tracks, independent of definition ordering.
      const resolved = new Set<string>();
      const resolveCargo = (id: string, visiting = new Set<string>()) => {
        if (resolved.has(id)) return;
        const item = cargo[id]; if (!item) return;
        if (visiting.has(id)) { item.visible = false; return; }
        visiting.add(id);
        if (item.attachment.kind === 'cargo' && item.attachment.id) {
          const parentId = item.attachment.id; resolveCargo(parentId, visiting);
          const owner = cargo[parentId], p = item.attachment.offset ?? [0, 0, 0];
          if (owner) { const s = Math.sin(owner.yaw), c = Math.cos(owner.yaw); item.pos = [owner.pos[0] + p[0] * c + p[2] * s, owner.pos[1] + p[1], owner.pos[2] - p[0] * s + p[2] * c]; item.yaw = owner.yaw; item.visible = item.visible && owner.visible; } else item.visible = false;
        }
        visiting.delete(id); resolved.add(id);
      };
      for (const id of Object.keys(cargo)) resolveCargo(id);
      const end = upperBound(events, t, e => e.at_s), start = upperBound(events, t - 1.2, e => e.at_s);
      const pulses = events.slice(start, end).filter(e => pulseKinds.has(e.kind)).map(e => ({ id: run.run_id + ':' + e.seq, kind: e.kind, entityId: e.entity_id, age: t - e.at_s, opacity: Math.max(0, 1 - (t - e.at_s) / 1.2) * .65, at_s: e.at_s }));
      const orderStages: Record<string, string> = {};
      for (const [orderId, timeline] of orderTimelines) { const state = timeline[upperBound(timeline, t, s => s.at_s) - 1]; if (state) orderStages[orderId] = state.stage; }
      const blocked = run.blocked.filter(b => b.start_s <= t && t < b.end_s);
      return { time: t, duration: run.duration_s, source: run.source, label: run.label, actors: actorFrames, cargo, events: crossed, pulses, labels: Object.values(actorFrames).filter(a => a.state !== 'IDLE').map(a => ({ actorId: a.id, text: labels[a.operation] ?? a.operation, operation: a.operation })), line: { blocked: blocked.length > 0, blockedSegmentIds: [...new Set(blocked.flatMap(b => b.segment_ids))] }, orderStages, warnings: run.warnings };
    },
  };
}

export function createReplayController(initial: VisualRun) {
  let compiled = compileVisualRun(initial), time = 0, playing = false, speed = 1, reducedMotion = false;
  const frame = (events: VisualEvent[] = []) => compiled.sample(time, events, reducedMotion);
  return {
    play() { if (time < compiled.run.duration_s) playing = true; },
    pause() { playing = false; },
    setSpeed(value: number) { if (!Number.isFinite(value) || value <= 0 || value > 60) throw new Error('Speed must be >0 and <=60'); speed = value; },
    setReducedMotion(value: boolean) { reducedMotion = value; },
    seek(value: number) { if (!Number.isFinite(value)) throw new Error('Invalid seek'); time = Math.max(0, Math.min(compiled.run.duration_s, value)); return frame(); },
    reset() { time = 0; playing = false; return frame(); },
    setRun(run: VisualRun) { compiled = compileVisualRun(run); time = 0; playing = false; return frame(); },
    advance(realDeltaSeconds: number) {
      if (!Number.isFinite(realDeltaSeconds) || realDeltaSeconds < 0) throw new Error('Invalid clock delta');
      if (!playing || !realDeltaSeconds) return frame();
      const previous = time; time = Math.min(compiled.run.duration_s, time + realDeltaSeconds * speed);
      const events = compiled.run.events;
      const crossed = events.slice(upperBound(events, previous, e => e.at_s), upperBound(events, time, e => e.at_s));
      if (time === compiled.run.duration_s) playing = false;
      return frame(crossed);
    },
    getFrame: () => frame(),
    getRun: () => compiled.run,
    getState: () => ({ time, duration: compiled.run.duration_s, playing, speed, source: compiled.run.source, runId: compiled.run.run_id }),
  };
}
