import type {FlowFrame} from './twinFlowScenario';
import type {OperationPanel} from './twinOperationView';

type Variant = 'A' | 'B';
type Metrics = {queue: number; packed: number; working: number};
type Phase = 'steady' | 'pressure' | 'support' | 'draining' | 'packed';
export type OperationsInput = {
  A: FlowFrame;
  B: FlowFrame;
  totalJobs: number;
  totalWorkers: number;
  totalVehicles: number;
  helpersTravelling: number;
};
const COPY: Record<Phase, {title: string; text: string}> = {
  steady: {title: 'Партия поступает на линию', text: 'Два варианта получают одинаковый поток.'},
  pressure: {title: 'Очередь на упаковке', text: 'Грузы ожидают освобождения ветки PK03.'},
  support: {title: 'Поддержка идёт к постам', text: 'Резервные посты ждут прибытия помощников.'},
  draining: {title: 'Резервные посты разбирают очередь', text: 'Поток распределён по доступным веткам.'},
  packed: {title: 'B упаковал всю партию', text: 'Сравните оставшуюся очередь в варианте A.'},
};
function metrics(frame: FlowFrame): Metrics {
  return {queue: frame.queue.main, packed: frame.counts.packed,
    working: frame.stations.filter(station => station.status === 'processing').length};
}
export function operationSummary(input: OperationsInput) {
  let phase: Phase = 'steady';
  if (input.B.counts.packed === input.totalJobs && input.totalJobs > 0) phase = 'packed';
  else if (input.B.decision.applied && input.helpersTravelling > 0) phase = 'support';
  else if (input.B.decision.applied && (input.B.queue.total < input.A.queue.total
    || input.B.counts.packed > input.A.counts.packed)) phase = 'draining';
  else if (input.A.queue.total > 0 || input.A.outage.active) phase = 'pressure';
  return {A: metrics(input.A), B: metrics(input.B), phase, ...COPY[phase],
    scope: `${input.totalJobs} грузов · команда ${input.totalWorkers}`
      + ` · погрузчиков ${input.totalVehicles} · демо-сценарий`};
}
function createCounter(document: Document, variant: Variant) {
  const root = document.createElement('div');
  root.className = 'tw-operation-counts glass';
  root.dataset.variant = variant;
  root.innerHTML = '<span><small>Очередь на линии</small><strong data-value="queue">0</strong></span>'
    + '<span><small>Упаковано</small><strong data-value="packed">0</strong></span>'
    + '<span><small>Постов в работе</small><strong data-value="working">0</strong></span>';
  const values = Object.fromEntries(['queue', 'packed', 'working'].map(key =>
    [key, root.querySelector<HTMLElement>(`[data-value="${key}"]`)!])) as Record<keyof Metrics, HTMLElement>;
  return {root, values};
}
function positionCounter(root: HTMLElement, panel: OperationPanel, width: number) {
  const {x, y, w} = panel.rect;
  const narrow = w < 600;
  root.style.left = narrow ? x + 12 + 'px' : '';
  root.style.right = narrow ? '' : Math.max(12, width - x - w + 12) + 'px';
  root.style.top = y + (narrow ? 52 : 10) + 'px';
}
export function createTwinOperationsHud(host: HTMLElement) {
  const document = host.ownerDocument;
  const banner = document.createElement('div');
  banner.className = 'tw-operation-story';
  banner.innerHTML = '<strong></strong><span></span><small></small>';
  banner.querySelector('strong')!.setAttribute('aria-live', 'polite');
  const title = banner.querySelector('strong')!, description = banner.querySelector('span')!;
  const scope = banner.querySelector('small')!;
  const counters = {A: createCounter(document, 'A'), B: createCounter(document, 'B')};
  banner.hidden = true;
  counters.A.root.hidden = true; counters.B.root.hidden = true;
  host.append(banner, counters.A.root, counters.B.root);
  let key = '', layoutKey = '';
  function update(input: OperationsInput, panels: readonly OperationPanel[]) {
    const nextLayout = JSON.stringify(panels);
    if (nextLayout !== layoutKey) {
      layoutKey = nextLayout;
      const width = host.clientWidth;
      banner.hidden = panels.length === 0;
      for (const counter of Object.values(counters)) counter.root.hidden = true;
      for (const panel of panels) {
        counters[panel.variant].root.hidden = false;
        positionCounter(counters[panel.variant].root, panel, width);
      }
    }
    const summary = operationSummary(input), next = JSON.stringify(summary);
    if (next === key) return;
    key = next;
    title.textContent = summary.title; description.textContent = summary.text;
    scope.textContent = summary.scope; banner.dataset.phase = summary.phase;
    for (const variant of ['A', 'B'] as const) {
      for (const field of ['queue', 'packed', 'working'] as const)
        counters[variant].values[field].textContent = String(summary[variant][field]);
    }
  }
  return {update, dispose() {banner.remove(); counters.A.root.remove(); counters.B.root.remove();}};
}
