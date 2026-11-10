import layout from '../../../contracts/layout.example.json' with { type: 'json' };
import { eventOrder, compileVisualRun } from './core';
import type { ActorDefinition, CargoKind, CargoState, CargoTrack, Vec3, VisualAction, VisualEvent, VisualRun } from './types';

type ObjectValue = Record<string, unknown>;
const object = (value: unknown): ObjectValue => { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected Run v2 object'); return value as ObjectValue; };
const text = (value: unknown) => typeof value === 'string' ? value : undefined;
const position = (value: unknown): Vec3 | undefined => Array.isArray(value) && value.length === 3 && value.every(v => typeof v === 'number' && Number.isFinite(v)) ? [...value] as Vec3 : undefined;
export function conveyorCell(cellId: string): { from: Vec3; to: Vec3 } | undefined {
  const match = /^([^:]+):(\d+)$/.exec(cellId); if (!match) return undefined;
  const [, id, indexText] = match, index = Number(indexText);
  const segment = layout.conveyor.segments.find(s => s.segment_id === id);
  if (!segment || !Number.isInteger(index) || index < 0 || index >= segment.cell_count) return undefined;
  const point = (offset: number) => segment.from.map((v, axis) => v + (segment.to[axis] - v) * offset / segment.cell_count) as Vec3;
  return { from: point(index), to: point(index + 1) };
}

/** Render adapter, not a second inventory/queue engine. Unknown locations stay
 * hidden and generate warnings; metrics remain owned by the supplied Run. */
export function adaptRunV2(value: unknown): VisualRun {
  const raw = object(value);
  if (raw.schema_version !== '2.0' || raw.layout_version !== layout.layout_version) throw new Error('Unsupported Run/layout version');
  if (typeof raw.horizon_s !== 'number' || !Number.isFinite(raw.horizon_s) || raw.horizon_s < 0) throw new Error('Invalid Run horizon');
  if (!Array.isArray(raw.actors) || !Array.isArray(raw.actions) || !Array.isArray(raw.events) || !Array.isArray(raw.cargo)) throw new Error('Incomplete inline Run v2');
  const actors = raw.actors.map(value => { const a = object(value), pos = position(a.initial_pos); if (!pos || !text(a.actor_id) || !['picker', 'packer', 'receiver', 'shipper', 'forklift_driver'].includes(String(a.role))) throw new Error('Invalid Run actor'); return { ...a, initial_pos: pos } as ActorDefinition; });
  const events = raw.events.map(value => { const e = object(value); if (!Number.isInteger(e.seq) || typeof e.at_s !== 'number' || !Number.isFinite(e.at_s) || e.at_s < 0 || !Number.isInteger(e.phase) || !text(e.kind) || !text(e.entity_id)) throw new Error('Invalid Run event'); return { ...e, payload: object(e.payload) } as VisualEvent; }).sort(eventOrder);
  const actions = raw.actions.map(value => { const a = object(value); return { ...a, pos: a.pos === undefined ? undefined : position(a.pos), waypoints: Array.isArray(a.waypoints) ? a.waypoints.map(v => { const p = object(v), pos = position(p.pos); if (!pos) throw new Error('Invalid waypoint'); return { node_id: String(p.node_id), pos, at_s: Number(p.at_s) }; }) : undefined } as VisualAction; });
  const warnings = new Set<string>();
  const tracks = new Map<string, CargoTrack>();
  for (const value of raw.cargo) {
    const c = object(value), id = text(c.cargo_id), kind = text(c.kind);
    if (!id || !['tote', 'parcel', 'pallet', 'lot'].includes(kind ?? '') || tracks.has(id)) throw new Error('Invalid/duplicate cargo');
    tracks.set(id, { cargo_id: id, kind: kind as CargoKind, order_ids: Array.isArray(c.order_ids) ? c.order_ids.map(String) : [], states: [{ at_s: 0, pos: [0, 0, 0], yaw: 0, visible: false, stage: 'location_not_exported', attachment: { kind: 'world' } }], motions: [] });
  }
  const unknown = (id: string) => { if (!tracks.has(id)) warnings.add('Event refers to absent cargo: ' + id); return tracks.get(id); };
  const put = (id: string | undefined, at_s: number, stage: string, pos?: Vec3, visible = true, attachment: CargoState['attachment'] = { kind: 'world' }) => {
    if (!id) return;
    const track = unknown(id); if (!track) return;
    const previous = track.states.at(-1)!;
    track.states.push({ at_s, pos: pos ?? [...previous.pos], yaw: previous.yaw, visible: visible && (!!pos || attachment.kind !== 'world' || previous.visible), stage, attachment });
    if (visible && !pos && attachment.kind === 'world' && !previous.visible) warnings.add('No physical location for ' + id + ' at ' + stage + '; hidden until a location is exported');
  };
  const entered = (id: string | undefined, at_s: number, cellId: string | undefined) => {
    if (!id || !cellId) return;
    const cell = conveyorCell(cellId), track = unknown(id);
    if (!cell || !track) { warnings.add('Unknown cell ' + cellId); return; }
    put(id, at_s, 'conveyor', cell.from);
    track.motions.push({ start_s: at_s, end_s: at_s + 1, stage: 'conveyor', waypoints: [{ node_id: cellId + ':in', pos: cell.from, at_s }, { node_id: cellId + ':out', pos: cell.to, at_s: at_s + 1 }] });
    put(id, at_s + 1, 'cell_boundary', cell.to);
  };
  const initial = object(raw.initial_state ?? {});
  if (initial.cells && typeof initial.cells === 'object') for (const [cellId, data] of Object.entries(initial.cells)) { const id = typeof data === 'string' ? data : data && typeof data === 'object' ? text((data as ObjectValue).cargo_id) : undefined; if (id) entered(id, 0, cellId); }
  const totesByOrder = new Map<string, string>();
  for (const e of events) {
    const p = e.payload, order = text(p.order_id), tote = text(p.tote_id) ?? (order ? totesByOrder.get(order) : undefined), parcel = text(p.parcel_id), pallet = text(p.pallet_id), actor = text(p.actor_id);
    const explicit = position(p.pos) ?? position(p.position);
    if (e.kind === 'order_assigned' && order && tote && actor) { totesByOrder.set(order, tote); put(tote, e.at_s, 'picking', undefined, true, { kind: 'actor', id: actor, offset: [0, .553, .62], anchor: 'cart' }); }
    if (e.kind === 'tote_inducted') entered(tote ?? e.entity_id, e.at_s, text(p.cell_id));
    if (e.kind === 'cell_entered') entered(text(p.cargo_id) ?? e.entity_id, e.at_s, text(p.cell_id));
    if (e.kind === 'pack_started') { const station = layout.pack_stations.find(s => s.pack_id === p.pack_id); put(tote, e.at_s, 'pack_wip', explicit ?? (station ? [...station.input_anchor] as Vec3 : undefined)); }
    if (e.kind === 'order_packed') { put(tote, e.at_s, 'virtual_empty_return', undefined, false); const station = layout.pack_stations.find(s => s.pack_id === p.pack_id); put(parcel ?? e.entity_id, e.at_s, 'packed', explicit ?? (station ? [...station.output_anchor] as Vec3 : undefined)); }
    if (e.kind === 'parcel_outfed') entered(parcel ?? e.entity_id, e.at_s, text(p.cell_id) ?? (typeof p.pack_id === 'string' ? layout.pack_stations.find(s => s.pack_id === p.pack_id)?.output_segment_id + ':0' : undefined));
    if (e.kind === 'shipping_arrived') put(parcel ?? e.entity_id, e.at_s, 'shipping_buffer', explicit ?? [...layout.conveyor.terminal.shipping_buffer_pos] as Vec3);
    if (e.kind === 'parcel_scanned' && pallet) { put(pallet, e.at_s, 'open_pallet', explicit); put(parcel, e.at_s, 'palletized', undefined, true, { kind: 'cargo', id: pallet, offset: [0, .14, 0] }); }
    if (e.kind === 'pallet_sealed') put(pallet ?? e.entity_id, e.at_s, 'sealed_pallet', explicit);
    if (e.kind === 'receipt_accepted') put(pallet ?? e.entity_id, e.at_s, 'receiving', explicit);
    if (e.kind === 'pallet_putaway') put(pallet ?? e.entity_id, e.at_s, 'reserve_staging', explicit);
    if (e.kind === 'order_dispatched') { put(pallet ?? e.entity_id, e.at_s, 'dispatched', undefined, false); for (const id of Array.isArray(p.parcel_ids) ? p.parcel_ids : []) put(String(id), e.at_s, 'dispatched', undefined, false); }
    // Optional exporter enrichment; generic payload schema currently permits it.
    if (text(p.cargo_id) && p.attachment && typeof p.attachment === 'object') {
      const attachment = object(p.attachment), kind = text(attachment.kind);
      if (['world', 'actor', 'vehicle', 'cargo'].includes(kind ?? '')) put(text(p.cargo_id), e.at_s, text(p.stage) ?? e.kind, explicit, true, { kind: kind as CargoState['attachment']['kind'], id: text(attachment.id), offset: position(attachment.offset), anchor: text(attachment.anchor) });
    }
  }
  for (const track of tracks.values()) { track.states.sort((a, b) => a.at_s - b.at_s); track.motions.sort((a, b) => a.start_s - b.start_s); }
  if (Array.isArray(raw.snapshots) && raw.snapshots.length) warnings.add('Inline events compiled into indexed visual timelines; opaque business snapshot payload is not interpreted');
  const duration = events.reduce((max, e) => Math.max(max, e.at_s), actions.reduce((max, a) => Math.max(max, a.end_s), Number(raw.horizon_s) || 0));
  const result: VisualRun = { run_id: String(raw.run_id), layout_version: String(raw.layout_version), source: 'run-v2', label: 'Run v2 · ' + String(raw.run_id), duration_s: duration, actors, actions, events, cargo: [...tracks.values()], blocked: actions.filter(a => a.state === 'BLOCKED' && a.operation.includes('conveyor')).map(a => ({ start_s: a.start_s, end_s: a.end_s, segment_ids: [] })), warnings: [...warnings], notes: ['Backend metrics are not recalculated by this render adapter.', 'Standard actor intervals and cell events are supported. Cargo attachment/unknown service anchors require explicit exported placement; unsupported locations are reported, not fabricated.'] };
  compileVisualRun(result);
  return result;
}
