import type {XYZ} from '../warehouseTypes';

type CarrierFrame = {
  id: string;
  visible: boolean;
  payload: 'tote' | 'parcel';
  position: XYZ;
};
type Point = {x: number; y: number};
type Clip = Point & {w: number; h: number};

export function createTwinCarrierIndicators(host: HTMLElement) {
  const markers = new Map<string, HTMLElement>();
  function update(frames: readonly CarrierFrame[], pixelsPerMetre: number,
    project: (position: XYZ) => Point, clip: Clip) {
    const active = new Set(frames.map(frame => frame.id));
    for (const frame of frames) {
      let marker = markers.get(frame.id);
      if (!marker) {
        marker = host.ownerDocument.createElement('span');
        marker.className = 'tw-carrier-indicator';
        marker.setAttribute('aria-hidden', 'true');
        host.append(marker);
        markers.set(frame.id, marker);
      }
      const point = project(frame.position);
      marker.hidden = !frame.visible || pixelsPerMetre >= 16 || !Number.isFinite(point.x)
        || !Number.isFinite(point.y) || point.x < clip.x || point.x > clip.x + clip.w
        || point.y < clip.y || point.y > clip.y + clip.h;
      marker.dataset.payload = frame.payload;
      marker.style.left = point.x + 'px';
      marker.style.top = point.y + 'px';
    }
    for (const [id, marker] of markers) if (!active.has(id)) marker.hidden = true;
  }
  function dispose() {
    for (const marker of markers.values()) marker.remove();
    markers.clear();
  }
  return {update, dispose};
}
