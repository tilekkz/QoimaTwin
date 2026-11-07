import layout from '../../../contracts/layout.example.json' with { type: 'json' };
import actorsFile from '../../../contracts/actors.example.json' with { type: 'json' };
import assignment from '../../../contracts/assignment.example.json' with { type: 'json' };
import type { ActorDefinition, ActorState, CargoKind, CargoState, CargoTrack, Vec3, VisualAction, VisualEvent, VisualRun, Waypoint } from './types';

type Graph = { nodes: { node_id: string; pos: number[] }[]; edges: { a: string; b: string; length_m: number }[] };
const distance = (a: number[], b: number[]) => Math.hypot(...a.map((v, i) => v - b[i]));
const vec = (p: number[]): Vec3 => [p[0], p[1], p[2]];

/** Small scripted visual narrative in the full immutable layout. No DES/KPI. */
export function createVisualFixture(): VisualRun {
  const actions: VisualAction[] = [], events: VisualEvent[] = [], cargo: CargoTrack[] = [];
  let serial = 0;
  const event = (at_s: number, kind: string, entity_id: string, payload: Record<string, unknown>, phase = 0) => events.push({ seq: serial++, at_s, phase, kind, entity_id, payload });
  const service = (actor_id: string, operation: string, start_s: number, end_s: number, pos: Vec3, entity_id: string | null, state: ActorState = 'BUSY_SERVICE', yaw?: number, endYaw?: number) => {
    actions.push({ action_id: 'visual-' + serial++, actor_id, operation, state, start_s, end_s, pos, entity_id, yaw, endYaw }); return end_s;
  };
  const travel = (actor_id: string, start: number, ids: string[], graph: Graph, speed: number, network: string, entity: string | null = null, yaw?: number) => {
    const nodes = new Map(graph.nodes.map(n => [n.node_id, vec(n.pos)]));
    let time = start;
    const waypoints = ids.map((id, index) => {
      if (!nodes.has(id)) throw new Error('Unknown fixture node ' + id);
      if (index) { const previous = ids[index - 1]; const edge = graph.edges.find(e => e.a === previous && e.b === id || e.b === previous && e.a === id); if (!edge) throw new Error('Illegal fixture edge ' + previous + ' → ' + id); time += edge.length_m / speed; }
      return { node_id: id, pos: nodes.get(id)!, at_s: time };
    });
    actions.push({ action_id: 'visual-' + serial++, actor_id, state: 'TRAVEL', operation: actor_id.startsWith('F') ? 'drive' : 'walk', start_s: start, end_s: time, entity_id: entity, waypoints, network, yaw });
    return time;
  };
  // These connectors are visual-only service corridors, not new shared edges.
  // Both are wholly inside the receiving/shipping zones, used before vehicles.
  const connector = (actor: string, start: number, points: Vec3[], entity: string | null = null) => {
    let time = start;
    const waypoints = points.map((pos, i) => { if (i) time += distance(points[i - 1], pos) / 1.2; return { node_id: 'VISUAL_SERVICE_' + actor + '_' + i, pos, at_s: time }; });
    actions.push({ action_id: 'visual-' + serial++, actor_id: actor, state: 'TRAVEL', operation: 'walk', start_s: start, end_s: time, entity_id: entity, waypoints, network: 'visual-service-connector' });
    return time;
  };
  const state = (at_s: number, pos: Vec3, stage: string, visible = true, attachment: CargoState['attachment'] = { kind: 'world' }, yaw = 0): CargoState => ({ at_s, pos, stage, visible, attachment, yaw });
  const track = (id: string, kind: CargoKind, states: CargoState[], orderIds: string[] = []): CargoTrack => { const result = { cargo_id: id, kind, states, motions: [], order_ids: orderIds }; cargo.push(result); return result; };
  const motion = (target: CargoTrack, points: Vec3[], start: number, speed: number, stage: string, block?: [number, number]) => {
    let time = start;
    const waypoints: Waypoint[] = [{ node_id: 'visual-service', pos: points[0], at_s: start }];
    for (let i = 1; i < points.length; i++) {
      const length = distance(points[i - 1], points[i]);
      const steps = Math.max(1, Math.round(length));
      for (let cell = 1; cell <= steps; cell++) {
        const pos = points[i - 1].map((v, j) => v + (points[i][j] - v) * cell / steps) as Vec3;
        time += length / steps / speed;
        waypoints.push({ node_id: 'visual-cell-' + waypoints.length, pos, at_s: time });
        if (block && Math.abs(time - block[0]) < 1e-6) { time = block[1]; waypoints.push({ node_id: 'visual-blocked-hold', pos: [...pos], at_s: time }); }
      }
    }
    target.motions.push({ start_s: start, end_s: time, waypoints, stage });
    const tail=points.at(-1)!,previous=points.at(-2)!;
    target.states.push(state(time,tail,stage,true,{kind:'world'},Math.atan2(tail[0]-previous[0],tail[2]-previous[2])));
    return time;
  };
  const order = 'VISUAL_ORDER_001', toteId = 'T001', parcelId = 'PARCEL_VISUAL_001', palletId = 'PALLET_OUT_001';
  const pickedPayload = (slotId: string) => {
    const lot = assignment.initial_lots.find(lot => lot.slot_id === slotId);
    if (!lot) throw new Error('Visual fixture pick has no canonical lot ' + slotId);
    return { order_id: order, actor_id: 'P01', slot_id: slotId, sku_id: lot.sku_id, lot_id: lot.lot_id, quantity: 1 };
  };
  event(0, 'order_arrived', order, { order_id: order }, 1);
  event(0, 'order_assigned', order, { order_id: order, actor_id: 'P01', tote_id: toteId }, 3);
  let time = travel('P01', 0, ['I01', 'N_A01_Z14', 'N_A01_Z16'], layout.picker_graph, 1.2, 'picker');
  time = service('P01', 'pick', time, time + 6.15, [10, 0, 16], order, 'BUSY_SERVICE', -Math.PI / 2);
  event(time, 'sku_picked', order, pickedPayload('S_A01_B01_L_01'));
  time = travel('P01', time, ['N_A01_Z16', 'N_A01_Z14', 'N_A02_Z14', 'N_A02_Z16'], layout.picker_graph, 1.2, 'picker');
  time = service('P01', 'pick', time, time + 6.15, [14.5, 0, 16], order, 'BUSY_SERVICE', -Math.PI / 2);
  event(time, 'sku_picked', order, pickedPayload('S_A02_B01_L_01'));
  time = travel('P01', time, ['N_A02_Z16', 'N_A02_Z14', 'N_A01_Z14', 'I01'], layout.picker_graph, 1.2, 'picker');
  const handoffStart = time;
  time = service('P01', 'handoff', time, time + 3, [10, 0, 12], toteId, 'BUSY_SERVICE', Math.PI);
  event(time, 'handoff_ready', toteId, { order_id: order, tote_id: toteId, actor_id: 'P01', induction_id: 'I01' });
  service('P01', 'tote_wait', time, 33, [10, 0, 12], toteId, 'WAIT_RESOURCE', Math.PI);
  service('P01', 'handoff_return', 33, 33.8, [10, 0, 12], null, 'IDLE', Math.PI);
  const tote = track(toteId, 'tote', [state(0, [10, .553, 12.62], 'picking', true, { kind: 'actor', id: 'P01', offset: [0, .553, .62], anchor: 'cart' }), state(handoffStart, [10, .553, 11.38], 'handoff')], [order]);
  // First .3s is the grasp; lift/slide then follows the hands for 2.7s.
  motion(tote, [[10, .553, 11.38], [10, .9, 11]], handoffStart + .3, distance([10, .553, 11.38], [10, .9, 11]) / 2.7, 'handoff');
  tote.states.push(state(33, [10, .9, 11], 'conveyor'));
  event(33, 'tote_inducted', toteId, { order_id: order, tote_id: toteId, actor_id: 'P01', induction_id: 'I01', target_pack_id: 'PK01', cell_id: 'FEED01:0' }, 2);
  const packAt = motion(tote, [[10, .9, 11], [10, .9, 10], [8, .9, 10], [8, .9, 8], [20, .9, 8], [20, .9, 6]], 33, 1, 'conveyor', [42, 48]);
  event(42, 'visual_line_blocked', 'LOOP_E', { reason: 'Scripted visual hold, not a simulated queue' });
  event(48, 'visual_line_resumed', 'LOOP_E', {});
  event(packAt, 'pack_started', toteId, { order_id: order, actor_id: 'K01', pack_id: 'PK01', tote_id: toteId }, 3);
  service('K01', 'pack', packAt, packAt + 24.1, [20, 0, 4.5], order, 'BUSY_SERVICE', Math.PI);
  motion(tote, [[20, .9, 6], [20, .9, 5.75], [19.28, .9, 5.75], [19.28, .85, 5], [19.28, .85, 4.73]], packAt, .8, 'pack_wip');
  const packedAt = packAt + 24.1;
  tote.states.push(state(packedAt, [19.28, .85, 4.73], 'virtual_empty_return', false));
  event(packedAt, 'order_packed', parcelId, { order_id: order, actor_id: 'K01', pack_id: 'PK01', tote_id: toteId, parcel_id: parcelId });
  const parcel = track(parcelId, 'parcel', [state(0, [20, .9, 3], 'not_created', false), state(packedAt, [20.72, .85, 4.79], 'packed')], [order]);
  const outfedAt = Math.ceil(packedAt + 3);
  const outPath: Vec3[] = [[20.72, .85, 4.79], [20.72, .85, 4], [20.72, .9, 3.3], [20, .9, 3.3], [20, .9, 3]];
  const outDistance = outPath.slice(1).reduce((sum, p, i) => sum + distance(outPath[i], p), 0);
  motion(parcel, outPath, packedAt, outDistance / (outfedAt - packedAt), 'outfeed_handoff');
  event(outfedAt, 'parcel_outfed', parcelId, { order_id: order, parcel_id: parcelId, actor_id: 'K01', pack_id: 'PK01' }, 2);
  const shippingAt = motion(parcel, [[20, .9, 3], [20, .9, 2], [66, .9, 2]], outfedAt, 1, 'outbound_conveyor');
  parcel.states.push(state(shippingAt, [66, .9, 2], 'shipping_buffer',true,{kind:'world'},Math.PI/2));
  event(shippingAt, 'shipping_arrived', parcelId, { order_id: order, parcel_id: parcelId });
  const serviceStart: Vec3 = [65.5, 0, 4], terminal: Vec3 = [66, 0, 2.3], pickPoint: Vec3 = [66, 0, 6], placeService: Vec3 = [65.65, 0, 6];
  connector('S01', shippingAt - distance(serviceStart, terminal) / 1.2, [serviceStart, terminal]);
  service('S01', 'scan', shippingAt, shippingAt + 8, terminal, parcelId, 'BUSY_SERVICE', Math.PI);
  parcel.states.push(state(shippingAt + 8, [66, .9, 2], 'carried_to_pallet', true, { kind: 'actor', id: 'S01', offset: [0, .9, .3] }));
  let carriedAt = service('S01', 'turn', shippingAt + 8, shippingAt + 8.6, terminal, parcelId, 'BUSY_SERVICE', Math.PI, 0);
  carriedAt = connector('S01', carriedAt, [terminal, pickPoint], parcelId);
  carriedAt = service('S01', 'turn', carriedAt, carriedAt + .6, pickPoint, parcelId, 'BUSY_SERVICE', 0, -Math.PI / 2);
  carriedAt = connector('S01', carriedAt, [pickPoint, placeService], parcelId);
  const placedAt = service('S01', 'pallet_place', carriedAt, carriedAt + 2, placeService, parcelId, 'BUSY_SERVICE', -Math.PI / 2);
  motion(parcel, [[65.35, .9, 6], [64.92, .14, 6]], carriedAt, distance([65.35, .9, 6], [64.92, .14, 6]) / 2, 'pallet_placement');
  parcel.states.push(state(placedAt, [64.92, .14, 6], 'palletized', true, { kind: 'cargo', id: palletId, offset: [0, .14, 0] }));
  event(placedAt, 'parcel_scanned', parcelId, { order_id: order, parcel_id: parcelId, pallet_id: palletId, actor_id: 'S01' });
  service('S01', 'placement_return', placedAt, placedAt + .6, placeService, null, 'IDLE', -Math.PI / 2);
  connector('S01', placedAt + .6, [placeService, [66, 0, 6], [66, 0, 4], serviceStart]);
  const sealedAt = placedAt + 300;
  const pallet = track(palletId, 'pallet', [state(0, [64.92, 0, 6], 'empty_pallet', true, { kind: 'world' }, -Math.PI / 2), state(placedAt, [64.92, 0, 6], 'open_pallet', true, { kind: 'world' }, -Math.PI / 2)], [order]);
  pallet.states.push(state(sealedAt, [64.92, 0, 6], 'sealed_pallet', true, { kind: 'world' }, -Math.PI / 2));
  event(sealedAt, 'pallet_sealed', palletId, { order_id: order, pallet_id: palletId, parcel_ids: [parcelId], actor_id: 'S01' }, 3);
  const outbound = layout.forklift_graphs.outbound;
  let f2 = travel('F02', sealedAt, ['FO_HOME', 'FO_VIA', 'FO_PICK'], outbound, 2, 'outbound');
  pallet.states.push(state(f2, [64.92, 0, 6], 'forklift_loading', true, { kind: 'vehicle', id: 'FL02', offset: [0, .10, 1.08] }));
  f2 = service('F02', 'loading', f2, f2 + 15, [66, 0, 6], palletId, 'BUSY_SERVICE', -Math.PI / 2);
  pallet.states.push(state(f2, [64.92, .10, 6], 'forklift_loaded', true, { kind: 'vehicle', id: 'FL02', offset: [0, .10, 1.08] }));
  f2 = travel('F02', f2, ['FO_PICK', 'FO_VIA'], outbound, 2, 'outbound', palletId, -Math.PI / 2); // Reverse out with forks still facing the pickup.
  f2 = service('F02', 'turn', f2, f2 + .8, [68, 0, 6], palletId, 'BUSY_SERVICE', -Math.PI / 2, Math.PI);
  f2 = travel('F02', f2, ['FO_VIA', 'FO_TURN'], outbound, 2, 'outbound', palletId);
  f2 = service('F02', 'turn', f2, f2 + .8, [68, 0, 2], palletId, 'BUSY_SERVICE', Math.PI, Math.PI / 2);
  f2 = travel('F02', f2, ['FO_TURN', 'FO_DROP'], outbound, 2, 'outbound', palletId);
  f2 = service('F02', 'unloading', f2, f2 + 15, [70, 0, 2], palletId, 'BUSY_SERVICE', Math.PI / 2);
  pallet.states.push(state(f2, [71.08, 0, 2], 'dispatched', false));
  event(f2, 'order_dispatched', palletId, { order_id: order, pallet_id: palletId, parcel_ids: [parcelId], actor_id: 'F02', dock_id: 'DOCK_OUT' });
  travel('F02', f2, ['FO_DROP', 'FO_TURN', 'FO_VIA', 'FO_HOME'], outbound, 2, 'outbound');
  // Independent receiving narrative, wholly within its own peripheral lane.
  const incoming = track('PALLET_IN_001', 'pallet', [state(0, [4, 0, 36.92], 'not_arrived', false, { kind: 'world' }, Math.PI), state(8, [4, 0, 36.92], 'receiving', true, { kind: 'world' }, Math.PI)]);
  event(8, 'receipt_accepted', incoming.cargo_id, { receipt_id: 'VISUAL_RECEIPT_001', pallet_id: incoming.cargo_id, sku_id: 'DEMO_003', quantity: 500 }, 1);
  let r1 = connector('R01', 8, [[3, 0, 38], [3, 0, 36.92]]);
  r1 = service('R01', 'receiving', r1, r1 + 90, [3, 0, 36.92], incoming.cargo_id, 'BUSY_SERVICE', Math.PI / 2);
  event(r1, 'receipt_processed', incoming.cargo_id, { receipt_id: 'VISUAL_RECEIPT_001', pallet_id: incoming.cargo_id, actor_id: 'R01' });
  connector('R01', r1, [[3, 0, 36.92], [3, 0, 38]]);
  let f1 = travel('F01', r1, ['FI_HOME', 'FI_PICK'], layout.forklift_graphs.inbound, 2, 'inbound');
  incoming.states.push(state(f1, [4, 0, 36.92], 'forklift_loading', true, { kind: 'vehicle', id: 'FL01', offset: [0, .10, 1.08] }));
  f1 = service('F01', 'loading', f1, f1 + 15, [4, 0, 38], incoming.cargo_id, 'BUSY_SERVICE', Math.PI);
  incoming.states.push(state(f1, [4, .10, 36.92], 'forklift_loaded', true, { kind: 'vehicle', id: 'FL01', offset: [0, .10, 1.08] }));
  f1 = travel('F01', f1, ['FI_PICK', 'FI_DROP'], layout.forklift_graphs.inbound, 2, 'inbound', incoming.cargo_id);
  f1 = service('F01', 'unloading', f1, f1 + 15, [4, 0, 16], incoming.cargo_id, 'BUSY_SERVICE', Math.PI);
  incoming.states.push(state(f1, [4, 0, 14.92], 'reserve_staging', true, { kind: 'world' }, Math.PI));
  event(f1, 'pallet_putaway', incoming.cargo_id, { pallet_id: incoming.cargo_id, actor_id: 'F01', receipt_id: 'VISUAL_RECEIPT_001', sku_id: 'DEMO_003', quantity: 500 });
  travel('F01', f1, ['FI_DROP', 'FI_PICK', 'FI_HOME'], layout.forklift_graphs.inbound, 2, 'inbound');
  for (const c of cargo) { c.states.sort((a, b) => a.at_s - b.at_s); c.motions.sort((a, b) => a.start_s - b.start_s); }
  return { run_id: 'visual-fixture-v2-001', layout_version: layout.layout_version, source: 'visual-fixture', label: 'VISUAL DEMO · синтетическая визуальная фикстура · не расчёт KPI', duration_s: 500, actors: actorsFile.actors.map(a => ({ ...a, initial_pos: vec(a.initial_pos) })) as ActorDefinition[], actions, events, cargo, blocked: [{ start_s: 42, end_s: 48, segment_ids: ['LOOP_E'] }], warnings: [], fitting: { forkContactLift: .071, carryLift: .171 }, notes: ['All 24 contract actors persist. Two drivers are attached to FL01/FL02; not additional pedestrians.', 'Scripted visual narrative only: no inventory ledger, optimizer, queue model or operational KPI.', 'Walking 1.2m/s; forklift 2m/s; belt 1m/s. Picker/forklift routes use existing graph edges. Six-second belt hold is scripted, not calculated.', 'Receiving/shipping manual connectors are explicit visual-only service corridors inside their zones, not shared graph mutations.', 'Outbound pallet seals 300s after first placement. Loaded vehicle backs out and turns in place at graph nodes; cosmetic turns add 1.6s.', 'Tote instant virtual return at packing is the stated P0 assumption. Parcel remains visible on pallet deck Y=.14.', 'Visual fork fitting: deck underside .116, rest fork top .045, contact lift .071, carry lift .171 gives pallet base Y=.10. Pick rootOffset is a .55m cosmetic reach and never changes graph coordinates.', 'One order follows the analytical fixture path with an explicit six-second hold plus manual service connectors. Times are visual fixture times, not engine benchmark results.'] };
}
