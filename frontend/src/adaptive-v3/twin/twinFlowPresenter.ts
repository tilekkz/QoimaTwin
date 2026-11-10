import type {PresenterStep} from './twinScenario';
import type {TwinFlowScenario} from './twinFlowScenario';

export type FlowPresenterStep = PresenterStep & {view: 'flow' | 'warehouse'};
type DraftStep = Omit<FlowPresenterStep, 'focus'>;
type PresentationCounts = {workers: number; vehicles: number};

function need(value: unknown, message: string): asserts value {
    if (!value) throw Error(message);
}
function staffReady(scenario: TwinFlowScenario) {
    const chapter = scenario.chapters.find(row => row.id === 'staff_ready');
    need(chapter && Number.isFinite(chapter.at_s) && chapter.at_s >= 0 && chapter.at_s <= scenario.duration_s, 'Flow presenter requires a staff-arrival cut');
    const stations = scenario.sample('B', chapter.at_s).stations;
    need(['PK05', 'PK06'].every(id => stations.some(row => row.station_id === id && row.available)), 'Flow presenter requires both helpers to be available');
    return chapter.at_s;
}
function parallelCut(scenario: TwinFlowScenario, ready: number) {
    const activities = scenario.audit('B').activities.filter(row => row.phase === 'packing');
    const target = Math.min(ready + 30, scenario.comparison_horizon_s);
    let selected = Math.min(ready + scenario.work_basis_s, scenario.duration_s);
    let distance = Infinity;
    for (const left of activities.filter(row => row.station_id === 'PK05')) {
        for (const right of activities.filter(row => row.station_id === 'PK06')) {
            const from = Math.max(ready, left.from_s, right.from_s);
            const to = Math.min(scenario.duration_s, left.to_s, right.to_s);
            if (to <= from) continue;
            const cut = target > from && target < to ? target : (from + to) / 2;
            if (Math.abs(cut - target) >= distance) continue;
            selected = cut;
            distance = Math.abs(cut - target);
        }
    }
    return selected;
}
function earlySteps(scenario: TwinFlowScenario, counts: PresentationCounts, ready: number): DraftStep[] {
    const initial = scenario.sample('A', 0);
    const decision = initial.decision.at_s;
    const queueAt = Math.min(decision - 1, initial.outage.from_s + 10);
    need(queueAt >= 0 && decision <= ready, 'Flow presenter requires ordered story cuts');
    const queued = scenario.sample('A', queueAt).counts.waiting;
    const rerouted = scenario.sample('B', decision).decision.rerouted_count;
    return [
        {title: 'Склад в работе', t: 0, mode: 'side', view: 'warehouse',
            text: `В демонстрационном эпизоде в каждой копии персонал — ${counts.workers}, погрузчики — ${counts.vehicles}. Общий поток — ${scenario.jobs.length} грузов, часть уже находится на линии в начале.`},
        {title: 'Очередь у PK03', t: queueAt, mode: 'side', view: 'flow', sheet: 'now',
            text: `PK03 недоступен в ${initial.outage.from_s}–${initial.outage.to_s} с, ожидают — ${queued}. Одинаковый поток в A и B упирается в один недоступный пост.`},
        {title: 'Подключаем резерв', t: decision, mode: 'side', view: 'flow',
            text: `На ${decision} с B направляет поток на PK05 и PK06, переназначено грузов — ${rerouted}. Выбраны только грузы, которые ещё могут попасть туда по направлению линии.`},
        {title: 'Помощь на месте', t: ready, mode: 'side', view: 'flow', play: true,
            text: `К ${Math.ceil(ready)} с помощники прибыли на PK05 и PK06. Посты начинают обслуживание, когда к ним доходит очередной груз.`},
    ];
}
function laterSteps(scenario: TwinFlowScenario, ready: number): DraftStep[] {
    const workingAt = parallelCut(scenario, ready);
    const working = scenario.sample('B', workingAt);
    const posts = working.stations.filter(row => row.status === 'processing').length;
    const comparison = scenario.comparison_horizon_s;
    const a = scenario.sample('A', comparison), b = scenario.sample('B', comparison);
    const endA = scenario.sample('A', scenario.duration_s), endB = scenario.sample('B', scenario.duration_s);
    const remaining = endA.counts.arrived - endA.counts.completed;
    const final = remaining > 0 ? 'работа в A не завершена' : 'все прибывшие грузы A покинули линию';
    return [
        {title: posts >= 2 ? 'Поток снова движется' : 'Помощь готова к работе', t: workingAt, mode: 'side', view: 'flow', play: true,
            text: `В B постов в работе — ${posts}, упаковано — ${working.counts.packed}. В очереди ещё ${working.counts.waiting} грузов, помощь разбирает общий поток.`},
        {title: 'Одинаковый момент', t: comparison, mode: 'swipe', view: 'flow', sheet: 'now',
            text: `На ${comparison} с упаковано A — ${a.counts.packed}, B — ${b.counts.packed}, ожидают A — ${a.counts.waiting}, B — ${b.counts.waiting}. Сдвиньте разделитель и сравните один и тот же момент.`},
        {title: 'Результат перераспределения', t: scenario.duration_s, mode: 'side', view: 'flow', sheet: 'now',
            text: `Упаковано A — ${endA.counts.packed}, B — ${endB.counts.packed}, вышло с линии A — ${endA.counts.completed}, B — ${endB.counts.completed}. В конце демонстрации ${final}, помощники B вернулись к своим постам.`},
    ];
}
/** Narration is a projection of one compiled visual episode and runtime entity counts. */
export function createTwinFlowPresenter(scenario: TwinFlowScenario, counts: PresentationCounts): FlowPresenterStep[] {
    need(scenario.source_kind === 'visual_fixture' && scenario.engine_operation === false && scenario.operational_admission === false, 'Flow presenter requires a visual episode');
    need(Number.isFinite(scenario.duration_s) && scenario.duration_s >= scenario.comparison_horizon_s && scenario.jobs.length > 0, 'Flow presenter requires a bounded episode');
    need(Number.isSafeInteger(counts.workers) && counts.workers > 0 && Number.isSafeInteger(counts.vehicles) && counts.vehicles > 0, 'Flow presenter requires actual presentation counts');
    const ready = staffReady(scenario);
    return [...earlySteps(scenario, counts, ready), ...laterSteps(scenario, ready)].map(step => ({
        ...step,
        focus: step.view === 'flow' ? {target: [106.5, 1, 4], span: 52} : {target: [72, 1.5, 36], span: 184},
    }));
}
