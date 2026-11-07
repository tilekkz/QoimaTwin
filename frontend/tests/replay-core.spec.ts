import { test, expect } from '@playwright/test';
import layout from '../../contracts/layout.example.json' with { type: 'json' };
import assignment from '../../contracts/assignment.example.json' with { type: 'json' };
import { adaptRunV2, compileVisualRun, conveyorCell, createReplayController, createSfxController, createVisualFixture, CueScheduler } from '../src/replay';
import type { VisualEvent } from '../src/replay';
import {sampleCargoPath} from '../src/replay/core';

test('cargo turns smoothly on transfer decks without changing the timed centreline',()=>{
  const points=[{node_id:'a',pos:[0,.9,0] as [number,number,number],at_s:0},{node_id:'b',pos:[0,.9,1] as [number,number,number],at_s:1},{node_id:'c',pos:[1,.9,1] as [number,number,number],at_s:2}];
  expect(sampleCargoPath(points,1).pos).toEqual([0,.9,1]);
  expect(sampleCargoPath(points,1).yaw).toBeCloseTo(Math.PI/4,8);
  expect(Math.abs(sampleCargoPath(points,1.001).yaw-sampleCargoPath(points,.999).yaw)).toBeLessThan(.02);
  expect(sampleCargoPath(points,.5)).toEqual({pos:[0,.9,.5],yaw:0});
  expect(sampleCargoPath(points,1.5)).toEqual({pos:[.5,.9,1],yaw:Math.PI/2});
});

test('belt hold and completed transport retain the same cargo orientation after seeks',()=>{
  const replay=createReplayController(createVisualFixture());
  const held=replay.seek(42).cargo.T001;
  for(const time of [42.001,45,47.999])expect(replay.seek(time).cargo.T001.yaw).toBe(held.yaw);
  const parcel=replay.getRun().cargo.find(cargo=>cargo.kind==='parcel')!;
  const end=parcel.motions.find(motion=>motion.stage==='outbound_conveyor')!.end_s;
  expect(replay.seek(end).cargo[parcel.cargo_id].yaw).toBeCloseTo(replay.seek(end-1e-5).cargo[parcel.cargo_id].yaw,6);
});

test('all 24 employees persist; drivers represent the two vehicles', () => {
  const replay = createReplayController(createVisualFixture());
  expect(Math.max(...replay.getRun().actions.map(a => a.end_s))).toBeLessThanOrEqual(500);
  expect(replay.getRun().events.find(e => e.kind === 'order_dispatched')!.at_s).toBeLessThan(500);
  for (const time of [0, 44, 82.1, 142, 460, 500, 0]) {
    const frame = replay.seek(time);
    expect(Object.keys(frame.actors)).toHaveLength(24);
    expect(Object.values(frame.actors).filter(a => a.role === 'forklift_driver').map(a => a.vehicleId).sort()).toEqual(['FL01', 'FL02']);
    expect(frame.events).toEqual([]);
  }
});

test('same absolute clock after different frame sizes, speeds and backward seeks', () => {
  const fixture = createVisualFixture(), a = createReplayController(fixture), b = createReplayController(fixture);
  a.play(); for (let i = 0; i < 420; i++) a.advance(.1);
  b.setSpeed(30); b.play(); b.advance(1.4);
  expect(a.getState().time).toBeCloseTo(42, 10);
  expect(b.getFrame().actors.P01.pos).toEqual(a.getFrame().actors.P01.pos);
  const expected = b.seek(462);
  b.seek(500); b.seek(1); b.reset();
  expect(b.seek(462)).toEqual(expected);
  b.pause(); const before = b.getFrame(); expect(b.advance(10)).toEqual(before);
});

test('half-open actions and event boundary applied once', () => {
  const replay = createReplayController(createVisualFixture());
  const first = replay.getRun().actions.find(a => a.actor_id === 'P01')!;
  expect(replay.seek(first.end_s - 1e-7).actors.P01.state).toBe('TRAVEL');
  expect(replay.seek(first.end_s).actors.P01.operation).toBe('pick');
  replay.seek(32.9); replay.play();
  const frame = replay.advance(.1);
  expect(frame.events.filter(e => e.kind === 'tote_inducted')).toHaveLength(1);
  expect(replay.advance(0).events).toEqual([]);
  expect(replay.getFrame().events).toEqual([]);
  expect(replay.seek(33).events).toEqual([]);
});

test('scripted belt hold stops the same cargo then resumes without teleport', () => {
  const replay = createReplayController(createVisualFixture());
  const stopped = replay.seek(42).cargo.T001.pos;
  for (const t of [43, 45, 47.999]) { const frame = replay.seek(t); expect(frame.cargo.T001.pos).toEqual(stopped); expect(frame.line.blocked).toBe(true); }
  expect(replay.seek(48).line.blocked).toBe(false);
  expect(replay.seek(48.5).cargo.T001.pos[0] - stopped[0]).toBeCloseTo(.5, 8);
  expect(replay.seek(58).actors.K01.operation).toBe('pack');
});

test('tote sits on basket base and stays with parked cart heading during pick', () => {
  const fixture = createVisualFixture();
  fixture.actions.find(a => a.actor_id === 'P01' && a.state === 'TRAVEL')!.yaw = Math.PI / 2;
  const replay = createReplayController(fixture), frame = replay.seek(5);
  expect(frame.actors.P01.yaw).toBe(-Math.PI / 2);
  expect(frame.actors.P01.cartYaw).toBe(Math.PI / 2);
  expect(frame.cargo.T001.pos).toEqual([10.62, .553, 16]);
  expect(frame.cargo.T001.attachment.anchor).toBe('cart');
  expect(replay.seek(40).actors.P01.pose.wheelAngle).toBe(replay.seek(60).actors.P01.pose.wheelAngle);
});

test('forklift reverse rolls backwards continuously and survives seek', () => {
  const run = createVisualFixture(), replay = createReplayController(run);
  const reverse = run.actions.find(a => a.actor_id === 'F02' && a.state === 'TRAVEL' && a.yaw === -Math.PI / 2)!;
  const turn = run.actions.find(a => a.actor_id === 'F02' && a.operation === 'turn' && Math.abs(a.start_s - reverse.end_s) < 1e-7)!;
  const forward = run.actions.find(a => a.actor_id === 'F02' && a.state === 'TRAVEL' && Math.abs(a.start_s - turn.end_s) < 1e-7)!;
  const theta = (t: number) => replay.seek(t).actors.F02.pose.wheelAngle;
  const start = theta(reverse.start_s), middle = theta((reverse.start_s + reverse.end_s) / 2), end = theta(reverse.end_s);
  expect(middle - start).toBeCloseTo(-1 / .30, 8);
  expect(end - start).toBeCloseTo(-2 / .30, 8);
  expect(theta(reverse.start_s - 1e-7)).toBeCloseTo(start, 5);
  expect(theta(reverse.end_s + 1e-7)).toBeCloseTo(end, 5);
  expect(theta(turn.end_s)).toBeCloseTo(end, 8);
  expect(theta(forward.end_s) - theta(forward.start_s)).toBeCloseTo(4 / .30, 8);
  replay.seek(500); replay.seek(0);
  expect(theta((reverse.start_s + reverse.end_s) / 2)).toBe(middle);
});

test('parked cart turns continuously at pick/travel boundaries and waypoints', () => {
  const run = createVisualFixture(), replay = createReplayController(run);
  const pick = run.actions.find(a => a.actor_id === 'P01' && a.operation === 'pick')!;
  const travel = run.actions.find(a => a.actor_id === 'P01' && a.state === 'TRAVEL' && Math.abs(a.start_s - pick.end_s) < 1e-7)!;
  const gap = (a: number[], b: number[]) => Math.hypot(...a.map((v, i) => v - b[i]));
  const before = replay.seek(pick.end_s - .01), after = replay.seek(pick.end_s + .01);
  expect(gap(before.cargo.T001.pos, after.cargo.T001.pos)).toBeLessThan(.1);
  expect(after.actors.P01.pos).toEqual([10, 0, 16 - .012]);
  expect(replay.seek((pick.start_s + pick.end_s) / 2).actors.P01.yaw).toBeCloseTo(-Math.PI / 2, 10);
  const corner = travel.waypoints![1].at_s;
  expect(gap(replay.seek(corner - .01).cargo.T001.pos, replay.seek(corner + .01).cargo.T001.pos)).toBeLessThan(.1);
  const expected = replay.seek(corner + .12).actors.P01;
  replay.seek(500); replay.seek(0); expect(replay.seek(corner + .12).actors.P01).toEqual(expected);
  const reverse = run.actions.find(a => a.actor_id === 'F02' && a.state === 'TRAVEL' && a.yaw !== undefined)!;
  expect(replay.seek((reverse.start_s + reverse.end_s) / 2).actors.F02.yaw).toBe(reverse.yaw);
});

test('all graph travel follows existing edges; service connectors stay in their zone', () => {
  for (const event of createVisualFixture().events.filter(e => e.kind === 'sku_picked')) {
    const lot = assignment.initial_lots.find(lot => lot.slot_id === event.payload.slot_id)!;
    expect(event.payload.sku_id).toBe(lot.sku_id);
    expect(event.payload.lot_id).toBe(lot.lot_id);
  }
  for (const action of createVisualFixture().actions.filter(a => a.state === 'TRAVEL')) {
    const points = action.waypoints!;
    if (action.network === 'visual-service-connector') {
      for (const p of points) { expect(p.pos[0]).toBeGreaterThanOrEqual(action.actor_id === 'R01' ? 0 : 64); expect(p.pos[0]).toBeLessThanOrEqual(action.actor_id === 'R01' ? 6 : 72); }
      continue;
    }
    const graph = action.network === 'picker' ? layout.picker_graph : layout.forklift_graphs[action.network as 'inbound' | 'outbound'];
    for (let i = 1; i < points.length; i++) {
      const edge = graph.edges.find(e => e.a === points[i - 1].node_id && e.b === points[i].node_id || e.b === points[i - 1].node_id && e.a === points[i].node_id);
      expect(edge).toBeTruthy();
      expect((points[i].at_s - points[i - 1].at_s) * (action.network === 'picker' ? 1.2 : 2)).toBeCloseTo(edge!.length_m, 8);
    }
  }
});

test('parent parcel follows loaded pallet regardless of track ordering and backward seek', () => {
  const fixture = createVisualFixture(), parcel = fixture.cargo.find(c => c.kind === 'parcel')!;
  parcel.states.at(-1)!.attachment.offset = [.1, .14, .2];
  const replay = createReplayController(fixture);
  const turn = fixture.actions.find(a => a.actor_id === 'F02' && a.operation === 'turn')!;
  const time = (turn.start_s + turn.end_s) / 2;
  const frame = replay.seek(time), parent = frame.cargo.PALLET_OUT_001, child = frame.cargo.PARCEL_VISUAL_001;
  expect(child.visible).toBe(true);
  expect(parent.pos[1]).toBeCloseTo(.1, 8);
  expect(child.pos[0]).toBeCloseTo(parent.pos[0] + .1 * Math.cos(parent.yaw) + .2 * Math.sin(parent.yaw), 8);
  expect(child.pos[1]).toBeCloseTo(parent.pos[1] + .14, 8);
  replay.seek(500); replay.seek(5); expect(replay.seek(time).cargo).toEqual(frame.cargo);
  expect(replay.seek(500).cargo.PARCEL_VISUAL_001.visible).toBe(false);
});

test('pallet stays grounded until fork contact, then lifts continuously; seal timer is 300s', () => {
  const fixture = createVisualFixture(), replay = createReplayController(fixture);
  const load = fixture.actions.find(a => a.actor_id === 'F02' && a.operation === 'loading')!;
  expect(replay.seek(0).cargo.PALLET_OUT_001).toMatchObject({ visible: true, stage: 'empty_pallet', yaw: -Math.PI / 2 });
  expect(replay.seek(load.start_s - 1e-7).cargo.PALLET_OUT_001.yaw).toBeCloseTo(replay.seek(load.start_s).cargo.PALLET_OUT_001.yaw, 8);
  const place = fixture.actions.find(a => a.actor_id === 'S01' && a.operation === 'pallet_place')!;
  const receive = fixture.actions.find(a => a.actor_id === 'R01' && a.operation === 'receiving')!;
  expect(place.pos![0] - .15).toBeGreaterThan(64.92 + .5);
  expect(receive.pos![0] + .15).toBeLessThan(4 - .7);
  expect(replay.seek(load.start_s).cargo.PALLET_OUT_001.pos[1]).toBe(0);
  expect(replay.seek(load.start_s + 12).cargo.PALLET_OUT_001.pos[1]).toBe(0);
  expect(replay.seek(load.end_s - 1e-5).cargo.PALLET_OUT_001.pos[1]).toBeCloseTo(replay.seek(load.end_s).cargo.PALLET_OUT_001.pos[1], 5);
  const placed = fixture.events.find(e => e.kind === 'parcel_scanned')!, sealed = fixture.events.find(e => e.kind === 'pallet_sealed')!;
  expect(sealed.at_s - placed.at_s).toBe(300);
});

test('reduced motion preserves logical state and mechanical lift while removing cosmetic pose', () => {
  const replay = createReplayController(createVisualFixture());
  const frame = replay.seek(5); replay.setReducedMotion(true); const reduced = replay.getFrame();
  expect(reduced.actors.P01.pos).toEqual(frame.actors.P01.pos);
  expect(reduced.actors.P01.pose.jointRotations).toEqual({});
  expect(reduced.actors.P01.pose.rootOffset).toEqual([0, 0, 0]);
});

test('adapter cell boundary mapping is directed and unknown payload locations are reported', () => {
  expect(conveyorCell('LOOP_W:52')).toEqual({ from: [10, .9, 10], to: [9, .9, 10] });
  expect(conveyorCell('LOOP_W:54')).toBeUndefined();
  expect(conveyorCell('LOOP_W:')).toBeUndefined();
  expect(conveyorCell('LOOP_W:0:extra')).toBeUndefined();
  const fixture = createVisualFixture();
  const run = adaptRunV2({ schema_version: '2.0', layout_version: fixture.layout_version, run_id: 'adapter-test', horizon_s: 500, actors: fixture.actors, actions: fixture.actions, events: [{ seq: 1, at_s: 1, phase: 1, kind: 'receipt_accepted', entity_id: 'PAL', payload: { pallet_id: 'PAL' } }], cargo: [{ cargo_id: 'PAL', kind: 'pallet', order_ids: [], contents: [] }], initial_state: { cells: {} }, snapshots: [] });
  expect(run.warnings.some(w => w.includes('No physical location'))).toBe(true);
  expect(createReplayController(run).seek(2).cargo.PAL.visible).toBe(false);
  expect(() => adaptRunV2({ schema_version: '1.0' })).toThrow();
});

test('invalid overlaps, duplicate events and NaN routes are rejected', () => {
  const run = createVisualFixture();
  run.events.push({ ...run.events[0] }); expect(() => compileVisualRun(run)).toThrow('Duplicate'); run.events.pop();
  run.actions.push({ ...run.actions[0] }); expect(() => compileVisualRun(run)).toThrow('Overlapping'); run.actions.pop();
  run.actions[0].waypoints![0].pos[0] = NaN; expect(() => compileVisualRun(run)).toThrow('Non-finite');
});

const cueEvent = (seq: number, kind = 'sku_picked'): VisualEvent => ({ seq, at_s: seq, phase: 0, kind, entity_id: 'source-' + seq, payload: {} });
test('sound limiter deduplicates, caps four voices and summarizes accelerated events', () => {
  const limiter = new CueScheduler();
  const events = Array.from({ length: 8 }, (_, i) => cueEvent(i));
  expect(limiter.plan(events, 0, 1)).toHaveLength(4); expect(limiter.count(0)).toBe(4);
  expect(limiter.plan(events, .1, 1)).toEqual([]);
  limiter.reset(); const summary = limiter.plan([...events, cueEvent(20, 'order_dispatched')], 1, 60);
  expect(summary).toHaveLength(1); expect(summary[0].frequency).toBe(880);
  expect(limiter.plan([cueEvent(21)], 2, 60)).toEqual([]);
  limiter.stop(); expect(limiter.count(2)).toBe(0);
});

test('audio starts muted and never constructs sound during silent QA or seek', () => {
  const sfx = createSfxController(), replay = createReplayController(createVisualFixture());
  replay.seek(8); replay.play(); const frame = replay.advance(5);
  sfx.update(frame, { playing: true, speed: 1 }, 0);
  expect(sfx.getState()).toMatchObject({ muted: true, unlocked: false, voices: 0, cues: 0 });
  sfx.update(replay.seek(33), { playing: true, speed: 1, discontinuity: true }, 1);
  expect(sfx.getState().voices).toBe(0); sfx.dispose();
});

test('mocked audio bus includes motor in four-voice cap and stops on pause/seek', async () => {
  class Parameter { value = 0; setValueAtTime(v: number) { this.value = v; } exponentialRampToValueAtTime(v: number) { this.value = v; } linearRampToValueAtTime(v: number) { this.value = v; } }
  class Source { frequency = new Parameter(); type = 'sine'; buffer: unknown; onended?: () => void; connect() {} disconnect() {} start() {} stop(at?: number) { if (at === undefined) this.onended?.(); } }
  const context = { currentTime: 0, sampleRate: 8000, state: 'running', destination: {}, resume: async () => {}, close: async () => {}, createOscillator: () => new Source(), createBufferSource: () => new Source(), createGain: () => ({ gain: new Parameter(), connect() {}, disconnect() {} }), createBiquadFilter: () => ({ type: 'lowpass', frequency: new Parameter(), Q: new Parameter(), connect() {}, disconnect() {} }), createBuffer: (_channels: number, samples: number) => ({ getChannelData: () => new Float32Array(samples) }) };
  const sfx = createSfxController({ createContext: () => context as unknown as AudioContext });
  expect(await sfx.unlock()).toBe(true); sfx.setMuted(false);
  const replay = createReplayController(createVisualFixture());
  sfx.update(replay.seek(40), { playing: true, speed: 1 }, 0);
  expect(sfx.getState().voices).toBe(1);
  const frame = replay.seek(40.5); frame.events = Array.from({ length: 8 }, (_, i) => cueEvent(i));
  sfx.update(frame, { playing: true, speed: 1 }, .5);
  expect(sfx.getState().voices).toBeLessThanOrEqual(4);
  sfx.update(replay.seek(43), { playing: false, speed: 1 }, 1);
  expect(sfx.getState().voices).toBe(0);
  sfx.update(replay.seek(50), { playing: true, speed: 1 }, 2);
  expect(sfx.getState().voices).toBe(1);
  sfx.update(replay.seek(5), { playing: true, speed: 1, discontinuity: true }, 3);
  expect(sfx.getState().voices).toBe(0); sfx.dispose();
});
