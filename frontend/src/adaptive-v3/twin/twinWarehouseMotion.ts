import * as THREE from 'three';
import { createWarehouseCargo } from '../warehouseCargo';
import { verifyWarehouseHeavyInboundSources } from '../warehouseHeavyInboundBinding';
import { compileWarehouseHeavyInboundPlan, type WarehouseHeavyInboundPlan } from '../warehouseHeavyInboundPlan';
import { createWarehouseHeavyInboundScene } from '../warehouseHeavyInboundScene';
import { deriveNativeWorkerGaitRig, compileNativeWorkerGait, type WorkerGaitPose } from '../warehouseWorkerGait';
import { validateRoutePolicy, createWarehouseRouter, type RoutePolicy } from '../warehouseRouting';
import type { WarehouseBundle, XYZ, V3Record } from '../warehouseTypes';
import type { WarehouseTexts } from '../warehouseAdapter';
export type TwinWarehouseMotion = {
    apply(variant: 'A' | 'B', at_s: number): void;
    actorPosition(variant: 'A' | 'B', at_s: number, actor_id: string): XYZ | undefined;
    carrierFrames(variant: 'A' | 'B', at_s: number): readonly BeltFrame[];
    snapshot(): Record<string, unknown>;
    dynamicObjects(): THREE.Object3D[];
    dispose(): void;
};
type Variant = 'A' | 'B';
type Local = {
    node: THREE.Object3D;
    position: THREE.Vector3;
    quaternion: THREE.Quaternion;
    scale: THREE.Vector3;
};
type Edge = {
    edge_id: string;
    from_node_id: string;
    to_node_id: string;
    length_m: number;
    path_kind: string;
    resource_id: string;
    turn_timing: string | null;
    centre?: XYZ;
    radius_m?: number;
    theta_start_rad?: number;
    theta_end_rad?: number;
};
type BeltStep = {
    start: number;
    end: number;
    phase: 'travel' | 'pivot' | 'packing_wait';
    edge: Edge;
    from: number;
    to: number;
    yawFrom: number;
    yawTo: number;
    payload: 'tote' | 'parcel';
};
export type BeltFrame = {
    id: string;
    visible: boolean;
    payload: 'tote' | 'parcel';
    phase: string;
    position: XYZ;
    yaw: number;
    source_edge_id: string;
};
// Finite display episode. Negative starts explicitly place two carriers in transit at t=0.
const BELT_STARTS = Object.freeze([-128, -64, 0, 64, 128, 192]);
const Y = new THREE.Vector3(0, 1, 0), UNIT = new THREE.Vector3(1, 1, 1);
const requireValue = (value: unknown, message: string): void => { if (!value)
    throw Error(message); };
const pose = (position: XYZ, yaw: number) => new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromAxisAngle(Y, yaw), UNIT);
function checkTime(variant: Variant, at: number) {
    requireValue((variant === 'A' || variant === 'B') && Number.isFinite(at) && at >= 0 && at <= 240, 'Invalid main comparison motion time or variant');
}
function save(root: THREE.Object3D): Local[] {
    const rows: Local[] = [];
    root.traverse(node => rows.push({ node, position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone() }));
    return rows;
}
function restore(rows: Local[]) {
    for (const row of rows) {
        row.node.position.copy(row.position);
        row.node.quaternion.copy(row.quaternion);
        row.node.scale.copy(row.scale);
    }
}
function actor(scene: THREE.Scene, id: string): THREE.Object3D {
    const found: THREE.Object3D[] = [];
    scene.traverse(node => { if (node.userData.semanticKind === 'actor' && node.userData.semanticId === id)
        found.push(node); });
    requireValue(found.length === 1, 'Original motion actor missing or duplicated: ' + id);
    return found[0];
}
function headPoint(root: THREE.Object3D): THREE.Vector3 {
    root.updateWorldMatrix(true, true);
    const bounds = new THREE.Box3().setFromObject(root), centre = bounds.getCenter(new THREE.Vector3());
    return new THREE.Vector3(centre.x, bounds.max.y + .55, centre.z);
}
function prepareWorker(scene: THREE.Scene, bundle: WarehouseBundle, policy: RoutePolicy) {
    const root = actor(scene, 'S02'), homes = save(root), rig = deriveNativeWorkerGaitRig(root);
    const router = createWarehouseRouter(bundle, policy), lookup = new Map(bundle.layout.walk.nodes.map(n => [n.node_id, n.world_pos]));
    const home = 'v3:service:OUT_S_EXPRESS', target = 'v3:ped-node:08400:01000';
    const route = (from: string, to: string) => {
        const plan = router.route({ source_kind: 'visual_fixture', engine_operation: false, mode: 'pedestrian', actor_id: 'S02', vehicle_id: null, cargo_archetype_id: null, from_node_id: from, to_node_id: to, service_port_id: null, closed_arc_ids: [] });
        requireValue(plan.ok, 'Shared apron worker route refused: ' + plan.reason);
        const ids = [from];
        for (const id of plan.arc_ids) {
            const arc = bundle.layout.walk.arcs.find(a => a.arc_id === id)!;
            ids.push(bundle.layout.walk.nodes[arc.to_node_index].node_id);
        }
        const points = ids.map(id => lookup.get(id)!);
        requireValue(points.every(p => p[2] >= 6 && p[2] <= 10 && p[0] >= 48 && p[0] <= 84), 'Worker route leaves the shared southern apron');
        return points;
    };
    const fixed = bundle.layout.modules.map(m => m.outer_bounds_world);
    const outward = compileNativeWorkerGait(rig, route(home, target), root.rotation.y, 1.2, fixed);
    const returning = compileNativeWorkerGait(rig, route(target, home), outward.sample(outward.duration_s).yaw_rad, 1.2, fixed);
    const head = root.getObjectByName('joint__head')!;
    const localHead = head.worldToLocal(headPoint(root));
    const chain: Local[] = [];
    for (let node: THREE.Object3D | null = head; node && node !== root; node = node.parent)
        chain.unshift(homes.find(row => row.node === node)!);
    const sample = (at: number) => at <= outward.duration_s + 4 ? outward.sample(Math.min(at, outward.duration_s)) : returning.sample(Math.min(returning.duration_s, at - outward.duration_s - 4));
    const position = (p: WorkerGaitPose) => {
        const matrix = pose(p.root_world, p.yaw_rad);
        for (const row of chain)
            matrix.multiply(new THREE.Matrix4().compose(row.position, p.joint_rotations[row.node.name] ? new THREE.Quaternion().fromArray(p.joint_rotations[row.node.name]) : row.quaternion, row.scale));
        return localHead.clone().applyMatrix4(matrix).toArray() as XYZ;
    };
    const apply = (at: number) => {
        restore(homes);
        const frame = sample(at), matrix = pose(frame.root_world, frame.yaw_rad);
        if (root.parent)
            matrix.premultiply(root.parent.matrixWorld.clone().invert());
        matrix.decompose(root.position, root.quaternion, root.scale);
        for (const [name, rotation] of Object.entries(frame.joint_rotations))
            root.getObjectByName(name)!.quaternion.fromArray(rotation);
        root.updateWorldMatrix(true, true);
    };
    return { root, sample, head: (at: number) => position(sample(at)), apply, reset: () => { restore(homes); root.updateWorldMatrix(true, true); }, duration: outward.duration_s + 4 + returning.duration_s };
}
function beltPath(edges: Edge[], from: string, to: string): Edge[] {
    const queue = [from], seen = new Set(queue), parents = new Map<string, Edge>();
    for (let i = 0; i < queue.length && !seen.has(to); i++) {
        for (const edge of edges.filter(e => e.from_node_id === queue[i]))
            if (!seen.has(edge.to_node_id)) {
                seen.add(edge.to_node_id);
                parents.set(edge.to_node_id, edge);
                queue.push(edge.to_node_id);
            }
    }
    requireValue(seen.has(to), 'Source conveyor route is disconnected');
    const result: Edge[] = [];
    for (let node = to; node !== from;) {
        const edge = parents.get(node)!;
        result.unshift(edge);
        node = edge.from_node_id;
    }
    return result;
}
function compileBelt(bundle: WarehouseBundle, variant: Variant) {
    const source = bundle.layout.data.conveyor as V3Record, edges = [...source.edges as Edge[]].sort((a, b) => a.edge_id.localeCompare(b.edge_id));
    const nodes = new Map((source.nodes as V3Record[]).map(n => [n.node_id as string, n.world_pos as XYZ]));
    const assumptions = source.source_assumptions as {
        speed_m_s: number;
        transfer_dwell_s: number;
    };
    requireValue(assumptions.speed_m_s > 0 && assumptions.transfer_dwell_s > 0, 'Source conveyor timing is missing');
    const station = variant === 'A' ? 'PK03' : 'PK05', steps: BeltStep[] = [];
    let time = 0;
    const append = (path: Edge[], payload: 'tote' | 'parcel') => {
        for (const edge of path) {
            const yaw = edge.path_kind === 'arc' || edge.resource_id === 'V3_FEED' ? 0 : edge.resource_id.startsWith('V3_SPUR') || edge.turn_timing ? Math.PI : Math.PI / 2;
            if (edge.turn_timing === 'before_edge') {
                steps.push({ start: time, end: time + assumptions.transfer_dwell_s, phase: 'pivot', edge, from: 0, to: 0, yawFrom: Math.PI / 2, yawTo: Math.PI, payload });
                time += assumptions.transfer_dwell_s;
            }
            const duration = edge.length_m / assumptions.speed_m_s;
            steps.push({ start: time, end: time + duration, phase: 'travel', edge, from: 0, to: 1, yawFrom: yaw, yawTo: edge.path_kind === 'arc' ? Math.PI / 2 : yaw, payload });
            time += duration;
            if (edge.turn_timing === 'after_edge') {
                steps.push({ start: time, end: time + assumptions.transfer_dwell_s, phase: 'pivot', edge, from: 1, to: 1, yawFrom: Math.PI, yawTo: Math.PI / 2, payload });
                time += assumptions.transfer_dwell_s;
            }
        }
    };
    append(beltPath(edges, 'v3:conv:intake', 'v3:conv:' + station + ':WORK'), 'tote');
    const last = steps.at(-1)!;
    steps.push({ ...last, start: time, end: time + (variant === 'A' ? 42 : 12), phase: 'packing_wait', from: 1, to: 1, yawFrom: last.yawTo, yawTo: last.yawTo });
    time = steps.at(-1)!.end;
    append(beltPath(edges, 'v3:conv:' + station + ':WORK', 'v3:conv:output'), 'parcel');
    return { steps, nodes, duration: time };
}
function beltPosition(step: BeltStep, at: number, nodes: Map<string, XYZ>) {
    const u = Math.max(0, Math.min(1, (at - step.start) / (step.end - step.start))), progress = step.from + (step.to - step.from) * u;
    const edge = step.edge, a = nodes.get(edge.from_node_id)!, b = nodes.get(edge.to_node_id)!;
    let position = a.map((v, i) => v + (b[i] - v) * progress) as XYZ;
    if (edge.path_kind === 'arc') {
        const angle = edge.theta_start_rad! + (edge.theta_end_rad! - edge.theta_start_rad!) * progress;
        position = [edge.centre![0] + edge.radius_m! * Math.cos(angle), edge.centre![1], edge.centre![2] + edge.radius_m! * Math.sin(angle)];
    }
    return { position, yaw: step.yawFrom + (step.yawTo - step.yawFrom) * u };
}
function beltFrames(plan: ReturnType<typeof compileBelt>, at: number): BeltFrame[] {
    return BELT_STARTS.map((start, index) => {
        const local = at - start, step = plan.steps.find(s => local >= s.start && local < s.end);
        const held = step ?? (local < 0 ? plan.steps[0]! : plan.steps.at(-1)!);
        const sampled = beltPosition(held, Math.max(0, Math.min(local, plan.duration)), plan.nodes);
        return { id: 'twin-visual-carrier-' + (index + 1), visible: !!step, payload: held.payload, phase: step?.phase ?? (local < 0 ? 'not_arrived' : 'finished_visual'), source_edge_id: held.edge.edge_id, ...sampled };
    });
}
type ParcelPart = {
    geometry: THREE.BufferGeometry;
    material: THREE.Material | THREE.Material[];
    matrix: THREE.Matrix4;
};
function parcelParts(scene: THREE.Scene, bundle: WarehouseBundle): ParcelPart[] {
    const source = createWarehouseCargo(bundle).snapshot().find(h => h.cargo.archetype_id === 'SMALL_CARTON')!;
    const admission = (bundle.layout.data.conveyor as V3Record).payload_admission as {
        maximum_footprint_m: number[];
        maximum_height_m: number;
        tote_outer_target_m: XYZ;
    };
    const dimensions = source.cargo.dimensions_xyz_m;
    requireValue(dimensions[0] <= admission.maximum_footprint_m[0] && dimensions[2] <= admission.maximum_footprint_m[1] && dimensions[1] <= admission.maximum_height_m, 'Source parcel geometry exceeds belt envelope');
    const tote = admission.tote_outer_target_m;
    requireValue(dimensions[0] <= tote[0] - .024 && dimensions[1] <= tote[1] - .012 && dimensions[2] <= tote[2] - .024, 'Source parcel does not fit the tote interior');
    const inverse = pose(source.position, source.yaw_rad).invert(), result: ParcelPart[] = [];
    scene.updateMatrixWorld(true);
    scene.traverse(node => {
        if (!(node instanceof THREE.InstancedMesh) || node.userData.semanticKind !== 'HU')
            return;
        const index = (node.userData.semanticIds as string[]).indexOf(source.handling_unit_id);
        if (index < 0)
            return;
        const matrix = new THREE.Matrix4();
        node.getMatrixAt(index, matrix);
        result.push({ geometry: node.geometry, material: node.material, matrix: inverse.clone().multiply(node.matrixWorld).multiply(matrix) });
    });
    requireValue(result.length > 0, 'Source parcel carton mesh is missing');
    return result;
}
class BeltView {
    readonly root = new THREE.Group();
    private readonly cargo = new Map<string, {
        root: THREE.Group;
        tote: THREE.Group;
        parcel: THREE.Group;
    }>();
    private readonly owned: (THREE.BufferGeometry | THREE.Material)[] = [];
    constructor(scene: THREE.Scene, bundle: WarehouseBundle) {
        const parts = parcelParts(scene, bundle);
        this.root.name = 'twin_visual_belt_motion';
        const dimensions = ((bundle.layout.data.conveyor as V3Record).payload_admission as {
            tote_outer_target_m: XYZ;
        }).tote_outer_target_m;
        try {
            const material = new THREE.MeshStandardMaterial({ color: '#1d6579', roughness: .65 });
            this.owned.push(material);
            for (let i = 0; i < BELT_STARTS.length; i++) {
                const root = new THREE.Group(), tote = this.tote(dimensions, material, parts), parcel = this.parcel(parts);
                root.add(tote, parcel);
                this.root.add(root);
                this.cargo.set('twin-visual-carrier-' + (i + 1), { root, tote, parcel });
            }
            scene.add(this.root);
        }
        catch (error) {
            this.dispose();
            throw error;
        }
    }
    private parcel(parts: ParcelPart[]) {
        const group = new THREE.Group();
        for (const part of parts) {
            const mesh = new THREE.Mesh(part.geometry, part.material);
            mesh.matrixAutoUpdate = false;
            mesh.matrix.copy(part.matrix);
            mesh.castShadow = true;
            group.add(mesh);
        }
        return group;
    }
    private tote(d: XYZ, material: THREE.Material, parts: ParcelPart[]) {
        const group = new THREE.Group(), thick = .012;
        const boxes: {
            size: XYZ;
            p: XYZ;
        }[] = [{ size: [d[0], thick, d[2]], p: [0, thick / 2, 0] }, { size: [thick, d[1], d[2]], p: [(-d[0] + thick) / 2, d[1] / 2, 0] }, { size: [thick, d[1], d[2]], p: [(d[0] - thick) / 2, d[1] / 2, 0] }, { size: [d[0], d[1], thick], p: [0, d[1] / 2, (-d[2] + thick) / 2] }, { size: [d[0], d[1], thick], p: [0, d[1] / 2, (d[2] - thick) / 2] }];
        for (const box of boxes) {
            const geometry = new THREE.BoxGeometry(...box.size), mesh = new THREE.Mesh(geometry, material);
            this.owned.push(geometry);
            mesh.position.fromArray(box.p);
            mesh.castShadow = true;
            group.add(mesh);
        }
        const goods = this.parcel(parts);
        goods.name = 'twin_visual_tote_goods';
        goods.position.y = thick;
        group.add(goods);
        return group;
    }
    apply(frames: BeltFrame[]) {
        for (const frame of frames) {
            const object = this.cargo.get(frame.id)!;
            object.root.visible = frame.visible;
            object.root.position.fromArray(frame.position);
            object.root.rotation.y = frame.yaw;
            object.tote.visible = frame.payload === 'tote';
            object.parcel.visible = frame.payload === 'parcel';
        }
        this.root.updateWorldMatrix(true, true);
    }
    dispose() { this.root.removeFromParent(); for (const item of this.owned)
        item.dispose(); this.owned.length = 0; }
}
async function readSource(path: string, signal: AbortSignal) {
    const response = await fetch(import.meta.env.BASE_URL + path.replace(/^\//, ''), { signal, cache: 'no-store' });
    requireValue(response.ok, 'Main motion source missing: ' + path);
    return response.text();
}
function dynamicLayers(roots: THREE.Object3D[]) {
    const saved = new Map<THREE.Object3D, number>();
    for (const root of roots)
        root.traverse(node => { if (!saved.has(node))
            saved.set(node, node.layers.mask); node.layers.set(1); });
    return () => { for (const [node, mask] of saved)
        node.layers.mask = mask; };
}
class MainWarehouseMotion implements TwinWarehouseMotion {
    private disposed = false;
    private variant: Variant = 'A';
    private at = 0;
    constructor(private readonly scene: THREE.Scene, private readonly plan: WarehouseHeavyInboundPlan, private readonly worker: ReturnType<typeof prepareWorker>, private readonly heavy: ReturnType<typeof createWarehouseHeavyInboundScene>, private readonly belt: BeltView, private readonly tracks: Record<Variant, ReturnType<typeof compileBelt>>, private readonly relativeHead: THREE.Vector3, private readonly roots: THREE.Object3D[], private readonly restoreLayers: () => void) { }
    apply(variant: Variant, at: number) {
        requireValue(!this.disposed, 'Main warehouse motion is disposed');
        checkTime(variant, at);
        this.heavy.apply(at);
        this.worker.apply(at);
        this.belt.apply(beltFrames(this.tracks[variant], at));
        this.scene.updateMatrixWorld(true);
        this.variant = variant;
        this.at = at;
    }
    actorPosition(variant: Variant, at: number, id: string): XYZ | undefined {
        requireValue(!this.disposed, 'Main warehouse motion is disposed');
        checkTime(variant, at);
        if (id === 'S02')
            return this.worker.head(at);
        if (id === 'F01') {
            const body = this.plan.sample(at).body;
            return this.relativeHead.clone().applyMatrix4(pose(body.position, body.yaw_rad)).toArray() as XYZ;
        }
        return undefined;
    }
    carrierFrames(variant: Variant, at: number): readonly BeltFrame[] {
        requireValue(!this.disposed, 'Main warehouse motion is disposed');
        checkTime(variant, at);
        return beltFrames(this.tracks[variant], at);
    }
    dynamicObjects() { return this.disposed ? [] : [...this.roots]; }
    snapshot() {
        return {
            variant: this.variant, at_s: this.at, disposed: this.disposed,
            source_kind: 'visual_fixture', engine_operation: false, operational_admission: false, cost_evaluated: false,
            source_stock_HUs: 530, moving_worker_ids: ['S02'], moving_vehicle_ids: ['FL01'], driver_id: 'F01',
            heavy: this.heavy.snapshot(), heavy_duration_s: this.plan.duration_s,
            heavy_visual_complete: this.plan.sample(this.at).completed_visual_jobs === 1,
            worker: { position: this.worker.sample(this.at).root_world, phase: this.worker.sample(this.at).stage, duration_s: this.worker.duration },
            belt: beltFrames(this.tracks[this.variant], this.at), belt_wait_basis: 'authored_visual_fixture',
            belt_carrier_starts_s: [...BELT_STARTS], belt_initial_state_basis: 'authored_prerolled_visual_carriers', belt_end_hold_s: 240,
            belt_motion_basis: 'source_geometry_speed_and_dwell', dynamic_roots: this.roots.length,
        };
    }
    dispose() {
        if (this.disposed)
            return;
        this.disposed = true;
        this.restoreLayers();
        this.worker.reset();
        this.belt.dispose();
        this.heavy.dispose();
        this.scene.updateMatrixWorld(true);
    }
}
/** A finite visual episode on the main comparison clock; no engine or KPI production. */
export async function createTwinWarehouseMotion(scene: THREE.Scene, bundle: WarehouseBundle, texts: WarehouseTexts, signal: AbortSignal): Promise<TwinWarehouseMotion> {
    signal.throwIfAborted();
    requireValue(scene.isScene && bundle.source_kind === 'visual_fixture' && bundle.engine_operation === false, 'Validated warehouse scene required');
    const [fixtureText, policyText] = await Promise.all([readSource('/data/v3/heavy-inbound-fixture.json', signal), readSource('/data/v3/route-policy-v3.json', signal)]);
    const fixture = await verifyWarehouseHeavyInboundSources(texts, fixtureText), policy = await validateRoutePolicy(policyText, bundle);
    signal.throwIfAborted();
    const plan = compileWarehouseHeavyInboundPlan(bundle, fixture), worker = prepareWorker(scene, bundle, policy);
    const vehicle = scene.getObjectByName('vehicle__FL01')!;
    requireValue(vehicle, 'Original FL01 is missing');
    const relativeHead = headPoint(actor(scene, 'F01')).applyMatrix4(vehicle.matrixWorld.clone().invert());
    const existing = new Set(scene.children), tracks = { A: compileBelt(bundle, 'A'), B: compileBelt(bundle, 'B') };
    const heavy = createWarehouseHeavyInboundScene(scene, bundle, plan);
    let belt: BeltView | undefined, restoreLayers: (() => void) | undefined;
    try {
        belt = new BeltView(scene, bundle);
        const roots = [vehicle, worker.root, ...scene.children.filter(node => !existing.has(node))];
        restoreLayers = dynamicLayers(roots);
        return new MainWarehouseMotion(scene, plan, worker, heavy, belt, tracks, relativeHead, roots, restoreLayers);
    }
    catch (error) {
        restoreLayers?.();
        worker.reset();
        belt?.dispose();
        heavy.dispose();
        throw error;
    }
}
