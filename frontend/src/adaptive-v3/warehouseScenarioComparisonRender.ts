import * as THREE from 'three';

export type WarehouseScenarioComparisonVariant = 'A' | 'B';
export type WarehouseScenarioComparisonRenderOptions = {
  comparison: boolean;
  variant: WarehouseScenarioComparisonVariant;
  /** Apply the already sampled absolute time. This must not advance a clock. */
  applyVariant: (variant: WarehouseScenarioComparisonVariant) => void;
};
export type WarehouseScenarioComparisonPane = Readonly<{
  variant: WarehouseScenarioComparisonVariant;
  /** Renderer logical pixels, with the WebGL bottom-left origin. */
  viewport: readonly [number, number, number, number];
  aspect: number;
}>;

const drawing = new WeakSet<object>();
function requireValue(value: unknown, reason: string): asserts value {
  if (!value) throw Error(reason);
}
/** Same matrixAutoUpdate rules as Object3D.updateWorldMatrix, evaluated privately.
 * A page renderPass runs before WebGLRenderer updates a newly framed camera. */
function currentWorldMatrix(node: THREE.Object3D): THREE.Matrix4 {
  const chain: THREE.Object3D[] = [];
  for (let current: THREE.Object3D | null = node; current; current = current.parent) chain.unshift(current);
  const world = new THREE.Matrix4(), local = new THREE.Matrix4();
  for (const current of chain) {
    if (!current.matrixWorldAutoUpdate) world.copy(current.matrixWorld);
    else world.multiply(current.matrixAutoUpdate ?
      local.compose(current.position, current.quaternion, current.scale) : current.matrix);
  }
  return world;
}

/** Two native passes over one logical warehouse, following Twin's shared-camera
 * and restore-after-each-frame rule. No assets or logical populations are copied.
 * The caller owns time, plan admission, labels and the applyVariant controller.
 */
export function renderWarehouseScenarioComparison(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.OrthographicCamera,
  options: WarehouseScenarioComparisonRenderOptions,
): Readonly<{panes: readonly WarehouseScenarioComparisonPane[]}> {
  requireValue(options && typeof options.comparison === 'boolean' &&
    ['A', 'B'].includes(options.variant) && typeof options.applyVariant === 'function',
  'INVALID_SCENARIO_COMPARISON_OPTIONS');
  requireValue(camera.isOrthographicCamera === true &&
    camera.projectionMatrix.elements.every(Number.isFinite) &&
    camera.matrixWorld.elements.every(Number.isFinite), 'ORTHOGRAPHIC_SCENARIO_CAMERA_REQUIRED');
  const projection = camera.projectionMatrix.clone(), inverse = camera.projectionMatrixInverse.clone();
  const world = currentWorldMatrix(camera);
  requireValue(world.elements.every(Number.isFinite) && Math.abs(world.determinant()) > 1e-12,
    'FINITE_INVERTIBLE_SCENARIO_CAMERA_REQUIRED');
  const e = projection.elements;
  requireValue(e[0] > 0 && e[5] > 0 && e[3] === 0 && e[7] === 0 &&
    e[11] === 0 && e[15] === 1, 'STANDARD_ORTHOGRAPHIC_PROJECTION_REQUIRED');
  requireValue(![renderer, scene, camera].some(item => drawing.has(item)),
    'SCENARIO_COMPARISON_RENDER_REENTRANT');
  const viewport = renderer.getViewport(new THREE.Vector4()), scissor = renderer.getScissor(new THREE.Vector4());
  requireValue(viewport.toArray().every(Number.isFinite) && viewport.z > 0 &&
    viewport.w >= (options.comparison ? 2 : Number.MIN_VALUE), 'INVALID_SCENARIO_COMPARISON_VIEWPORT');
  const scissorTest = renderer.getScissorTest(), autoClear = renderer.autoClear;
  const clearFlags = [renderer.autoClearColor, renderer.autoClearDepth, renderer.autoClearStencil] as const;
  const target = renderer.getRenderTarget();
  const projectionFields = {
    left: camera.left, right: camera.right, top: camera.top, bottom: camera.bottom,
    near: camera.near, far: camera.far, zoom: camera.zoom, view: camera.view,
  };
  const viewFields = camera.view ? {...camera.view} : null;
  const paneHeight = Math.floor(viewport.w / 2);
  // An odd-height viewport leaves one clear pixel between equal-aspect panes.
  const rects = options.comparison ? [
    {variant: 'A' as const, viewport: [viewport.x, viewport.y + viewport.w - paneHeight, viewport.z, paneHeight] as const},
    {variant: 'B' as const, viewport: [viewport.x, viewport.y, viewport.z, paneHeight] as const},
  ] : [{variant: options.variant, viewport: viewport.toArray() as [number, number, number, number]}];
  const panes = rects.map(pane => Object.freeze({...pane,
    viewport: Object.freeze([...pane.viewport]) as readonly [number, number, number, number],
    aspect: pane.viewport[2] / pane.viewport[3],
  }));
  const cameras = panes.map(pane => {
    const copy = camera.clone(false);
    // The source camera may have a parent: use its exact world transform as the
    // standalone pass camera, without changing the source camera or its target.
    copy.matrixAutoUpdate = false;
    copy.matrixWorldAutoUpdate = false;
    copy.matrix.copy(world);
    copy.matrixWorld.copy(world);
    copy.matrixWorldInverse.copy(world).invert();
    copy.matrixWorld.decompose(copy.position, copy.quaternion, copy.scale);
    if (options.comparison) {
      // Keep horizontal projection and world centre exactly. Only the vertical
      // extent changes to the pane aspect; near/far depth mapping stays exact.
      const centreY = -e[13] / e[5], verticalScale = e[0] * pane.aspect;
      copy.projectionMatrix.copy(projection);
      copy.projectionMatrix.elements[5] = verticalScale;
      copy.projectionMatrix.elements[13] = -centreY * verticalScale;
      copy.projectionMatrixInverse.copy(copy.projectionMatrix).invert();
      copy.view = null;
      copy.zoom = 1;
      copy.left = (-1 - e[12]) / e[0];
      copy.right = (1 - e[12]) / e[0];
      copy.bottom = centreY - 1 / verticalScale;
      copy.top = centreY + 1 / verticalScale;
    }
    return copy;
  });
  const errors: unknown[] = [];
  for (const item of [renderer, scene, camera]) drawing.add(item);
  try {
    renderer.autoClear = false;
    renderer.setScissorTest(true);
    renderer.setScissor(viewport);
    renderer.clear(true, true, true);
    for (let i = 0; i < panes.length; i++) {
      options.applyVariant(panes[i].variant);
      renderer.setViewport(...panes[i].viewport);
      renderer.setScissor(...panes[i].viewport);
      renderer.render(scene, cameras[i]);
    }
  } catch (error) { errors.push(error); }
  finally {
    const restore = (action: () => void) => { try { action(); } catch (error) { errors.push(error); } };
    // Keep the guard during restoration: a native apply may request another draw.
    restore(() => options.applyVariant(options.variant));
    restore(() => {
      Object.assign(camera, projectionFields);
      if (camera.view && viewFields) Object.assign(camera.view, viewFields);
      camera.projectionMatrix.copy(projection);
      camera.projectionMatrixInverse.copy(inverse);
    });
    restore(() => renderer.setRenderTarget(target));
    restore(() => renderer.setViewport(viewport));
    restore(() => renderer.setScissor(scissor));
    restore(() => renderer.setScissorTest(scissorTest));
    restore(() => {
      renderer.autoClear = autoClear;
      [renderer.autoClearColor, renderer.autoClearDepth, renderer.autoClearStencil] = clearFlags;
    });
    for (const item of [renderer, scene, camera]) drawing.delete(item);
  }
  if (errors.length === 1) throw errors[0];
  if (errors.length > 1) throw new AggregateError(errors, 'SCENARIO_COMPARISON_RENDER_OR_RESTORE_FAILED');
  return Object.freeze({panes: Object.freeze(panes)});
}
