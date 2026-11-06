import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const baseURL = (process.env.QOIMA_TEST_BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
test.use({ launchOptions: { args: ['--mute-audio'] } });

async function openWarehouse(page: Page, context: BrowserContext) {
  const errors: string[] = [], models = new Map<string, number>();
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.pathname.endsWith('.glb')) models.set(url.pathname, response.status());
  });
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === new URL(baseURL).origin || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
    errors.push('External resource: ' + url.href);
    return route.abort();
  });
  await page.goto(baseURL);
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'ready', { timeout: 45_000 });
  await page.waitForFunction(() => (window as any).__QOIMA_VIEWER__?.getPerfState().calls > 0);
  return { errors, models };
}
const state = (page: Page) => page.evaluate(() => (window as any).__QOIMA_VIEWER__.getState());
const frame = (page: Page) => page.evaluate(() => (window as any).__QOIMA_VIEWER__.replay.getFrame());
async function renderedFrames(page: Page, count = 3) {
  await page.evaluate(async count => {
    for (let i = 0; i < count; i++) await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
  }, count);
}
async function seekThroughUI(page: Page, time: number) {
  const controlTime = await page.getByRole('slider', { name: 'Время воспроизведения' }).evaluate((input, value) => {
    (input as HTMLInputElement).value = String(value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return Number((input as HTMLInputElement).value);
  }, time);
  // Native range step=.1 quantizes decimal event times; the replay follows the
  // control's actual value. Direct API seeks are checked separately below.
  expect(Math.abs(controlTime - time)).toBeLessThanOrEqual(.051);
  await expect.poll(async () => (await state(page)).replay.time).toBe(controlTime);
  await renderedFrames(page);
}

test('v2 overview renders the complete local registry with one canvas and mute', async ({ page, context }, testInfo) => {
  const { errors, models } = await openWarehouse(page, context), current = await state(page);
  expect(current.layoutVersion).toBe('qoima-72x48-v2');
  expect(current.counts).toMatchObject({ racks: 288, slots: 864, occupied: 600, actors: 24, vehicles: 2, packs: 6, conveyorCells: 179, skuCount: 200 });
  for (const [kind, count] of Object.entries({ actor: 24, rack: 288, slot: 600, cell: 179, vehicle: 2, pack: 6 })) {
    expect(current.renderedRegistry[kind], kind).toHaveLength(count);
    expect(new Set(current.renderedRegistry[kind]).size, kind + ' unique IDs').toBe(count);
  }
  expect(current.motion.actors).toHaveLength(24);
  expect(new Set(current.motion.actors).size).toBe(24);
  expect(Object.keys(current.logicalActorPositions)).toHaveLength(24);
  expect(Object.keys(current.slotRegistry)).toHaveLength(864);
  expect(current.quality).toBe('low');
  expect(current.calls).toBeGreaterThan(0);
  expect(current.calls).toBeLessThanOrEqual(180);
  expect(current.triangles).toBeGreaterThan(0);
  expect(current.triangles).toBeLessThanOrEqual(350_000);
  expect(current.audio).toMatchObject({ muted: true, unlocked: false, voices: 0 });
  expect(models.size).toBe(21);
  expect([...models.values()].every(status => status === 200)).toBe(true);
  await expect(page.locator('canvas')).toHaveCount(1);
  await expect(page.locator('[data-asset]')).toHaveCount(21);
  await expect(page.locator('.source-caption')).toContainText(/VISUAL DEMO|визуальная фикстура/i);
  await expect(page.locator('.source-caption')).toContainText('backend');
  await page.screenshot({ path: 'test-results/v2-runtime/overview.png' });
  await testInfo.attach('overview-render-metrics.json', { body: JSON.stringify({ calls: current.calls, triangles: current.triangles, memory: current.memory, counts: current.counts }), contentType: 'application/json' });
  expect(errors).toEqual([]);
});

test('zoom, slot selection, quality and responsive UI retain the full warehouse', async ({ page, context }) => {
  const { errors } = await openWarehouse(page, context), initial = (await state(page)).distance;
  const canvas = page.locator('canvas'), bounds = await canvas.boundingBox();
  expect(bounds).toBeTruthy();
  await page.mouse.move(bounds!.x + bounds!.width * .45, bounds!.y + bounds!.height * .6);
  await page.mouse.wheel(0, -300);
  await expect.poll(async () => (await state(page)).distance).toBeLessThan(initial);
  await page.getByRole('button', { name: /^Детали/ }).click();
  await expect(page.locator('.selection-tag')).toContainText('S_A01_B01_L_01');
  expect((await state(page)).selected).toBe('S_A01_B01_L_01');
  await page.getByRole('button', { name: /^Обзор/ }).click();
  await page.getByRole('button', { name: 'Поток / упаковка', exact: true }).click();
  expect((await state(page)).target[2]).toBeLessThan(14);
  for (const quality of ['high', 'low']) {
    await page.locator('.scene-controls select').selectOption(quality);
    await expect.poll(async () => (await state(page)).quality).toBe(quality);
  }
  expect((await state(page)).renderedRegistry.actor).toHaveLength(24);
  await page.getByRole('button', { name: /^Сверху/ }).click();
  await renderedFrames(page);
  await page.screenshot({ path: 'test-results/v2-runtime/top.png' });
  for (const viewport of [{ width: 720, height: 600 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport); await renderedFrames(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await expect(canvas).toBeVisible();
    expect((await state(page)).counts.actors).toBe(24);
    await page.screenshot({ path: `test-results/v2-runtime/responsive-${viewport.width}.png` });
  }
  expect(errors).toEqual([]);
});

test('play/pause, seek and reset hold the blocked tote and never duplicate cargo', async ({ page, context }) => {
  const { errors } = await openWarehouse(page, context);
  await page.getByRole('button', { name: 'Воспроизвести', exact: true }).click();
  await expect.poll(async () => (await state(page)).replay.time).toBeGreaterThan(.05);
  await page.getByRole('button', { name: 'Пауза', exact: true }).click();
  await expect.poll(async () => (await state(page)).replay.playing).toBe(false);
  const paused = (await state(page)).replay.time; await renderedFrames(page, 8);
  expect((await state(page)).replay.time).toBe(paused);
  await page.getByRole('combobox', { name: 'Скорость воспроизведения' }).selectOption('60');
  expect((await state(page)).replay.speed).toBe(60);
  await page.evaluate(() => (window as any).__QOIMA_VIEWER__.replay.seek(12.34567));
  expect((await state(page)).replay.time).toBe(12.34567);
  await seekThroughUI(page, 43); const blocked = await frame(page);
  expect(blocked.line.blocked).toBe(true);
  await expect(page.locator('.timeline-label .blocked')).toContainText('Линия удерживает груз');
  await seekThroughUI(page, 45);
  expect((await frame(page)).cargo.T001.pos).toEqual(blocked.cargo.T001.pos);
  await seekThroughUI(page, 49);
  expect((await frame(page)).line.blocked).toBe(false);
  expect((await frame(page)).cargo.T001.pos).not.toEqual(blocked.cargo.T001.pos);
  for (const time of [43, 83, 45, 0, 43]) {
    await seekThroughUI(page, time);
    const current = await state(page), snapshot = await frame(page);
    const visible = Object.values(snapshot.cargo).filter((cargo: any) => cargo.visible) as any[];
    expect(new Set(current.motion.cargo).size).toBe(current.motion.cargo.length);
    expect(current.motion.cargo.slice().sort()).toEqual(visible.map(cargo => cargo.id).sort());
    expect(current.renderedRegistry.tote).toHaveLength(96);
    expect(new Set(current.renderedRegistry.tote).size).toBe(96);
    for (const cargo of visible.filter(cargo => cargo.kind === 'tote')) {
      // inspectEntity returns the first real rendered instance. A leftover pool
      // copy would be found before the cargo batch and expose its wrong position.
      const actual = await page.evaluate(id => (window as any).__QOIMA_VIEWER__.inspectEntity(id), cargo.id);
      expect(actual).toBeTruthy();
      expect(Math.hypot(...actual.rootWorld.map((value: number, axis: number) => value - cargo.pos[axis]))).toBeLessThan(.002);
    }
    if (time === 43) expect(snapshot.cargo.T001.pos).toEqual(blocked.cargo.T001.pos);
    expect(current.motion.actors).toHaveLength(24);
  }
  await page.screenshot({ path: 'test-results/v2-runtime/blocked-tote.png' });
  await page.getByRole('button', { name: 'Сбросить время' }).click();
  const reset = await frame(page);
  expect(reset.time).toBe(0); expect((await state(page)).replay.playing).toBe(false);
  await page.getByRole('button', { name: 'Сбросить время' }).click();
  expect((await frame(page)).cargo).toEqual(reset.cargo);
  expect(errors).toEqual([]);
});

test('all reference gallery images load from the local project', async ({ page, context }) => {
  const { errors } = await openWarehouse(page, context);
  await page.getByRole('button', { name: /^Референсы/ }).click();
  const figures = page.locator('.gallery-grid figure'); await expect(figures).toHaveCount(21);
  for (let index = 0; index < 21; index++) {
    const image = figures.nth(index).locator('img'); await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).complete && (element as HTMLImageElement).naturalWidth > 0)).toBe(true);
    expect(new URL(await image.getAttribute('src') || '', baseURL).origin).toBe(new URL(baseURL).origin);
    expect(await image.getAttribute('src')).toContain('references/');
  }
  await page.getByRole('button', { name: 'Закрыть референсы' }).click();
  await expect(page.locator('.reference-gallery')).toHaveCount(0);
  await expect(page.locator('canvas')).toHaveCount(1); expect(errors).toEqual([]);
});

test('reduced motion pauses presentation without dropping actors or making sound', async ({ page, context }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const { errors } = await openWarehouse(page, context);
  expect((await state(page)).reducedMotion).toBe(true);
  expect((await state(page)).replay.playing).toBe(false);
  await page.getByRole('checkbox', { name: 'Спокойный режим' }).uncheck();
  await expect.poll(async () => (await state(page)).reducedMotion).toBe(false);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.getByRole('button', { name: 'Воспроизвести', exact: true }).click();
  await expect.poll(async () => (await state(page)).replay.playing).toBe(true);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect.poll(async () => (await state(page)).reducedMotion).toBe(true);
  await expect.poll(async () => (await state(page)).replay.playing).toBe(false);
  expect((await state(page)).renderedRegistry.actor).toHaveLength(24);
  expect((await state(page)).audio).toMatchObject({ muted: true, voices: 0 });
  expect(errors).toEqual([]);
});

test('wrong Run version is rejected through import UI without replacing the scene', async ({ page, context }) => {
  const { errors } = await openWarehouse(page, context), previous = (await state(page)).replay.runId;
  await page.locator('input[type=file]').setInputFiles({ name: 'unsupported-run.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ schema_version: '1.0', layout_version: 'qoyma-20x18-v1' })) });
  await expect(page.getByRole('alert')).toContainText('Unsupported Run/layout version');
  expect((await state(page)).replay.runId).toBe(previous);
  expect((await state(page)).renderedRegistry.rack).toHaveLength(288);
  await expect(page.locator('canvas')).toHaveCount(1);
  await page.getByRole('button', { name: 'Визуальное демо', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect((await state(page)).replay.time).toBe(0); expect(errors).toEqual([]);
});

test('follow order changes tote to parcel to pallet, pans on seek and clears after dispatch', async ({ page, context }) => {
  const { errors } = await openWarehouse(page, context);
  const stages = await page.evaluate(() => {
    const run = (window as any).__QOIMA_VIEWER__.replay.getRun();
    const packed = run.events.find((event: any) => event.kind === 'order_packed');
    const scanned = run.events.find((event: any) => event.kind === 'parcel_scanned');
    const dispatched = run.events.find((event: any) => event.kind === 'order_dispatched');
    return { orderId: packed.payload.order_id, packed: packed.at_s, parcelId: packed.payload.parcel_id,
      scanned: scanned.at_s, palletId: scanned.payload.pallet_id, dispatched: dispatched.at_s };
  });
  await page.getByRole('button', { name: /^Следовать заказу/ }).click();
  await expect.poll(async () => (await state(page)).following).toBe('T001');
  expect((await state(page)).followingOrder).toBe(stages.orderId);
  const first = await state(page);
  const direction = first.camera.map((value: number, axis: number) => value - first.target[axis]);
  const magnitude = Math.hypot(...direction);
  for (const [time, id] of [[stages.packed + .5, stages.parcelId], [stages.scanned + .5, stages.palletId]] as [number, string][]) {
    await seekThroughUI(page, time);
    await expect.poll(async () => (await state(page)).following).toBe(id);
    const current = await state(page);
    expect(current.selected).toBe(id);
    const actual = await page.evaluate(id => (window as any).__QOIMA_VIEWER__.inspectEntity(id), id);
    expect(actual).toBeTruthy();
    expect(Math.hypot(...current.target.map((value: number, axis: number) => value - actual.rootWorld[axis]))).toBeLessThan(2);
    const after = current.camera.map((value: number, axis: number) => value - current.target[axis]);
    const cosine = after.reduce((sum: number, value: number, axis: number) => sum + value * direction[axis], 0) / (Math.hypot(...after) * magnitude);
    expect(cosine).toBeGreaterThan(.999);
  }
  await seekThroughUI(page, stages.dispatched + .5);
  await expect.poll(async () => (await state(page)).followingOrder).toBe('');
  expect((await state(page)).following).toBe('');
  expect((await state(page)).selected).toBe('');
  await expect(page.locator('.selection-tag')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/v2-runtime/follow-order-dispatched.png' });
  expect(errors).toEqual([]);
});

test('actual WebAudio unlocks through UI, emits a cue and stops on pause, seek, reset and mute', async ({ page, context }) => {
  // The real AudioContext graph runs; Chromium --mute-audio suppresses all
  // speaker output. No sound is played audibly and no audio API is mocked.
  const { errors } = await openWarehouse(page, context);
  expect((await state(page)).audio).toMatchObject({ muted: true, unlocked: false, voices: 0 });
  await page.getByRole('button', { name: 'Включить звук', exact: true }).click();
  await expect.poll(async () => (await state(page)).audio.unlocked).toBe(true);
  expect((await state(page)).audio.muted).toBe(false);
  const pickedAt = await page.evaluate(() => (window as any).__QOIMA_VIEWER__.replay.getRun().events.find((event: any) => event.kind === 'sku_picked').at_s);
  await seekThroughUI(page, 8.8);
  await page.getByRole('button', { name: 'Воспроизвести', exact: true }).click();
  await expect.poll(async () => (await state(page)).replay.time).toBeGreaterThan(pickedAt + .05);
  await expect.poll(async () => (await state(page)).audio.cues).toBeGreaterThan(0);
  expect((await state(page)).audio.voices).toBeLessThanOrEqual(4);
  await page.getByRole('button', { name: 'Пауза', exact: true }).click();
  expect((await state(page)).audio.voices).toBe(0);
  // The belt's actual oscillator is sustained, making cleanup checks immune
  // to a short one-shot cue ending between browser protocol messages.
  await seekThroughUI(page, 34);
  await page.getByRole('button', { name: 'Воспроизвести', exact: true }).click();
  await expect.poll(async () => (await state(page)).audio.voices).toBeGreaterThan(0);
  expect((await state(page)).audio.voices).toBeLessThanOrEqual(4);
  const onSeek = await page.getByRole('slider', { name: 'Время воспроизведения' }).evaluate(input => {
    (input as HTMLInputElement).value = '43'; input.dispatchEvent(new Event('input', { bubbles: true }));
    return (window as any).__QOIMA_VIEWER__.getState().audio;
  });
  expect(onSeek.voices).toBe(0);
  await page.getByRole('button', { name: 'Пауза', exact: true }).click();
  await seekThroughUI(page, 34);
  await page.getByRole('button', { name: 'Воспроизвести', exact: true }).click();
  await expect.poll(async () => (await state(page)).audio.voices).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Сбросить время' }).click();
  expect((await state(page)).audio.voices).toBe(0);
  expect((await state(page)).replay).toMatchObject({ time: 0, playing: false });
  await page.getByRole('button', { name: 'Выключить звук', exact: true }).click();
  expect((await state(page)).audio).toMatchObject({ muted: true, unlocked: true, voices: 0 });
  expect(errors).toEqual([]);
});

test('v2 GLB calibration preserves metre axes, actual heights and three bin anchors', async ({ page }) => {
  await page.goto(baseURL + '/?calibration=v2');
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'ready', { timeout: 30_000 });
  const diagnostics = await page.evaluate(() => (window as any).__QOIMA_CALIBRATION_V2__);
  expect(diagnostics).toMatchObject({ webgl: true, localGlb: true, layoutVersion: 'qoima-72x48-v2' });
  const vector = (actual: number[], expected: number[]) => actual.forEach((value, axis) => expect(value).toBeCloseTo(expected[axis], 4));
  vector(diagnostics.positions.calibration_axis_end__X, [1, 0, 0]);
  vector(diagnostics.positions.calibration_axis_end__Y, [0, 1, 0]);
  vector(diagnostics.positions.calibration_axis_end__Z, [0, 0, 1]);
  expect(diagnostics.sizes['standing-worker'][1]).toBeCloseTo(1.7, 4);
  expect(diagnostics.sizes['rack-high'][1]).toBeCloseTo(5.4, 4);
  expect(diagnostics.sizes['conveyor-high'][1]).toBeCloseTo(.95, 4);
  vector(diagnostics.positions.calibration_anchor__belt_top, [6, .9, 0]);
  for (const [index, height] of [.45, 2.25, 4.05].entries()) vector(diagnostics.positions['calibration_anchor__rack_bin_0' + (index + 1)], [4, height, 0]);
  await expect(page.locator('canvas')).toHaveCount(1);
  await page.screenshot({ path: 'test-results/v2-runtime/calibration-v2.png' });
});
