import { expect, test } from '@playwright/test';

test('local production build renders Blender GLB with canonical axes and units', async ({ page, context }) => {
  const errors: string[] = [];
  const remote: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => {
    if (!request.url().startsWith('http://127.0.0.1:4173/') && !request.url().startsWith('data:')) remote.push(request.url());
  });
  await context.route('**/*', (route) => route.request().url().startsWith('http://127.0.0.1:4173/') ? route.continue() : route.abort());
  await page.goto('http://127.0.0.1:4173/?calibration=1');
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'ready');
  await expect(page.locator('canvas')).toHaveCount(1);
  const diagnostics = JSON.parse(await page.locator('#diagnostics').textContent() || '{}');
  expect(diagnostics.webgl).toBe(true);
  expect(diagnostics.localGlb).toBe(true);
  expect(diagnostics.unitCubeSize).toEqual([1, 1, 1]);
  diagnostics.positions.anchor_box__S_A1_B1.forEach((value: number, index: number) => {
    expect(value).toBeCloseTo([1.5, 0.9, 4][index], 6);
  });
  await page.setViewportSize({ width: 720, height: 600 });
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'ready');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/environment.png' });
  expect(errors).toEqual([]);
  expect(remote).toEqual([]);
});

test('missing GLB displays an error instead of an empty successful scene', async ({ page }) => {
  await page.route('**/models/calibration.glb', (route) => route.fulfill({ status: 404, body: 'missing' }));
  await page.goto('http://127.0.0.1:4173/?calibration=1');
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'error');
  await expect(page.getByRole('status')).not.toBeEmpty();
});
