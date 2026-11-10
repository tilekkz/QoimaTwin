import * as THREE from 'three';
import { createWarehouseCargo } from '../warehouseCargo';
import { verifyWarehouseHeavyInboundSources } from '../warehouseHeavyInboundBinding';
import { compileWarehouseHeavyInboundPlan, type WarehouseHeavyInboundPlan } from '../warehouseHeavyInboundPlan';
import { createWarehouseHeavyInboundScene } from '../warehouseHeavyInboundScene';
import { validateRoutePolicy } from '../warehouseRouting';
import { compileTwinFlowScenario, type TwinFlowScenario, type FlowFrame } from './twinFlowScenario';
import { createTwinStaffResponse, type TwinStaffResponse, type TwinStaffActivity } from './twinStaffResponse';
import { createTwinFleetTraffic, type TwinFleetTraffic } from './twinFleetTraffic';
import type { WarehouseLayoutPlan } from '../warehouseLayoutPlan';
import type { WarehouseBundle, XYZ, V3Record } from '../warehouseTypes';
import type { WarehouseTexts } from '../warehouseAdapter';
export type TwinWarehouseMotion = {
    apply(variant: 'A' | 'B', at_s: number): void;
    actorPosition(variant: 'A' | 'B', at_s: number, actor_id: string): XYZ | undefined;
    carrierFrames(variant: 'A' | 'B', at_s: number): readonly BeltFrame[];
    operations(variant: 'A' | 'B', at_s: number): FlowFrame & {
        staff: TwinStaffActivity[];
        working_count: number;
        hotpost_staff_count: number;
    };
    actorActivity(variant: 'A' | 'B', at_s: number, actor_id: string): TwinStaffActivity | undefined;
    scenario(): TwinFlowScenario;
    presentationCounts(): PresentationCounts;
    snapshot(): Record<string, unknown>;
    dynamicObjects(): THREE.Object3D[];
    dispose(): void;
};
export type PresentationCounts = {
    workers: number;
    vehicles: number;
    sourceWorkers: number;
    sourceVehicles: number;
    extraWorkers: number;
    extraVehicles: number;
};
export type TwinWarehouseMotionOptions = {layoutPlan?: WarehouseLayoutPlan};
type Variant = 'A' | 'B';
type Local = {
    node: THREE.Object3D;
    position: THREE.Vector3;
    quaternion: THREE.Quaternion;
    scale: THREE.Vector3;
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
const Y = new THREE.Vector3(0, 1, 0), UNIT = new THREE.Vector3(1, 1, 1);
const requireValue = (value: unknown, message: string): void => {
    if (!value)
        throw Error(message);
};
const pose = (position: XYZ, yaw: number) => new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromAxisAngle(Y, yaw), UNIT);
function checkTime(variant: Variant, at: number, duration: number) {
    requireValue((variant === 'A' || variant === 'B') && Number.isFinite(at) && at >= 0 && at <= duration, 'Invalid main comparison motion time or variant');
}
function save(root: THREE.Object3D): Local[] {
    const rows: Local[] = [];
    root.traverse(node => rows.push({
        node,
        position: node.position.clone(),
        quaternion: node.quaternion.clone(),
        scale: node.scale.clone()
    }));
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
    scene.traverse(node => {
        if (node.userData.semanticKind === 'actor' && node.userData.semanticId === id)
            found.push(node);
    });
    requireValue(found.length === 1, 'Original motion actor missing or duplicated: ' + id);
    return found[0];
}
function headPoint(root: THREE.Object3D): THREE.Vector3 {
    root.updateWorldMatrix(true, true);
    const bounds = new THREE.Box3().setFromObject(root), centre = bounds.getCenter(new THREE.Vector3());
    return new THREE.Vector3(centre.x, bounds.max.y + .55, centre.z);
}
function prepareWorker(scene: THREE.Scene) {
    const root = actor(scene, 'S02'), homes = save(root), head = headPoint(root).toArray() as XYZ;
    // S02 stays at its original home while source-qualified packers share the apron.
    const reset = () => {
        restore(homes);
        root.updateWorldMatrix(true, true);
    };
    return {
        root,
        head: () => [...head] as XYZ,
        reset
    };
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
        result.push({
            geometry: node.geometry,
            material: node.material,
            matrix: inverse.clone().multiply(node.matrixWorld).multiply(matrix)
        });
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
    constructor(scene: THREE.Scene, bundle: WarehouseBundle, ids: readonly string[]) {
        const parts = parcelParts(scene, bundle);
        this.root.name = 'twin_visual_belt_motion';
        const dimensions = ((bundle.layout.data.conveyor as V3Record).payload_admission as {
            tote_outer_target_m: XYZ;
        }).tote_outer_target_m;
        try {
            const material = new THREE.MeshStandardMaterial({ color: '#1d6579', roughness: .65 });
            this.owned.push(material);
            for (const id of ids) {
                const root = new THREE.Group(), tote = this.tote(dimensions, material, parts), parcel = this.parcel(parts);
                root.add(tote, parcel);
                this.root.add(root);
                this.cargo.set(id, {
                    root,
                    tote,
                    parcel
                });
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
    dispose() {
        this.root.removeFromParent();
        for (const item of this.owned)
            item.dispose();
        this.owned.length = 0;
    }
}
async function readSource(path: string, signal: AbortSignal) {
    const response = await fetch(import.meta.env.BASE_URL + path.replace(/^\//, ''), { signal, cache: 'no-store' });
    requireValue(response.ok, 'Main motion source missing: ' + path);
    return response.text();
}
function dynamicLayers(roots: THREE.Object3D[]) {
    const saved = new Map<THREE.Object3D, number>();
    for (const root of roots)
        root.traverse(node => {
            if (!saved.has(node))
                saved.set(node, node.layers.mask);
            node.layers.set(1);
        });
    return () => {
        for (const [node, mask] of saved)
            node.layers.mask = mask;
    };
}
class MainWarehouseMotion implements TwinWarehouseMotion {
    private disposed = false;
    private variant: Variant = 'A';
    private at = 0;
    constructor(private readonly scene: THREE.Scene,
        private readonly plan: WarehouseHeavyInboundPlan, private readonly worker: ReturnType<typeof prepareWorker>, private readonly heavy: ReturnType<typeof createWarehouseHeavyInboundScene>, private readonly belt: BeltView, private readonly flow: TwinFlowScenario, private readonly staff: TwinStaffResponse, private readonly relativeHead: THREE.Vector3, private readonly roots: THREE.Object3D[], private readonly restoreLayers: () => void, private readonly fleet?: TwinFleetTraffic) {
    }
    private live(variant: Variant, at: number) {
        requireValue(!this.disposed, 'Main warehouse motion is disposed');
        checkTime(variant, at, this.flow.duration_s);
    }
    operations(variant: Variant, at: number) {
        this.live(variant, at);
        const flow = this.flow.sample(variant, at);
        const mask = flow.stations.filter(row => row.status === 'processing').map(row => row.station_id);
        const staff = this.staff.sample(variant, at, mask);
        return {
            ...flow,
            staff: staff.workers,
            working_count: staff.working_count,
            hotpost_staff_count: staff.hotpost_staff_count
        };
    }
    apply(variant: Variant, at: number) {
        const flow = this.operations(variant, at);
        this.heavy.apply(at);
        this.worker.reset();
        this.staff.apply(variant, at, flow.stations.filter(row => row.status === 'processing').map(row => row.station_id));
        this.fleet?.apply(variant, at);
        this.belt.apply(flow.cargoFrames);
        this.scene.updateMatrixWorld(true);
        this.variant = variant;
        this.at = at;
    }
    actorPosition(variant: Variant, at: number, id: string): XYZ | undefined {
        this.live(variant, at);
        if (id === 'S02')
            return this.worker.head();
        const staff = this.staff.actorPosition(variant, id, at);
        if (staff)
            return staff;
        if (id === 'F01') {
            const body = this.plan.sample(at).body;
            return this.relativeHead.clone().applyMatrix4(pose(body.position, body.yaw_rad)).toArray() as XYZ;
        }
        return this.fleet?.actorPosition(variant, at, id) ?? undefined;
    }
    actorActivity(variant: Variant, at: number, id: string) {
        return this.operations(variant, at).staff.find(row => row.actor_id === id);
    }
    carrierFrames(variant: Variant, at: number): readonly BeltFrame[] {
        this.live(variant, at);
        return this.flow.sample(variant, at).cargoFrames;
    }
    scenario() {
        this.live(this.variant, this.at);
        return this.flow;
    }
    presentationCounts(): PresentationCounts {
        this.live(this.variant, this.at);
        const fleet = this.fleet?.summary();
        return {
            workers: fleet?.people ?? 24,
            vehicles: fleet?.vehicles ?? 2,
            sourceWorkers: 24,
            sourceVehicles: 2,
            extraWorkers: fleet?.extra_people ?? 0,
            extraVehicles: fleet?.extra_vehicles ?? 0,
        };
    }
    dynamicObjects() {
        return this.disposed ? [] : [...this.roots];
    }
    snapshot() {
        const operations = this.operations(this.variant, this.at);
        return {
            variant: this.variant,
            at_s: this.at,
            disposed: this.disposed,
            source_kind: 'visual_fixture',
            engine_operation: false,
            operational_admission: false,
            cost_evaluated: false,
            presentation_counts: this.presentationCounts(),
            visual_extra_fleet: this.fleet?.snapshot() ?? null,
            source_stock_HUs: 530,
            moving_worker_ids: ['K01', 'K02', 'K05', 'K06'],
            moving_vehicle_ids: ['FL01'],
            driver_id: 'F01',
            heavy: this.heavy.snapshot(),
            heavy_duration_s: this.plan.duration_s,
            heavy_visual_complete: this.plan.sample(this.at).completed_visual_jobs === 1,
            worker: {
                actor_id: 'S02',
                phase: 'source_home',
                patrol_disabled_for_shared_apron: true
            },
            belt: operations.cargoFrames,
            operations,
            belt_wait_basis: 'common_source_capacity_reservations_and_staff_availability',
            belt_carrier_starts_s: this.flow.jobs.map(job => job.arrival_s),
            belt_initial_state_basis: 'common_authored_preroll',
            belt_end_hold_s: this.flow.duration_s,
            belt_motion_basis: 'source_geometry_speed_and_dwell',
            dynamic_roots: this.roots.length,
        };
    }
    dispose() {
        if (this.disposed)
            return;
        this.disposed = true;
        this.restoreLayers();
        this.fleet?.dispose();
        this.staff.dispose();
        this.worker.reset();
        this.belt.dispose();
        this.heavy.dispose();
        this.scene.updateMatrixWorld(true);
    }
}
/** Finite visual packing episode. Source paths and original actors share one clock. */
export async function createTwinWarehouseMotion(scene: THREE.Scene, bundle: WarehouseBundle, texts: WarehouseTexts, signal: AbortSignal, options: TwinWarehouseMotionOptions = {}): Promise<TwinWarehouseMotion> {
    signal.throwIfAborted();
    requireValue(scene.isScene && bundle.source_kind === 'visual_fixture' && bundle.engine_operation === false, 'Validated warehouse scene required');
    const [fixtureText, policyText] = await Promise.all([readSource('/data/v3/heavy-inbound-fixture.json', signal), readSource('/data/v3/route-policy-v3.json', signal)]);
    const fixture = await verifyWarehouseHeavyInboundSources(texts, fixtureText), policy = await validateRoutePolicy(policyText, bundle);
    signal.throwIfAborted();
    const plan = compileWarehouseHeavyInboundPlan(bundle, fixture), worker = prepareWorker(scene);
    const vehicle = scene.getObjectByName('vehicle__FL01')!;
    requireValue(vehicle, 'Original FL01 is missing');
    const relativeHead = headPoint(actor(scene, 'F01')).applyMatrix4(vehicle.matrixWorld.clone().invert());
    const existing = new Set(scene.children);
    let staff: TwinStaffResponse | undefined, heavy: ReturnType<typeof createWarehouseHeavyInboundScene> | undefined;
    let fleet: TwinFleetTraffic | undefined;
    let belt: BeltView | undefined, restoreLayers: (() => void) | undefined;
    try {
        staff = await createTwinStaffResponse(scene, bundle, policy);
        signal.throwIfAborted();
        const flow = compileTwinFlowScenario(bundle, { staffReady_s: staff.stationReady_s, duration_s: Math.max(360, staff.duration_s) });
        heavy = createWarehouseHeavyInboundScene(scene, bundle, plan);
        if (options.layoutPlan) fleet = createTwinFleetTraffic(scene, bundle, options.layoutPlan);
        belt = new BeltView(scene, bundle, flow.jobs.map(job => job.id));
        const roots = [...new Set([vehicle, worker.root, ...staff.dynamicRoots, ...(fleet?.dynamicRoots ?? []), ...scene.children.filter(node => !existing.has(node))])];
        restoreLayers = dynamicLayers(roots);
        return new MainWarehouseMotion(scene, plan, worker, heavy, belt, flow, staff, relativeHead, roots, restoreLayers, fleet);
    }
    catch (error) {
        restoreLayers?.();
        fleet?.dispose();
        staff?.dispose();
        worker.reset();
        belt?.dispose();
        heavy?.dispose();
        throw error;
    }
}
