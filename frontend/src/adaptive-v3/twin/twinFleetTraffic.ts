import * as THREE from 'three';
import {sampleVehicleArc} from '../warehouseRoutePose';
import {compileNativeWorkerGait, deriveNativeWorkerGaitRig} from '../warehouseWorkerGait';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {WarehouseBundle, XYZ} from '../warehouseTypes';

type Variant = 'A' | 'B';
type SavedPose = {node: THREE.Object3D; position: THREE.Vector3; quaternion: THREE.Quaternion; scale: THREE.Vector3};
const owners = new WeakSet<THREE.Scene>();
const axisY = new THREE.Vector3(0, 1, 0);
const unit = new THREE.Vector3(1, 1, 1);
const speed = .8;
const stopSeconds = 2;
const routes = [
    {id: 'DEMO_FLEET_01', operator: 'DEMO_OPERATOR_01', arc: 'v3:vehicle:edge:0209', from: [6, 0, 42], to: [6, 0, 48]},
    {id: 'DEMO_FLEET_02', operator: 'DEMO_OPERATOR_02', arc: 'v3:vehicle:edge:0213', from: [6, 0, 58], to: [6, 0, 64]},
    {id: 'DEMO_FLEET_03', operator: 'DEMO_OPERATOR_03', arc: 'v3:vehicle:edge:0221', from: [138, 0, 42], to: [138, 0, 48]},
    {id: 'DEMO_FLEET_04', operator: 'DEMO_OPERATOR_04', arc: 'v3:vehicle:edge:0225', from: [138, 0, 58], to: [138, 0, 64]},
    {id: 'DEMO_FLEET_05', operator: 'DEMO_OPERATOR_05', arc: 'v3:vehicle:edge:0263', from: [28, 0, 67], to: [48, 0, 67]},
] as const;
type FleetRoute = typeof routes[number];

function need(value: unknown, message: string): asserts value {
    if (!value) throw Error(message);
}
function time(variant: Variant, at: number) {
    need((variant === 'A' || variant === 'B') && typeof at === 'number' && Number.isFinite(at) && at >= 0, 'INVALID_TWIN_FLEET_TIME_OR_VARIANT');
}
function pose(position: XYZ, yaw: number) {
    return new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromAxisAngle(axisY, yaw), unit);
}
function save(root: THREE.Object3D) {
    const rows: SavedPose[] = [];
    root.traverse(node => rows.push({node, position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone()}));
    return rows;
}
function restore(rows: SavedPose[]) {
    for (const row of rows) {
        row.node.position.copy(row.position);
        row.node.quaternion.copy(row.quaternion);
        row.node.scale.copy(row.scale);
    }
}

class FleetPreparation {
    readonly roots: THREE.Object3D[] = [];
    private readonly materials = new Map<THREE.Material, THREE.Material>();
    private readonly swept: THREE.Box3[] = [];
    private readonly fixed: THREE.Box3[];
    private readonly actorHomes: XYZ[];
    private readonly sourceVehicle: THREE.Object3D;
    private readonly sourceWalker: THREE.Object3D;

    constructor(readonly scene: THREE.Scene, private readonly bundle: WarehouseBundle, layoutPlan: WarehouseLayoutPlan) {
        need(
            bundle.source_kind === 'visual_fixture' && bundle.engine_operation === false &&
            bundle.registry.workers.length === 24 && bundle.registry.vehicles.length === 2,
            'TWIN_FLEET_SOURCE_REQUIRED',
        );
        need(
            layoutPlan.source_kind === 'visual_fixture' && layoutPlan.engine_operation === false &&
            /^[a-f0-9]{64}$/.test(layoutPlan.plan_sha256) && Array.isArray(layoutPlan.fixed_obstacles),
            'TWIN_FLEET_VALIDATED_B_REQUIRED',
        );
        const sourceVehicle = scene.getObjectByName('vehicle__FL02');
        const sourceDriver = sourceVehicle?.getObjectByName('actor__F02');
        const sourceWalker = scene.getObjectByName('actor__S02');
        need(
            sourceVehicle && sourceDriver && sourceWalker &&
            sourceDriver.userData.assignment === 'seated_existing_actor' &&
            sourceDriver.position.distanceTo(new THREE.Vector3(0, .29, -.615)) < 1e-7,
            'TWIN_FLEET_NATIVE_PROTOTYPES_REQUIRED',
        );
        need(
            sourceVehicle.getWorldScale(new THREE.Vector3()).distanceTo(unit) < 1e-9 &&
            sourceWalker.getWorldScale(new THREE.Vector3()).distanceTo(unit) < 1e-9,
            'TWIN_FLEET_NATIVE_SCALE_REQUIRED',
        );
        scene.updateMatrixWorld(true);
        this.sourceVehicle = sourceVehicle;
        this.sourceWalker = sourceWalker;
        this.fixed = [
            ...bundle.layout.modules.map(module => module.outer_bounds_world),
            ...layoutPlan.modules.map(module => module.outer_bounds_world),
            ...layoutPlan.fixed_obstacles.map(obstacle => obstacle.bounds),
        ].map(box => new THREE.Box3(new THREE.Vector3(...box.min), new THREE.Vector3(...box.max)));
        this.actorHomes = layoutPlan.actor_homes.map(actor => actor.position_world);
    }
    private greenMaterial(material: THREE.Material) {
        if (!['V3_Worker_RoleVest', 'V3_Worker_RoleHeadwear'].includes(material.name)) return material;
        if (!this.materials.has(material)) {
            need(material instanceof THREE.MeshStandardMaterial, 'TWIN_FLEET_NATIVE_UNIFORM_REQUIRED');
            const owned = material.clone();
            owned.color.set('#2AA56A');
            this.materials.set(material, owned);
        }
        return this.materials.get(material)!;
    }
    private green(root: THREE.Object3D) {
        root.traverse(node => {
            node.userData.visual_extra = true;
            if (!(node instanceof THREE.Mesh)) return;
            node.material = Array.isArray(node.material)
                ? node.material.map(material => this.greenMaterial(material))
                : this.greenMaterial(node.material);
        });
    }
    private clear(box: THREE.Box3) {
        need(
            box.min.x >= 0 && box.min.z >= 0 && box.max.x <= 144 && box.max.z <= 72 &&
            this.fixed.every(obstacle => !box.intersectsBox(obstacle)),
            'TWIN_FLEET_ROUTE_OBSTRUCTED',
        );
        need(this.actorHomes.every(point =>
            new THREE.Vector3(...point).distanceTo(box.clampPoint(new THREE.Vector3(...point), new THREE.Vector3())) >= .6
        ), 'TWIN_FLEET_SOURCE_POST_OBSTRUCTED');
        need(this.swept.every(previous => !box.intersectsBox(previous)), 'TWIN_FLEET_EXTRA_ROUTES_OVERLAP');
        this.swept.push(box);
    }
    private vehiclePrototype(route: FleetRoute) {
        const root = this.sourceVehicle.clone(true);
        root.name = 'vehicle__' + route.id;
        root.position.set(0, 0, 0);
        root.quaternion.identity();
        root.userData = {
            semanticKind: 'demo-vehicle', semanticId: route.id, visual_extra: true,
            source_prototype_id: 'FL02', asset_id: 'forklift', source_kind: 'visual_fixture', engine_operation: false,
        };
        const driver = root.getObjectByName('actor__F02')!;
        driver.name = 'actor__' + route.operator;
        driver.userData = {
            semanticKind: 'demo-actor', semanticId: route.operator, visual_extra: true,
            source_prototype_id: 'F02', asset_id: 'worker-base', workerRole: 'forklift_driver',
            visual_uniform: 'green', source_kind: 'visual_fixture', engine_operation: false,
        };
        this.green(root);
        this.roots.push(root);
        root.updateMatrixWorld(true);
        return {root, driver};
    }
    private sourceRoute(route: FleetRoute) {
        const arc = this.bundle.layout.vehicle.arcs.find(candidate => candidate.arc_id === route.arc);
        need(arc && arc.fields.geometry && (arc.fields.geometry as {kind: string}).kind === 'line', 'TWIN_FLEET_SOURCE_STRAIGHT_REQUIRED');
        const start = sampleVehicleArc(arc, 0), end = sampleVehicleArc(arc, 1);
        const a = new THREE.Vector3(...start.position), delta = new THREE.Vector3(...end.position).sub(a);
        const from = new THREE.Vector3(...route.from), to = new THREE.Vector3(...route.to);
        const u0 = from.clone().sub(a).dot(delta) / delta.lengthSq();
        const u1 = to.clone().sub(a).dot(delta) / delta.lengthSq();
        need(
            u0 >= 0 && u1 <= 1 && u1 > u0 &&
            a.clone().addScaledVector(delta, u0).distanceTo(from) < 1e-7 &&
            a.clone().addScaledVector(delta, u1).distanceTo(to) < 1e-7,
            'TWIN_FLEET_SOURCE_SUBSEGMENT_REQUIRED',
        );
        return {arc, start, from, to, u0, u1};
    }
    prepareVehicle(route: FleetRoute, index: number) {
        const {root, driver} = this.vehiclePrototype(route);
        const bounds = new THREE.Box3().setFromObject(root);
        const {arc, start, from, to, u0, u1} = this.sourceRoute(route);
        const sweep = bounds.clone().applyMatrix4(pose([...route.from], start.yaw_rad));
        sweep.union(bounds.clone().applyMatrix4(pose([...route.to], start.yaw_rad)));
        this.clear(sweep.expandByScalar(.25));
        const headLocal = root.worldToLocal(driver.getObjectByName('joint__head')!.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0, .55, 0)));
        const joints = new Map<string, THREE.Object3D>();
        for (const name of ['joint__wheel_front_L', 'joint__wheel_front_R', 'joint__wheel_rear_L', 'joint__wheel_rear_R', 'joint__rear_steer_L', 'joint__rear_steer_R']) {
            const joint = root.getObjectByName(name);
            need(joint, 'TWIN_FLEET_NATIVE_WHEELS_REQUIRED');
            joints.set(name, joint);
        }
        return {route, root, arc, u0, u1, stroke: from.distanceTo(to) * Math.PI / (2 * speed), offset: index * 3, saved: save(root), joints, headLocal};
    }
    prepareWalker() {
        const root = this.sourceWalker.clone(true);
        root.name = 'actor__DEMO_WALKER_01';
        root.userData = {
            semanticKind: 'demo-actor', semanticId: 'DEMO_WALKER_01', visual_extra: true,
            source_prototype_id: 'S02', asset_id: 'worker-base', workerRole: 'shipper',
            visual_uniform: 'green', source_kind: 'visual_fixture', engine_operation: false,
        };
        root.position.set(98, 0, 69);
        root.rotation.set(0, Math.PI / 2, 0);
        this.green(root);
        this.roots.push(root);
        root.updateMatrixWorld(true);
        this.clear(new THREE.Box3(new THREE.Vector3(91.25, 0, 66.25), new THREE.Vector3(112.75, 2.1, 69.75)));
        const rig = deriveNativeWorkerGaitRig(root);
        const path: XYZ[] = [[98, 0, 69], [112, 0, 69], [112, 0, 67], [92, 0, 67], [92, 0, 69], [98, 0, 69]];
        const fixed = this.fixed.map(box => ({min: box.min.toArray() as XYZ, max: box.max.toArray() as XYZ}));
        const walk = compileNativeWorkerGait(rig, path, Math.PI / 2, 1.2, fixed);
        const headLocal = root.worldToLocal(root.getObjectByName('joint__head')!.getWorldPosition(new THREE.Vector3())).add(new THREE.Vector3(0, .55, 0));
        return {root, walk, saved: save(root), period: walk.duration_s + 2, headLocal};
    }
    dispose() {
        for (const root of this.roots) root.removeFromParent();
        for (const material of this.materials.values()) material.dispose();
    }
}
type FleetVehicle = ReturnType<FleetPreparation['prepareVehicle']>;
function vehicleFrame(vehicle: FleetVehicle, at: number) {
    const period = 2 * vehicle.stroke + 2 * stopSeconds;
    const cut = (at + vehicle.offset) % period;
    let fraction = 0, velocity = 0, phase: 'forward' | 'reverse' | 'stopped' = 'stopped';
    if (cut < vehicle.stroke) {
        fraction = (1 - Math.cos(Math.PI * cut / vehicle.stroke)) / 2;
        velocity = speed * Math.sin(Math.PI * cut / vehicle.stroke);
        phase = 'forward';
    } else if (cut < vehicle.stroke + stopSeconds) {
        fraction = 1;
    } else if (cut < 2 * vehicle.stroke + stopSeconds) {
        const elapsed = cut - vehicle.stroke - stopSeconds;
        fraction = (1 + Math.cos(Math.PI * elapsed / vehicle.stroke)) / 2;
        velocity = -speed * Math.sin(Math.PI * elapsed / vehicle.stroke);
        phase = 'reverse';
    }
    const state = sampleVehicleArc(vehicle.arc, vehicle.u0 + (vehicle.u1 - vehicle.u0) * fraction);
    return {
        id: vehicle.route.id, operator_id: vehicle.route.operator, phase,
        position: state.position, yaw_rad: state.yaw_rad, speed_m_s: velocity,
        rear_steer_rad: state.rear_steer_rad, wheel_angles_rad: state.wheel_angles_rad,
        source_arc_id: vehicle.arc.arc_id,
    };
}
function applyVehicle(vehicle: FleetVehicle, frame: ReturnType<typeof vehicleFrame>) {
    restore(vehicle.saved);
    vehicle.root.position.fromArray(frame.position);
    vehicle.root.rotation.set(0, frame.yaw_rad, 0);
    for (const side of ['L', 'R'] as const) {
        vehicle.joints.get('joint__wheel_front_' + side)!.rotateX(frame.wheel_angles_rad[side === 'L' ? 'front_L' : 'front_R']);
        vehicle.joints.get('joint__wheel_rear_' + side)!.rotateX(frame.wheel_angles_rad[side === 'L' ? 'rear_L' : 'rear_R']);
        vehicle.joints.get('joint__rear_steer_' + side)!.rotation.y = frame.rear_steer_rad[side];
    }
}

class FleetController {
    private readonly vehicles: FleetVehicle[];
    private readonly walker: ReturnType<FleetPreparation['prepareWalker']>;
    private disposed = false;
    private current: ReturnType<FleetController['sample']> | null = null;

    constructor(private readonly preparation: FleetPreparation) {
        owners.add(preparation.scene);
        try {
            this.vehicles = routes.map((route, index) => preparation.prepareVehicle(route, index));
            this.walker = preparation.prepareWalker();
            for (const root of preparation.roots) preparation.scene.add(root);
            this.apply('A', 0);
        } catch (error) {
            preparation.dispose();
            owners.delete(preparation.scene);
            throw error;
        }
    }
    private live() {
        need(!this.disposed, 'TWIN_FLEET_DISPOSED');
    }
    private sample(variant: Variant, at: number) {
        this.live();
        time(variant, at);
        const cut = at % this.walker.period;
        const walking = this.walker.walk.sample(Math.min(cut, this.walker.walk.duration_s));
        return {
            variant, at_s: at, vehicles: this.vehicles.map(vehicle => vehicleFrame(vehicle, at)),
            walker: {
                id: 'DEMO_WALKER_01', position: walking.root_world, yaw_rad: walking.yaw_rad,
                phase: walking.stage, speed_m_s: walking.speed_m_s, joint_rotations: walking.joint_rotations,
            },
            visual_extra: true, source_kind: 'visual_fixture', engine_operation: false, completed_jobs: 0,
        };
    }
    apply(variant: Variant, at: number) {
        const state = this.sample(variant, at);
        this.vehicles.forEach((vehicle, index) => applyVehicle(vehicle, state.vehicles[index]));
        const root = this.walker.root;
        restore(this.walker.saved);
        root.position.fromArray(state.walker.position);
        root.rotation.set(0, state.walker.yaw_rad, 0);
        for (const [name, rotation] of Object.entries(state.walker.joint_rotations)) root.getObjectByName(name)!.quaternion.fromArray(rotation);
        for (const item of this.preparation.roots) {
            item.traverse(node => node.updateMatrix());
            item.updateWorldMatrix(true, true);
        }
        this.current = state;
        return structuredClone(state);
    }
    summary() {
        return {
            original_vehicles: 2, extra_vehicles: 5, vehicles: 7,
            original_people: 24, extra_people: 6, people: 30,
            source_kind: 'visual_fixture', visual_extra: true, engine_operation: false,
            operational_admission: false, completed_jobs: 0, affects_packing_jobs: false,
            max_vehicle_speed_m_s: speed, braking_stop_s: stopSeconds,
            walker_period_s: this.walker.period,
            extra_actor_ids: [...routes.map(route => route.operator), 'DEMO_WALKER_01'],
            extra_vehicle_ids: routes.map(route => route.id),
            route_basis: 'separate_disjoint_subsegments_of_source_straight_vehicle_arcs',
            worker_basis: 'native_unloaded_gait_and_original_seated_driver_hierarchy',
        };
    }
    actorPosition(variant: Variant, at: number, id: string): XYZ | null {
        const state = this.sample(variant, at);
        if (id === 'DEMO_WALKER_01') {
            return this.walker.headLocal.clone().applyMatrix4(pose(state.walker.position, state.walker.yaw_rad)).toArray() as XYZ;
        }
        const index = this.vehicles.findIndex(vehicle => vehicle.route.operator === id);
        return index < 0 ? null : this.vehicles[index].headLocal.clone().applyMatrix4(pose(state.vehicles[index].position, state.vehicles[index].yaw_rad)).toArray() as XYZ;
    }
    snapshot() {
        this.live();
        return structuredClone(this.current!);
    }
    dispose() {
        if (this.disposed) return;
        this.preparation.dispose();
        owners.delete(this.preparation.scene);
        this.disposed = true;
    }
    publicAPI() {
        return Object.freeze({
            apply: this.apply.bind(this), actorPosition: this.actorPosition.bind(this),
            dynamicRoots: Object.freeze(this.preparation.roots), summary: this.summary.bind(this),
            snapshot: this.snapshot.bind(this), dispose: this.dispose.bind(this),
        });
    }
}

/** Common, separately labelled native visual extras. No source staffing or jobs change. */
export function createTwinFleetTraffic(scene: THREE.Scene, bundle: WarehouseBundle, layoutPlan: WarehouseLayoutPlan) {
    need(!owners.has(scene), 'TWIN_FLEET_SCENE_BUSY');
    return new FleetController(new FleetPreparation(scene, bundle, layoutPlan)).publicAPI();
}

export type TwinFleetTraffic = ReturnType<typeof createTwinFleetTraffic>;
