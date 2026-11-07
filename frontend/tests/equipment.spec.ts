import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

const baseURL = (process.env.QOIMA_TEST_BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const assetIds = [
  'standing-worker', 'picker-worker', 'driver', 'picking-cart', 'rack-high',
  'conveyor-high', 'conveyor-corner', 'conveyor-diverter', 'order-tote', 'sealed-parcel',
  'packing-station', 'forklift', 'dock', 'crate', 'pallet', 'buffer-pallet',
  'environment-shell', 'rack-low', 'worker-low', 'conveyor-low', 'tote-low',
];
test.use({ launchOptions: { args: ['--mute-audio'] } });

async function openWarehouse(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(baseURL);
  await expect(page.locator('main')).toHaveAttribute('data-phase', 'ready', { timeout: 45_000 });
  await page.waitForFunction(() => (window as any).__QOIMA_VIEWER__?.getPerfState().calls > 0);
  return errors;
}
async function renderFrames(page: Page, count = 3) {
  await page.evaluate(async count => {
    for (let i = 0; i < count; i++) await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
  }, count);
}
const distance = (a: number[], b: number[]) => Math.hypot(...a.map((value, axis) => value - b[axis]));

test('all 21 exported GLBs are selected through UI and captured in four actual browser views', async ({ page, request }, testInfo) => {
  test.setTimeout(300_000);
  const errors = await openWarehouse(page);
  const actualIds = await page.locator('[data-asset]').evaluateAll(buttons => buttons.map(button => button.getAttribute('data-asset')));
  expect(actualIds.slice().sort()).toEqual(assetIds.slice().sort());
  const metrics: unknown[] = [];
  let runtimeBytes = 0;
  for (const id of assetIds) {
    const response = await request.get(baseURL + '/models/v2/' + id + '.glb');
    expect(response.ok(), id + ' local GLB').toBe(true);
    runtimeBytes += (await response.body()).byteLength;
    await page.locator(`[data-asset="${id}"]`).click();
    await expect.poll(() => page.evaluate(() => (window as any).__QOIMA_VIEWER__.getState().mode)).toBe(id);
    await expect(page.locator('canvas')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Воспроизвести', exact: true })).toBeDisabled();
    for (const [view, label] of Object.entries({ front: 'Спереди', side: 'Сбоку', rear: 'Сзади', quarter: 'Объём' })) {
      await page.getByRole('navigation', { name: 'Ракурсы модели' }).getByRole('button', { name: label, exact: true }).click();
      await renderFrames(page);
      const current = await page.evaluate(() => (window as any).__QOIMA_VIEWER__.getPerfState());
      expect(current.calls, id + ':' + view).toBeGreaterThan(0);
      expect(current.triangles, id + ':' + view).toBeGreaterThan(0);
      expect(current.replay.playing).toBe(false);
      if(id==='sealed-parcel'&&view==='quarter')expect(await page.evaluate(()=>(window as any).__QOIMA_VIEWER__.getState().distance)).toBeLessThan(2);
      await page.screenshot({ path: `test-results/v2-runtime/${id}/${view}.png` });
      metrics.push({ assetId: id, view, ...current });
    }
  }
  expect(runtimeBytes).toBeLessThanOrEqual(10_000_000);
  await testInfo.attach('stand-render-metrics.json', { body: JSON.stringify({ runtimeBytes, views: metrics }), contentType: 'application/json' });
  await page.getByRole('button', { name: 'Весь склад', exact: false }).click();
  await expect.poll(() => page.evaluate(() => (window as any).__QOIMA_VIEWER__.getState().mode)).toBe('overview');
  await expect(page.locator('canvas')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('actual posed driver, forklift and carried pallet anchors stay connected through travel and turns', async ({ page }) => {
  const errors = await openWarehouse(page);
  const cases = await page.evaluate(() => {
    const run = (window as any).__QOIMA_VIEWER__.replay.getRun();
    const loading = run.actions.find((action: any) => action.actor_id === 'F02' && action.operation === 'loading');
    const unloading = run.actions.find((action: any) => action.actor_id === 'F02' && action.operation === 'unloading');
    return run.actions.filter((action: any) => action.actor_id === 'F02' && action.start_s >= loading.end_s && action.end_s <= unloading.start_s)
      .map((action: any) => ({ time: (action.start_s + action.end_s) / 2, palletId: loading.entity_id, operation: action.operation }));
  });
  expect(cases.length).toBeGreaterThanOrEqual(3);
  const snapshots: any[] = [];
  for (const sample of cases) {
    await page.evaluate(({ time }) => {
      const viewer = (window as any).__QOIMA_VIEWER__;
      viewer.replay.pause(); viewer.replay.seek(time); viewer.selectActor('F02');
    }, sample);
    await renderFrames(page);
    const current = await page.evaluate(({ palletId }) => {
      const viewer = (window as any).__QOIMA_VIEWER__, frame = viewer.replay.getFrame();
      const parcel = Object.values(frame.cargo).find((cargo: any) => cargo.visible && cargo.attachment.kind === 'cargo' && cargo.attachment.id === palletId) as any;
      return {
        state: viewer.getState(), driver: viewer.inspectRig('F02'), vehicle: viewer.inspectRig('FL02'),
        pallet: viewer.inspectEntity(palletId), parcel: parcel && viewer.inspectEntity(parcel.id),
        frameDriver: frame.actors.F02, framePallet: frame.cargo[palletId],
      };
    }, sample);
    expect(current.state.motion.heroIds).toEqual(expect.arrayContaining(['FL02', 'F02']));
    expect(current.driver).toBeTruthy(); expect(current.vehicle).toBeTruthy(); expect(current.pallet).toBeTruthy();
    expect(distance(current.driver.rootWorld, current.vehicle.nodes.anchor_driver_seat)).toBeLessThan(.002);
    expect(distance(current.pallet.rootWorld, current.vehicle.nodes.anchor_pallet)).toBeLessThan(.002);
    expect(current.pallet.rootWorld[1]).toBeGreaterThanOrEqual(0);
    expect(current.framePallet.attachment).toMatchObject({ kind: 'vehicle', id: 'FL02' });
    expect(current.frameDriver.pose.lift).toBeGreaterThan(.071);
    for (const [side, suffix] of [['left', 'L'], ['right', 'R']]) {
      expect(distance(current.driver.nodes['hand_' + suffix], current.vehicle.nodes['anchor_hand_' + side])).toBeLessThan(.07);
    }
    if (current.parcel) expect(distance(current.parcel.rootWorld, current.vehicle.nodes.anchor_cargo)).toBeLessThan(.002);
    expect(new Set(current.state.motion.cargo).size).toBe(current.state.motion.cargo.length);
    snapshots.push({ time: sample.time, pallet: current.pallet.rootWorld, seat: current.driver.rootWorld });
  }
  await page.screenshot({ path: 'test-results/v2-runtime/forklift-carry-contact.png' });
  await page.evaluate(time => {
    const viewer = (window as any).__QOIMA_VIEWER__;
    viewer.replay.seek(0); viewer.replay.seek(time); viewer.selectActor('F02');
  }, cases[0].time);
  await renderFrames(page);
  const repeated = await page.evaluate(id => (window as any).__QOIMA_VIEWER__.inspectEntity(id).rootWorld, cases[0].palletId);
  expect(distance(repeated, snapshots[0].pallet)).toBeLessThan(.002);
  expect(errors).toEqual([]);
});

async function loadFinalGLB(request: APIRequestContext, id: string) {
  const response = await request.get(baseURL + '/models/v2/' + id + '.glb');
  expect(response.ok(), id).toBe(true);
  const bytes = await response.body();
  const scene = (await new GLTFLoader().parseAsync(new Uint8Array(bytes).buffer, '')).scene;
  scene.updateMatrixWorld(true);
  return scene;
}
function worldBounds(scene: THREE.Object3D) {
  const result = new THREE.Box3();
  const point = new THREE.Vector3();
  scene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const positions = object.geometry.getAttribute('position');
    for (let index = 0; index < positions.count; index++) result.expandByPoint(point.fromBufferAttribute(positions, index).applyMatrix4(object.matrixWorld));
  });
  return result;
}

test('the tote clears cart walls and picked unit packs stay inside its actual cavity',async({page,request})=>{
  const tote=await loadFinalGLB(request,'order-tote'),cart=await loadFinalGLB(request,'picking-cart'),crate=await loadFinalGLB(request,'crate');
  const outer=worldBounds(tote);const half=outer.getSize(new THREE.Vector3()).multiplyScalar(.5);
  // Probe the real cart wall triangles through the tote's occupied height.
  for(const y of [.60,.70,.82])for(const z of [-.18,0,.18])for(const sign of [-1,1]){
    const ray=new THREE.Raycaster(new THREE.Vector3(0,y,z),new THREE.Vector3(sign,0,0));
    const hit=ray.intersectObject(cart,true)[0];if(hit)expect(hit.distance).toBeGreaterThan(half.x+.001);
  }
  const errors=await openWarehouse(page);
  await page.evaluate(()=>{const v=(window as any).__QOIMA_VIEWER__;v.replay.seek(40);});await renderFrames(page);
  const contents=await page.evaluate(()=>{
    const v=(window as any).__QOIMA_VIEWER__;const frame=v.replay.getFrame();
    return{tote:frame.cargo.T001,items:v.replay.getRun().events.filter((event:any)=>event.kind==='sku_picked'&&event.at_s<=40).map((event:any)=>v.inspectEntity('T001:'+event.seq))};
  });
  expect(contents.items).toHaveLength(2);
  const inverse=new THREE.Matrix4().compose(new THREE.Vector3().fromArray(contents.tote.pos),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),contents.tote.yaw),new THREE.Vector3(1,1,1)).invert();
  for(const item of contents.items){
    expect(item).toBeTruthy();const bounds=worldBounds(crate).applyMatrix4(new THREE.Matrix4().fromArray(item.matrixWorld).premultiply(inverse));
    expect(bounds.min.x).toBeGreaterThan(outer.min.x+.025);expect(bounds.max.x).toBeLessThan(outer.max.x-.025);
    expect(bounds.min.z).toBeGreaterThan(outer.min.z+.025);expect(bounds.max.z).toBeLessThan(outer.max.z-.025);
    expect(bounds.min.y).toBeGreaterThan(.02);expect(bounds.max.y).toBeLessThan(outer.max.y-.02);
  }
  expect(errors).toEqual([]);
});

test('final GLB fork surfaces physically fit the empty pallet and cargo origins remain canonical', async ({ request }) => {
  const forklift = await loadFinalGLB(request, 'forklift'), pallet = await loadFinalGLB(request, 'pallet');
  for (const name of ['pivot_carriage', 'pivot_steering_wheel', 'anchor_driver_seat', 'anchor_pallet', 'anchor_cargo',
    'pivot_wheel_front_left_spin', 'pivot_wheel_front_right_spin', 'pivot_wheel_rear_left_spin', 'pivot_wheel_rear_right_spin',
    'pivot_wheel_rear_left_steer', 'pivot_wheel_rear_right_steer']) expect(forklift.getObjectByName(name), name).toBeTruthy();
  const support: number[] = [], point = new THREE.Vector3();
  forklift.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const positions = object.geometry.getAttribute('position');
    for (let index = 0; index < positions.count; index++) {
      point.fromBufferAttribute(positions, index).applyMatrix4(object.matrixWorld);
      if (point.z > .48 && point.z < 1.2 && point.y < .1 && Math.abs(Math.abs(point.x) - .225) < .06) support.push(point.y);
    }
  });
  expect(support.length).toBeGreaterThan(0);
  const forkTop = Math.max(...support);
  expect(forkTop).toBeCloseTo(.045, 4);
  const ray = new THREE.Raycaster(new THREE.Vector3(.225, 0, .186), new THREE.Vector3(0, 1, 0));
  const underside = ray.intersectObject(pallet, true)[0];
  expect(underside).toBeTruthy();
  expect(underside.point.y).toBeCloseTo(.116, 4);
  const palletAnchor = forklift.getObjectByName('anchor_pallet')!.getWorldPosition(new THREE.Vector3());
  expect(underside.point.y - forkTop).toBeCloseTo(-palletAnchor.y, 4);
  const palletBounds = worldBounds(pallet), palletSize = palletBounds.getSize(new THREE.Vector3());
  expect(palletBounds.min.y).toBeCloseTo(0, 5);
  for (const [axis, expected] of [1.4, .14, 1].entries()) expect(palletSize.getComponent(axis)).toBeCloseTo(expected, 4);
  const crate = worldBounds(await loadFinalGLB(request, 'crate'));
  expect(crate.getCenter(new THREE.Vector3()).length()).toBeLessThan(.0001);
  const parcel = worldBounds(await loadFinalGLB(request, 'sealed-parcel'));
  expect(parcel.min.y).toBeCloseTo(0, 5); expect(parcel.max.y).toBeCloseTo(.32, 4);
  const packing = await loadFinalGLB(request, 'packing-station');
  for (const name of ['pivot_scanner', 'pivot_packing_carton', 'pivot_carton_flap_front', 'pivot_carton_flap_rear',
    'pivot_carton_flap_left', 'pivot_carton_flap_right', 'anchor_input_tote', 'anchor_output_parcel', 'anchor_scanner_lens']) {
    expect(packing.getObjectByName(name), name).toBeTruthy();
  }
  const supportBelow = (position: THREE.Vector3) => {
    // A port may lie on an exact outer edge while its material-batched mesh
    // contains float32 local coordinates. Probe at most 0.1mm around the point
    // to avoid classifying round-off at that edge as a missing support surface.
    const heights = [[0, 0], [.0001, 0], [-.0001, 0], [0, .0001], [0, -.0001]].map(([dx, dz]) => {
      const ray = new THREE.Raycaster(new THREE.Vector3(position.x + dx, 3, position.z + dz), new THREE.Vector3(0, -1, 0));
      return ray.intersectObject(packing, true)[0]?.point.y;
    }).filter((height): height is number => height !== undefined);
    return heights.length ? Math.max(...heights) : undefined;
  };
  for (const name of ['input_branch', 'input_cross', 'input_turn', 'input_table', 'output_table', 'output_turn', 'output_cross', 'output_outfeed']) {
    const anchor = packing.getObjectByName('anchor_transfer_' + name);
    expect(anchor, name).toBeTruthy();
    const position = anchor!.getWorldPosition(new THREE.Vector3()), supportY = supportBelow(position);
    expect(supportY, name + ' has a physical counter below the cargo').toBeDefined();
    // Rollers stand 18mm above the structural deck, so a ray between them sees
    // that deck. Both are inside the project's 20mm anchor-fit tolerance.
    expect(Math.abs(position.y - supportY!)).toBeLessThanOrEqual(.0201);
  }
  for (const z of [.29, .1, -.1, -.3, -.5]) {
    expect(supportBelow(new THREE.Vector3(.72, .85, z)), 'clear output lane at ' + z).toBeLessThanOrEqual(.8701);
  }
  for (const z of [.23, .1, .05]) {
    expect(supportBelow(new THREE.Vector3(-.72, .85, z)), 'clear input table at ' + z).toBeLessThanOrEqual(.8701);
  }
});
