import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { layout } from '../contracts';

export const assetCatalog = [
  { id: 'rack-bay', label: 'Стеллаж', note: 'Стойки, укосины и три уровня', reference: 'rack-bay-reference.png' },
  { id: 'crate', label: 'Коробка', note: 'Складки, лента и этикетка', reference: 'crate-reference.png' },
  { id: 'picker-cart', label: 'Комплектовщик', note: 'Персонаж и тележка', reference: 'picker-cart-reference.png' },
  { id: 'packing-station', label: 'Упаковочный пост', note: 'Стол, сканер, принтер и упаковка', reference: 'packing-station-reference.png' },
  { id: 'buffer-pallet', label: 'Буфер', note: 'Низкая платформа для переносов', reference: 'buffer-pallet.png' },
  { id: 'forklift', label: 'Погрузчик', note: 'Деталь окружения', reference: 'forklift.png' },
  { id: 'ibc-tote', label: 'IBC-контейнер', note: 'Бак, клетка, поддон и клапан', reference: 'ibc-tote.png' },
  { id: 'environment', label: 'Окружение', note: 'Каркас, окна и инженерные детали', reference: 'environment.png' },
] as const;
export type AssetId = typeof assetCatalog[number]['id'];
export type ViewId = AssetId | 'overview';
export type SceneStatus = { mode: ViewId; calls: number; triangles: number; slotCount: number; selected: string; ready: boolean };

export async function mountWarehouse(host: HTMLElement, onStatus: (state: SceneStatus) => void) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power', preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.3;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#e9e7e0');
  const camera = new THREE.PerspectiveCamera(38, 1, .015, 180);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .1;
  controls.minDistance = .4;
  controls.maxDistance = 85;
  controls.maxPolarAngle = Math.PI / 2 - .025;
  controls.screenSpacePanning = true;
  scene.add(new THREE.HemisphereLight(0xfff5dd, 0x71828a, 1.4));
  const key = new THREE.DirectionalLight(0xfff1d2, 2.7);
  key.position.set(-8, 24, -8);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = key.shadow.camera.bottom = -23;
  key.shadow.camera.right = key.shadow.camera.top = 23;
  key.shadow.camera.far = 80;
  key.shadow.bias = -.0003;
  key.shadow.normalBias = .025;
  const fill = new THREE.DirectionalLight(0xc8e4f0, .9);
  fill.position.set(20, 14, 18);
  scene.add(key, key.target, fill);
  const loader = new GLTFLoader();
  const templates = new Map<string, THREE.Group>();
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  let current = new THREE.Group();
  let mode: ViewId = 'overview';
  let selected = '';
  let disposed = false;
  let raf = 0;
  let tick = 0;
  const proxies: THREE.Mesh[] = [];
  const highlight = new THREE.Box3Helper(new THREE.Box3(), 0xc98a22);
  highlight.visible = false;
  scene.add(highlight);
  const proxyGeometry = new THREE.BoxGeometry(.96, 2.65, 1.56);
  geometries.add(proxyGeometry);
  const proxyMaterial = new THREE.MeshBasicMaterial();
  materials.add(proxyMaterial);

  const stats = (): SceneStatus => ({ mode, calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, slotCount: mode === 'overview' ? layout.slots.length : 0, selected, ready: true });
  const fit = (bounds: THREE.Box3, direction = new THREE.Vector3(1.12, 1.25, -1.6)) => {
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    direction.normalize();
    const rotation = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().lookAt(direction, new THREE.Vector3(), camera.up)).invert();
    const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov)/2);
    let distance = sphere.radius;
    for (const x of [bounds.min.x,bounds.max.x]) for (const y of [bounds.min.y,bounds.max.y]) for (const z of [bounds.min.z,bounds.max.z]) {
      const point = new THREE.Vector3(x,y,z).sub(sphere.center).applyQuaternion(rotation);
      distance = Math.max(distance,point.z+Math.abs(point.y)/(tangent*.86),point.z+Math.abs(point.x)/(tangent*camera.aspect*.88));
    }
    controls.target.copy(sphere.center);
    camera.position.copy(sphere.center).addScaledVector(direction, distance*1.04);
    controls.minDistance = Math.max(.25, sphere.radius * .08);
    controls.update();
  };
  const freeCurrent = () => {
    scene.remove(current);
    current.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.userData.ownedGeometry) { obj.geometry.dispose(); geometries.delete(obj.geometry); }
    });
  };
  const clone = (id: string, position: number[] = [0, 0, 0], name = id, rotation = 0) => {
    const object = templates.get(id)!.clone(true);
    object.name = name;
    object.position.fromArray(position);
    object.rotation.y = rotation;
    object.updateMatrixWorld(true);
    return object;
  };
  const batch = (group: THREE.Group) => {
    group.updateMatrixWorld(true);
    const buckets = new Map<string, { material: THREE.Material; geometry: THREE.BufferGeometry[] }>();
    group.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh) || Array.isArray(obj.material)) return;
      const mat = obj.material as THREE.MeshStandardMaterial;
      const signature = [mat.color?.getHex(), mat.roughness, mat.metalness, mat.emissive?.getHex(), mat.emissiveIntensity].join(':');
      const bucket = buckets.get(signature) || { material: mat, geometry: [] };
      const geometry = obj.geometry.clone().applyMatrix4(obj.matrixWorld);
      bucket.geometry.push(geometry);
      buckets.set(signature, bucket);
    });
    const result = new THREE.Group();
    for (const value of buckets.values()) {
      const geometry = mergeGeometries(value.geometry, false);
      value.geometry.forEach((entry) => entry.dispose());
      if (!geometry) throw new Error('Не удалось объединить геометрию сцены');
      const mesh = new THREE.Mesh(geometry, value.material);
      mesh.castShadow = mesh.receiveShadow = true;
      mesh.userData.ownedGeometry = true;
      geometries.add(geometry);
      result.add(mesh);
    }
    return result;
  };
  const setMode = (next: ViewId) => {
    freeCurrent();
    mode = next;
    selected = '';
    highlight.visible = false;
    proxies.length = 0;
    const group = new THREE.Group();
    if (next === 'overview') {
      group.add(clone('environment'));
      for (const slot of layout.slots) {
        group.add(clone('rack-bay', [slot.rack_center[0], 0, slot.rack_center[2]], `rackbay__${slot.slot_id}`));
        group.add(clone('crate', slot.bin_anchor, `box__${slot.slot_id}`));
        const proxy = new THREE.Mesh(proxyGeometry, proxyMaterial);
        proxy.position.set(slot.rack_center[0], 1.325, slot.rack_center[2]);
        proxy.userData.slotId = slot.slot_id;
        proxy.updateMatrixWorld(true);
        proxies.push(proxy);
      }
      group.add(clone('packing-station', [9, 0, .6]));
      group.add(clone('buffer-pallet', [18, 0, .8]));
      group.add(clone('forklift', [18.2, 0, 10.4], 'forklift__STATIC', Math.PI));
      group.add(clone('ibc-tote', [18.2, 0, 5.3]));
      group.add(clone('picker-cart', [3, 0, 6], 'picker_root__P1', Math.PI));
      group.add(clone('picker-cart', [11, 0, 8], 'picker_root__P2'));
    } else group.add(clone(next));
    current = batch(group);
    scene.add(current);
    key.target.position.copy(new THREE.Box3().setFromObject(current).getCenter(new THREE.Vector3()));
    renderer.shadowMap.needsUpdate = true;
    fit(new THREE.Box3().setFromObject(current), next === 'overview' || next === 'environment' ? new THREE.Vector3(1.12,1.25,-1.6) : new THREE.Vector3(1.2,.9,1.6));
    onStatus(stats());
  };
  const overview = () => setMode('overview');
  const top = () => fit(new THREE.Box3().setFromObject(current), new THREE.Vector3(.001, 1, -.001));
  const focusSlot = (id: string) => {
    const proxy = proxies.find((entry) => entry.userData.slotId === id);
    if (!proxy) return;
    selected = id;
    const bounds = new THREE.Box3().setFromObject(proxy);
    highlight.box.copy(bounds);
    highlight.visible = true;
    fit(bounds, new THREE.Vector3(1.7, 1.15, -1.4));
    onStatus(stats());
  };
  const pointer = new THREE.Vector2();
  const ray = new THREE.Raycaster();
  let down = [0, 0];
  const pointerDown = (event: PointerEvent) => { down = [event.clientX, event.clientY]; };
  const pointerUp = (event: PointerEvent) => {
    if (Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5 || mode !== 'overview') return;
    const bounds = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX-bounds.left)/bounds.width*2-1, -(event.clientY-bounds.top)/bounds.height*2+1);
    ray.setFromCamera(pointer, camera);
    const hit = ray.intersectObjects(proxies, false)[0];
    if (hit) focusSlot(hit.object.userData.slotId);
  };
  const observer = new ResizeObserver(() => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width/height;
    camera.updateProjectionMatrix();
  });
  const dispose = () => {
    disposed = true;
    cancelAnimationFrame(raf);
    observer.disconnect();
    controls.dispose();
    renderer.domElement.removeEventListener('pointerdown',pointerDown);
    renderer.domElement.removeEventListener('pointerup',pointerUp);
    geometries.forEach((geo) => geo.dispose());
    materials.forEach((mat) => mat.dispose());
    highlight.geometry.dispose();
    (highlight.material as THREE.Material).dispose();
    key.shadow.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  };
  try {
    await Promise.all(assetCatalog.map(async (asset) => {
      const result = await loader.loadAsync(`${import.meta.env.BASE_URL}models/${asset.id}.glb`);
      templates.set(asset.id, result.scene);
      result.scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          (Array.isArray(object.material)?object.material:[object.material]).forEach((material) => materials.add(material));
        }
      });
    }));
    if (disposed) throw new Error('Scene disposed');
    host.appendChild(renderer.domElement);
    renderer.setSize(host.clientWidth, host.clientHeight);
    camera.aspect = host.clientWidth/host.clientHeight;
    camera.updateProjectionMatrix();
    observer.observe(host);
    renderer.domElement.addEventListener('pointerdown',pointerDown);
    renderer.domElement.addEventListener('pointerup',pointerUp);
    overview();
    const animate = () => {
      if (disposed) return;
      controls.update();
      renderer.render(scene,camera);
      if (++tick % 30 === 0) onStatus(stats());
      raf = requestAnimationFrame(animate);
    };
    animate();
    return { dispose, setMode, overview, top, focusSlot, getState: () => ({...stats(), camera: camera.position.toArray(), target: controls.target.toArray(), distance: camera.position.distanceTo(controls.target)}) };
  } catch (error) { dispose(); throw error; }
}
