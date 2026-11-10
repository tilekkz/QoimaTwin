import type {XYZ} from '../warehouseTypes';
import type {FlowFrame, FlowStationFrame, FlowStationId} from './twinFlowScenario';

type Point = {x: number; y: number};
type Clip = Point & {w: number; h: number};
type Status = FlowStationFrame['status'];

export function packingStationPositions(rows: readonly {pack_id: string; table_origin: XYZ}[]) {
  const positions = new Map<FlowStationId, XYZ>();
  for (const row of rows) if (['PK03', 'PK05', 'PK06'].includes(row.pack_id)) {
    positions.set(row.pack_id as FlowStationId, [row.table_origin[0], 5, row.table_origin[2]]);
  }
  return positions;
}

export function stationPresentation(status: Status, helpRequested: boolean) {
  const states = {
    processing: {state: 'work', text: 'Работает'},
    outage: {state: 'sos', text: 'Остановлен'},
    reserved: {state: 'transfer', text: 'Передача'},
    idle: {state: 'ready', text: 'Готов'},
    unavailable: helpRequested
      ? {state: 'support', text: 'Ждёт помощника'}
      : {state: 'reserve', text: 'Резерв'},
  };
  return states[status];
}

export function createTwinStationIndicators(host: HTMLElement,
  positions: ReadonlyMap<FlowStationId, XYZ>) {
  const markers = new Map<FlowStationId, HTMLElement>();
  for (const id of positions.keys()) {
    const marker = host.ownerDocument.createElement('div');
    marker.className = 'tw-station-indicator glass';
    const title = host.ownerDocument.createElement('b');
    const detail = host.ownerDocument.createElement('span');
    title.textContent = id;
    marker.append(title, detail);
    marker.hidden = true;
    host.append(marker);
    markers.set(id, marker);
  }
  function update(frame: FlowFrame | undefined, project: (position: XYZ) => Point,
    clip: Clip, enabled: boolean) {
    for (const [id, marker] of markers) {
      const station = frame?.stations.find(row => row.station_id === id);
      const point = project(positions.get(id)!);
      marker.hidden = !enabled || !station || (id !== 'PK03'
        && (frame?.variant !== 'B' || !frame.decision.applied))
        || !Number.isFinite(point.x) || !Number.isFinite(point.y)
        || point.x < clip.x || point.x > clip.x + clip.w
        || point.y < clip.y || point.y > clip.y + clip.h;
      if (marker.hidden || !station) continue;
      const helpRequested = !!frame?.decision.applied && station.staff_ready_s !== null
        && frame.at_s < station.staff_ready_s;
      const presentation = stationPresentation(station.status, helpRequested);
      if (marker.dataset.state !== presentation.state) {
        marker.dataset.state = presentation.state;
        marker.lastElementChild!.textContent = presentation.text;
        marker.setAttribute('aria-label', id + ' · ' + presentation.text);
      }
      marker.style.left = point.x + 'px';
      marker.style.top = point.y + 'px';
    }
  }
  function dispose() {
    for (const marker of markers.values()) marker.remove();
    markers.clear();
  }
  return {update, dispose};
}
