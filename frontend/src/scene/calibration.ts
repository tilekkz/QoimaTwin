import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { legacyLayout as layout } from '../contracts';

export async function mountCalibration(host: HTMLElement) {
  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe7ebee);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 50);
  camera.position.set(6, 5, 8);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0.7, 0.4, 1);
  controls.enablePan = false;
  controls.minDistance = 3;
  controls.maxDistance = 15;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x747474, 2));
  const light = new THREE.DirectionalLight(0xffffff, 2);
  light.position.set(4, 8, 6);
  scene.add(light, new THREE.GridHelper(10, 10), new THREE.AxesHelper(2));
  const render = () => renderer.render(scene, camera);
  const resize = new ResizeObserver(() => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    render();
  });
  const dispose = () => {
    resize.disconnect();
    controls.removeEventListener('change', render);
    controls.dispose();
    const geometries = new Set<THREE.BufferGeometry>();
    const materials = new Set<THREE.Material>();
    scene.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (mesh.geometry) geometries.add(mesh.geometry);
      if (mesh.material) (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach((m) => materials.add(m));
    });
    geometries.forEach((geometry) => geometry.dispose());
    materials.forEach((material) => material.dispose());
    renderer.dispose();
    renderer.domElement.remove();
  };

  try {
    const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}models/calibration.glb`);
    scene.add(gltf.scene);
    gltf.scene.updateMatrixWorld(true);
    const expectedAnchors: Record<string, number[]> = {
      anchor_origin: [0, 0, 0], anchor_x: [1, 0, 0],
      anchor_y: [0, 1, 0], anchor_z: [0, 0, 1],
      anchor_box__S_A1_B1: layout.slots.find((slot) => slot.slot_id === 'S_A1_B1')!.bin_anchor,
    };
    const positions: Record<string, number[]> = {};
    for (const [name, expected] of Object.entries(expectedAnchors)) {
      const node = gltf.scene.getObjectByName(name);
      if (!node) throw new Error(`GLB: отсутствует ${name}`);
      const actual = node.getWorldPosition(new THREE.Vector3());
      if (actual.distanceTo(new THREE.Vector3(...expected)) > 1e-6) throw new Error(`GLB: неверная ось/координата ${name}`);
      positions[name] = actual.toArray();
    }
    const cube = gltf.scene.getObjectByName('calibration_cube_1m');
    if (!cube) throw new Error('GLB: отсутствует метровый куб');
    const size = new THREE.Box3().setFromObject(cube).getSize(new THREE.Vector3());
    if (size.distanceTo(new THREE.Vector3(1, 1, 1)) > 1e-6) throw new Error('GLB: нарушен масштаб 1 метр');
    if (cube.userData.layout_version !== layout.layout_version) throw new Error('GLB: несовместимый layout_version');
    host.appendChild(renderer.domElement);
    controls.update();
    controls.addEventListener('change', render);
    resize.observe(host);
    render();
    return { dispose, diagnostics: { webgl: true, threeRevision: THREE.REVISION, localGlb: true, unitCubeSize: size.toArray(), positions } };
  } catch (error) {
    dispose();
    throw error;
  }
}
