import './style.css';
import '../adaptive-v3/warehouse.css';
import { adaptWarehouseV3, WAREHOUSE_BASE_FILES, type WarehouseTexts } from '../adaptive-v3/warehouseAdapter';
import { createWarehouseScene } from '../adaptive-v3/warehouseScene';
import { decodeArmStream, integer, need, verifyArmPair, type ArmData, type ArmName } from './stream';
import { compilePlayback, createPlaybackClock, type PlaybackFrame } from './playback';
import { createNativeLayer, nativeGeometry } from './scene';
const element = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const status = element<HTMLElement>('native-status'), host = element<HTMLElement>('native-viewport');
const pairInput = element<HTMLInputElement>('native-pair'), armInput = element<HTMLSelectElement>('native-arm');
const seek = element<HTMLInputElement>('native-seek'), play = element<HTMLButtonElement>('native-play');
const loadButton = element<HTMLButtonElement>('native-load'), controls = element<HTMLFieldSetElement>('native-controls');
let controller: AbortController | undefined, scene: Awaited<ReturnType<typeof createWarehouseScene>> | undefined;
let layer: ReturnType<typeof createNativeLayer> | undefined, clock: ReturnType<typeof createPlaybackClock> | undefined;
let models: Record<ArmName, ReturnType<typeof compilePlayback>> | undefined, arms: Record<ArmName, ArmData> | undefined;
let frame: PlaybackFrame | undefined, phase = 'empty', serial = 0, animation = 0, previous = 0, lastInfo = 0;
let restoreLoad = false;
const selected = (): ArmName => armInput.value === 'candidate' ? 'candidate' : 'baseline';
const seconds = (tick: number) => (tick / 1000000).toFixed(3);
function stopScene() {
    cancelAnimationFrame(animation);
    animation = 0;
    clock?.pause();
    layer?.dispose();
    layer = undefined;
    scene?.dispose();
    scene = undefined;
    models = undefined;
    arms = undefined;
    frame = undefined;
    clock = undefined;
    controls.disabled = true;
}
function draw() {
    if (!clock || !models || !arms)
        return;
    frame = models[selected()].sample(clock.tick);
    seek.value = String(clock.tick);
    element<HTMLOutputElement>('native-time').value = seconds(clock.tick) + ' с · ' + clock.tick + ' ticks';
    play.textContent = clock.playing ? 'Пауза' : 'Воспроизвести';
    if (performance.now() - lastInfo > 100 || !clock.playing) {
        const catalog = arms[selected()].catalog;
        element<HTMLElement>('native-facts').textContent = JSON.stringify({ arm: selected(), status: catalog.status, observed_until_tick: catalog.observed_until_tick, outcome: catalog.outcome, tick: frame.tick, carriers: frame.carriers.map(c => ({ job: c.job_id, carrier: c.hu_id, payload: c.payload_id, status: c.status })), relocation: frame.relocations.map(r => ({ hu: r.hu_id, custody: r.custody, status: r.status, taken_tick: r.taken_tick, placed_tick: r.placed_tick, returned_tick: r.returned_tick })) }, null, 2);
        lastInfo = performance.now();
    }
    scene?.requestRender();
}
function advance(now: number) {
    if (!clock?.playing) {
        animation = 0;
        return;
    }
    clock.advance(Math.min(.25, Math.max(0, (now - previous) / 1000)));
    previous = now;
    draw();
    animation = clock.playing ? requestAnimationFrame(advance) : 0;
}
function setPlaying(value: boolean) {
    if (!clock)
        return;
    if (value) {
        clock.play();
        previous = performance.now();
        if (!animation)
            animation = requestAnimationFrame(advance);
    }
    else {
        clock.pause();
        cancelAnimationFrame(animation);
        animation = 0;
    }
    draw();
}
function seekTick(value: number) {
    if (!clock)
        return;
    setPlaying(false);
    clock.seek(value);
    draw();
}
async function readArm(arm: ArmName, pair: string, signal: AbortSignal, mode: string, budgetBytes: number): Promise<ArmData> {
    let body: ReadableStream<Uint8Array>;
    if (mode === 'files') {
        const file = element<HTMLInputElement>('native-' + arm + '-file').files?.[0];
        need(file && file.size <= 192 * 1024 * 1024, 'Выберите NDJSON-файл ' + arm + ' до 192 MiB.');
        body = file.stream();
    }
    else {
        const response = await fetch('/api/v3/relocation-pairs/' + pair + '/arms/' + arm + '/bundle', { signal, cache: 'no-store' });
        need(response.ok && response.body && response.headers.get('content-type')?.includes('application/x-ndjson'), 'API ' + arm + ' вернул ' + response.status);
        body = response.body;
    }
    return decodeArmStream(body, pair, arm, { signal, budgetBytes, progress: (loaded, total) => { status.textContent = arm + ' · проверено файлов ' + loaded + ' / ' + total; } });
}
async function readGeometry(signal: AbortSignal) {
    const entries = Object.entries(WAREHOUSE_BASE_FILES);
    const values = await Promise.all(entries.map(async ([key, path]) => {
        const response = await fetch(import.meta.env.BASE_URL + path.replace(/^\//, ''), { signal });
        need(response.ok, 'Не загружена исходная геометрия ' + key);
        return [key, await response.text()] as const;
    }));
    return adaptWarehouseV3(Object.fromEntries(values) as WarehouseTexts);
}
async function preparePlayback(signal: AbortSignal, pair: string, mode: string) {
    const baseline = await readArm('baseline', pair, signal, mode, 64 * 1024 * 1024);
    const remaining = 64 * 1024 * 1024 - baseline.retainedBytes;
    need(remaining > 0, 'Native pair cache budget exhausted before candidate');
    const candidate = await readArm('candidate', pair, signal, mode, remaining);
    verifyArmPair(baseline, candidate);
    const bundle = await readGeometry(signal);
    signal.throwIfAborted();
    const a = compilePlayback(baseline, nativeGeometry(bundle, baseline));
    const b = compilePlayback(candidate, nativeGeometry(bundle, candidate));
    arms = { baseline, candidate };
    models = { baseline: a, candidate: b };
    const end = Math.min(a.observed, b.observed);
    clock = createPlaybackClock(end);
    clock.setRate(Number(element<HTMLSelectElement>('native-speed').value));
    seek.max = String(end);
    seek.value = '0';
    frame = models[selected()].sample(0);
    element<HTMLElement>('native-identity').textContent = 'pair ' + pair + '\nA ' + baseline.header.native_run_id + '\nB ' + candidate.header.native_run_id + '\nКэш проекции ' + ((baseline.retainedBytes + candidate.retainedBytes) / 1048576).toFixed(2) + ' MiB / 64 MiB';
    return bundle;
}
function sourceDisabled(value: boolean) {
    for (const id of ['native-pair', 'native-source', 'native-baseline-file', 'native-candidate-file'])
        element<HTMLInputElement | HTMLSelectElement>(id).disabled = value;
}
function validateSource(pair: string, mode: string) {
        need(/^[a-f0-9]{64}$/.test(pair), 'Нужен полный 64-символьный pair ID.');
        if (mode === 'files')
            for (const arm of ['baseline', 'candidate'])
                need(element<HTMLInputElement>('native-' + arm + '-file').files?.[0], 'Выберите оба NDJSON-файла baseline и candidate.');
}
async function load() {
    const token = ++serial;
    controller?.abort();
    stopScene();
    controller = new AbortController();
    const signal = controller.signal, pair = pairInput.value.trim(), mode = element<HTMLSelectElement>('native-source').value;
    phase = 'loading';
    loadButton.disabled = true;
    sourceDisabled(true);
    element<HTMLButtonElement>('native-cancel').disabled = false;
    status.textContent = 'Читаем native NDJSON. Серверная строгая проверка может занять несколько минут.';
    try {
        validateSource(pair, mode);
        const bundle = await preparePlayback(signal, pair, mode);
        need(token === serial, 'Загрузка заменена новой.');
        status.textContent = 'Загружаем исходные модели склада A…';
        const loadedScene = await createWarehouseScene(host, bundle, { signal, progress: (done, total) => { if (token === serial && !signal.aborted) status.textContent = 'Модели ' + done + ' / ' + total; }, select: () => undefined, renderPass(renderer, world, camera) {
                if (token !== serial || signal.aborted)
                    return;
                layer ??= createNativeLayer(world, bundle);
                if (frame)
                    layer.apply(frame);
                renderer.render(world, camera);
            } });
        if (token !== serial || signal.aborted) {
            loadedScene.dispose();
            return;
        }
        scene = loadedScene;
        phase = 'ready';
        controls.disabled = false;
        scene.frameAt([92.775, .92, 4.15], 85);
        status.textContent = 'Native pair проверена. Управление использует локальные записи. Исходная геометрия A в обоих вариантах.';
        draw();
    }
    catch (error) {
        if (token !== serial)
            return;
        stopScene();
        phase = 'error';
        status.textContent = signal.aborted ? 'Чтение остановлено. Можно выбрать файлы и повторить.' : error instanceof Error ? error.message : 'Не удалось открыть native pair.';
    }
    finally {
        if (token === serial) {
            loadButton.disabled = false;
            sourceDisabled(false);
            element<HTMLButtonElement>('native-cancel').disabled = true;
        }
    }
}
loadButton.addEventListener('click', () => void load());
play.addEventListener('click', () => setPlaying(!clock?.playing));
seek.addEventListener('input', () => seekTick(integer(Number(seek.value))));
armInput.addEventListener('change', draw);
element<HTMLButtonElement>('native-reset').addEventListener('click', () => seekTick(0));
element<HTMLButtonElement>('native-cancel').addEventListener('click', () => controller?.abort());
element<HTMLSelectElement>('native-speed').addEventListener('change', event => { clock?.setRate(Number((event.target as HTMLSelectElement).value)); draw(); });
element<HTMLSelectElement>('native-source').addEventListener('change', event => { element<HTMLElement>('native-files').hidden = (event.target as HTMLSelectElement).value !== 'files'; });
element<HTMLButtonElement>('native-overview').addEventListener('click', () => scene?.setView('overview'));
element<HTMLButtonElement>('native-conveyor').addEventListener('click', () => {
    if (!clock)
        return;
    seekTick(Math.min(220000000, Number(seek.max)));
    scene?.frameAt([92.775, .92, 4.15], 85);
});
element<HTMLButtonElement>('native-relocation').addEventListener('click', () => {
    if (!clock || !models)
        return;
    armInput.value = 'candidate';
    seekTick(Math.min(80000000, Number(seek.max)));
    const position = models.candidate.sample(Math.min(86740000, Number(seek.max))).relocations[0]?.position;
    if (position)
        scene?.frameAt(position, 30);
});
document.addEventListener('visibilitychange', () => {
    if (document.hidden)
        setPlaying(false);
});
function dispose() { serial++; controller?.abort(); stopScene(); phase = 'disposed'; restoreLoad = false; }
host.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    if (phase !== 'loading' && phase !== 'ready')
        return;
    serial++;
    controller?.abort();
    stopScene();
    phase = 'error';
    loadButton.disabled = false;
    sourceDisabled(false);
    element<HTMLButtonElement>('native-cancel').disabled = true;
    status.textContent = 'Графика браузера перезапустилась. Повторите загрузку.';
}, true);
window.addEventListener('pagehide', () => {
    const wasLoading = phase === 'loading' || phase === 'ready';
    dispose();
    restoreLoad = wasLoading;
});
window.addEventListener('pageshow', event => {
    if (!event.persisted || phase !== 'disposed')
        return;
    phase = 'empty';
    loadButton.disabled = false;
    sourceDisabled(false);
    element<HTMLButtonElement>('native-cancel').disabled = true;
    const reload = restoreLoad;
    restoreLoad = false;
    if (reload)
        void load();
    else
        status.textContent = 'Выберите два сохранённых ответа bundle или API. Загрузка начинается по кнопке.';
});
Object.assign(window, { __QOIMA_NATIVE_PAIR__: { snapshot: () => ({ phase, pair_id: arms?.baseline.header.pair_id ?? null, source_kind: 'verified_saved_native_pair', arm: selected(), tick: clock?.tick ?? null, playing: clock?.playing ?? false, rate: clock?.rate ?? null, retained_bytes: arms ? arms.baseline.retainedBytes + arms.candidate.retainedBytes : 0, physical_admission: false, full_n1_acceptance: false, presentation_interpolation: true, frame }), dispose } });
