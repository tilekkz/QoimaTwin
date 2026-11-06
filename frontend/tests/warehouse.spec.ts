import { expect, test } from '@playwright/test';

test('warehouse overview, all assets, zoom and local reference gallery', async ({page,context})=>{
  const errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await context.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:4173/')?route.continue():route.abort());
  await page.goto('http://127.0.0.1:4173/');
  await expect(page.locator('main')).toHaveAttribute('data-phase','ready');
  const state=()=>page.evaluate(()=>(window as any).__QOIMA_VIEWER__.getState());
  await expect.poll(async()=>(await state()).calls).toBeGreaterThan(0);
  expect((await state()).slotCount).toBe(20);
  expect((await state()).calls).toBeLessThan(150);
  await page.screenshot({path:'test-results/warehouse-overview.png'});
  const initial=(await state()).distance;
  await page.locator('canvas').hover();
  await page.mouse.wheel(0,-300);
  await expect.poll(async()=>(await state()).distance).toBeLessThan(initial);
  await page.getByRole('button',{name:'Детали',exact:false}).click();
  await expect(page.locator('.selection-tag')).toContainText('S_A1_B1');
  await page.screenshot({path:'test-results/warehouse-detail.png'});
  for(const id of ['rack-bay','crate','picker-cart','packing-station','buffer-pallet','forklift','ibc-tote','environment']){
    await page.locator(`[data-asset="${id}"]`).click();
    await expect.poll(async()=>(await state()).mode).toBe(id);
    await expect(page.locator('canvas')).toHaveCount(1);
    await page.screenshot({path:`test-results/asset-${id}.png`});
  }
  await page.getByRole('button',{name:'Референсы',exact:false}).click();
  await expect(page.locator('.gallery-grid figure')).toHaveCount(8);
  await expect.poll(()=>page.locator('.gallery-grid img').evaluateAll(imgs=>imgs.filter(img=>(img as HTMLImageElement).complete&&(img as HTMLImageElement).naturalWidth>0).length)).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Закрыть референсы'}).click();
  await page.getByRole('button',{name:'Обзор',exact:false}).first().click();
  await page.getByRole('button',{name:'Сверху',exact:false}).click();
  await page.screenshot({path:'test-results/warehouse-top.png'});
  await page.setViewportSize({width:720,height:600});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
