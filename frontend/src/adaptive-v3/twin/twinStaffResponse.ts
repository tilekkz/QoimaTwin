import * as THREE from 'three';
import {createWarehouseRouter, type RoutePolicy} from '../warehouseRouting';
import {compileNativeWorkerGait, deriveNativeWorkerGaitRig, type CompiledWorkerGait, type WorkerGaitPose} from '../warehouseWorkerGait';
import {sampleWarehouseManualGripPose} from '../warehouseManualGripPose';
import type {WarehouseBundle, XYZ} from '../warehouseTypes';

type Variant = 'A' | 'B';
type StaffId = 'K01' | 'K02' | 'K03' | 'K05' | 'K06';
type Station = 'PK01' | 'PK02' | 'PK03' | 'PK05' | 'PK06';
type Phase = 'walking_to_help' | 'working' | 'waiting' | 'returning' | 'break_walk' | 'break' | 'break_return' | 'end_hold';
type LocalPose = {
    node: THREE.Object3D;
    position: THREE.Vector3;
    quaternion: THREE.Quaternion;
    scale: THREE.Vector3;
    matrix: THREE.Matrix4;
    auto: boolean;
    worldAuto: boolean;
};
type Track = {
    id: StaffId;
    root: THREE.Object3D;
    saved: LocalPose[];
    home: XYZ;
    homeStation: Station;
    targetStation: Station | null;
    headLocal: THREE.Vector3;
    depart: number;
    arrive: number;
    returnDepart: number;
    returnArrive: number;
    stationary?: true;
    outbound?: CompiledWorkerGait;
    returning?: CompiledWorkerGait;
    outboundArcIds: string[];
    returnArcIds: string[];
};
type StaffFrame = {
    gait: WorkerGaitPose | null;
    phase: Phase;
    available: boolean;
    station: Station | null;
    sourcePost: boolean;
};
export type TwinStaffActivity = {
    actor_id: StaffId;
    role: 'packer';
    phase: Phase;
    position: XYZ;
    head_position: XYZ;
    station_id: Station | null;
    available: boolean;
    source_post_available: boolean;
    message: string;
};

const HELPER_RETURN = 260;
const BREAK_RETURN = 320;
const owners = new WeakSet<THREE.Scene>();
const Y = new THREE.Vector3(0, 1, 0);
const UNIT = new THREE.Vector3(1, 1, 1);
const definitions = [
    {id: 'K01', from: 'PK01', to: 'v3:service:PK05', target: 'PK05', depart: 46},
    {id: 'K02', from: 'PK02', to: 'v3:service:PK06', target: 'PK06', depart: 48},
    {id: 'K05', from: 'PK05', to: 'v3:cart-stop:PK04', target: null, depart: 30},
    {id: 'K06', from: 'PK06', to: 'v3:service:CART_PARK', target: null, depart: 32},
] as const;

function need(value: unknown, reason: string): asserts value {
    if (!value) throw Error(reason);
}
function checkTime(variant: Variant, time: number) {
    need((variant === 'A' || variant === 'B') && typeof time === 'number' && Number.isFinite(time) && time >= 0, 'INVALID_TWIN_STAFF_TIME_OR_VARIANT');
}
function save(root: THREE.Object3D): LocalPose[] {
    const rows: LocalPose[] = [];
    root.traverse(node => rows.push({
        node, position: node.position.clone(), quaternion: node.quaternion.clone(),
        scale: node.scale.clone(), matrix: node.matrix.clone(),
        auto: node.matrixAutoUpdate, worldAuto: node.matrixWorldAutoUpdate,
    }));
    return rows;
}
function restore(rows: LocalPose[]) {
    for (const row of rows) {
        row.node.position.copy(row.position);
        row.node.quaternion.copy(row.quaternion);
        row.node.scale.copy(row.scale);
        row.node.matrix.copy(row.matrix);
        row.node.matrixAutoUpdate = row.auto;
        row.node.matrixWorldAutoUpdate = row.worldAuto;
    }
}
function worldPose(position: XYZ, yaw: number) {
    return new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromAxisAngle(Y, yaw), UNIT);
}
function headLocal(root: THREE.Object3D) {
    return root.worldToLocal(root.getObjectByName('joint__head')!.getWorldPosition(new THREE.Vector3())).add(new THREE.Vector3(0, .55, 0));
}
function fixedBounds(bundle: WarehouseBundle) {
    const conveyor = bundle.layout.data.conveyor as {
        physical_modules: {floor_bounds_xz: {min: number[]; max: number[]}}[];
        packing_stations: {table_origin: XYZ; table_dimensions_m: XYZ}[];
    };
    const fixed = bundle.layout.modules.map(module => module.outer_bounds_world);
    for (const module of conveyor.physical_modules) {
        fixed.push({min: [module.floor_bounds_xz.min[0], 0, module.floor_bounds_xz.min[1]], max: [module.floor_bounds_xz.max[0], 8, module.floor_bounds_xz.max[1]]});
    }
    for (const station of conveyor.packing_stations) {
        const [x, , z] = station.table_origin;
        const [width, height, depth] = station.table_dimensions_m;
        fixed.push({min: [x - width / 2, 0, z - depth / 2], max: [x + width / 2, height, z + depth / 2]});
    }
    return fixed;
}
function prepareContext(scene: THREE.Scene, bundle: WarehouseBundle, policy: RoutePolicy) {
    need(bundle.source_kind === 'visual_fixture' && bundle.engine_operation === false && bundle.registry.workers.length === 24, 'TWIN_STAFF_SOURCE_REQUIRED');
    const actors = new Map<string, THREE.Object3D>();
    scene.updateMatrixWorld(true);
    scene.traverse(node => {
        if (node.userData.semanticKind !== 'actor') return;
        const id = node.userData.semanticId;
        need(typeof id === 'string' && !actors.has(id), 'TWIN_STAFF_UNIQUE_ACTORS_REQUIRED');
        actors.set(id, node);
    });
    need(actors.size === 24 && bundle.registry.workers.every(worker => actors.has(worker.actor_id)), 'TWIN_STAFF_EXACT24_REQUIRED');
    return {
        bundle, actors, router: createWarehouseRouter(bundle, policy),
        nodes: new Map(bundle.layout.walk.nodes.map(node => [node.node_id, node])),
        arcs: new Map(bundle.layout.walk.arcs.map(arc => [arc.arc_id, arc])),
        fixed: fixedBounds(bundle),
    };
}
type StaffContext = ReturnType<typeof prepareContext>;
function route(context: StaffContext, id: StaffId, from: string, to: string) {
    const plan = context.router.route({
        source_kind: 'visual_fixture', engine_operation: false,
        mode: 'pedestrian', actor_id: id, vehicle_id: null, cargo_archetype_id: null,
        from_node_id: from, to_node_id: to, service_port_id: null, closed_arc_ids: [],
    });
    need(plan.ok, 'TWIN_STAFF_ROUTE_REFUSED:' + id + ':' + plan.reason);
    const points: XYZ[] = [[...context.nodes.get(from)!.world_pos]];
    let current = from;
    for (const arcId of plan.arc_ids) {
        const arc = context.arcs.get(arcId)!;
        need(context.bundle.layout.walk.nodes[arc.from_node_index].node_id === current, 'TWIN_STAFF_ROUTE_CHAIN_REQUIRED');
        const next = context.bundle.layout.walk.nodes[arc.to_node_index];
        points.push([...next.world_pos]);
        current = next.node_id;
    }
    need(current === to && points.every(point =>
        point[0] >= 55 && point[0] <= 132 && point[2] >= 6.1 - 1e-9 && point[2] <= 10 + 1e-9
    ), 'TWIN_STAFF_SHARED_APRON_REQUIRED');
    return {points, arcIds: [...plan.arc_ids]};
}
function sourcePacker(context: StaffContext, id: StaffId, home: XYZ) {
    const root = context.actors.get(id)!;
    const profile = context.bundle.profiles.profiles.find(row => row.worker_id === id)!;
    need(profile.allowed_roles.includes('packer') && profile.walk_speed_m_s === 1.2 && profile.skill_levels.packer === 1, 'TWIN_STAFF_SOURCE_PACKER_REQUIRED');
    need(
        root.userData.asset_id === 'worker-base' &&
        root.getWorldScale(new THREE.Vector3()).distanceTo(UNIT) < 1e-9 &&
        root.getWorldPosition(new THREE.Vector3()).distanceTo(new THREE.Vector3(...home)) < 1e-7,
        'TWIN_STAFF_ORIGINAL_POST_REQUIRED',
    );
    return {root, profile};
}
function walkingTrack(context: StaffContext, definition: typeof definitions[number]): Track {
    const homeNode = 'v3:service:' + definition.from;
    const home = context.nodes.get(homeNode)!.world_pos;
    const {root, profile} = sourcePacker(context, definition.id, home);
    const saved = save(root), rig = deriveNativeWorkerGaitRig(root);
    const outwardRoute = route(context, definition.id, homeNode, definition.to);
    const returnRoute = route(context, definition.id, definition.to, homeNode);
    const yaw = new THREE.Euler().setFromQuaternion(root.getWorldQuaternion(new THREE.Quaternion()), 'YXZ').y;
    const outbound = compileNativeWorkerGait(rig, outwardRoute.points, yaw, profile.walk_speed_m_s, context.fixed);
    const returning = compileNativeWorkerGait(rig, returnRoute.points, outbound.sample(outbound.duration_s).yaw_rad, profile.walk_speed_m_s, context.fixed);
    const returnDepart = definition.target ? HELPER_RETURN : BREAK_RETURN;
    return {
        id: definition.id, root, saved, home: [...home], homeStation: definition.from,
        targetStation: definition.target, headLocal: headLocal(root), depart: definition.depart,
        arrive: definition.depart + outbound.duration_s, returnDepart,
        returnArrive: returnDepart + returning.duration_s, outbound, returning,
        outboundArcIds: outwardRoute.arcIds, returnArcIds: returnRoute.arcIds,
    };
}
function stationaryTrack(context: StaffContext): Track {
    const home = context.nodes.get('v3:service:PK03')!.world_pos;
    const {root} = sourcePacker(context, 'K03', home);
    return {
        id: 'K03', root, saved: save(root), home: [...home], homeStation: 'PK03',
        targetStation: 'PK03', headLocal: headLocal(root), stationary: true,
        depart: 0, arrive: 0, returnDepart: Number.MAX_VALUE, returnArrive: 0,
        outboundArcIds: [], returnArcIds: [],
    };
}
function activityMessage(phase: Phase, station: Station | null, track: Track) {
    if (phase === 'walking_to_help') return 'Иду на ' + track.targetStation;
    if (phase === 'working') return 'Работаю на ' + station;
    if (phase === 'returning') return 'Возвращаюсь на ' + track.homeStation;
    if (phase === 'break_walk') return 'Освобождаю пост';
    if (phase === 'break') return 'Перерыв';
    if (phase === 'break_return') return 'Возвращаюсь с перерыва';
    return station ? 'Готов на ' + station : 'Ожидаю';
}
function workPose(track: Track, time: number) {
    const from = track.targetStation ? track.arrive : 0;
    const until = track.targetStation ? track.returnDepart : 30;
    const weight = Math.max(0, Math.min(1, (time - from) / .75, (until - time) / .75));
    const pose = sampleWarehouseManualGripPose(3 + .35 * (.5 - .5 * Math.cos((time - from) * Math.PI * 2 / 7.5)));
    for (const part of ['upper_arm', 'forearm', 'hand']) {
        for (const side of ['L', 'R']) {
            const node = track.root.getObjectByName('joint__' + part + '_' + side)!;
            const angles = pose.eulers['joint__' + part + '_L'].map((value, index) => side === 'R' && index > 0 ? -value : value);
            const target = new THREE.Quaternion().setFromEuler(new THREE.Euler(angles[0], angles[1], angles[2], 'XYZ'));
            node.quaternion.slerp(target, weight);
        }
    }
}

class StaffController {
    private readonly tracks: Track[] = [];
    readonly breakClear_s: Readonly<{PK05: number; PK06: number}>;
    readonly stationReady_s: Readonly<{PK05: number; PK06: number}>;
    readonly duration_s: number;
    private disposed = false;
    private current: ReturnType<StaffController['sample']> | null = null;

    constructor(private readonly scene: THREE.Scene, context: StaffContext) {
        owners.add(scene);
        try {
            for (const definition of definitions) this.tracks.push(walkingTrack(context, definition));
            this.tracks.push(stationaryTrack(context));
            this.breakClear_s = Object.freeze({PK05: this.tracks[2].arrive, PK06: this.tracks[3].arrive});
            this.stationReady_s = Object.freeze({PK05: Math.max(this.tracks[0].arrive, this.breakClear_s.PK05), PK06: Math.max(this.tracks[1].arrive, this.breakClear_s.PK06)});
            need(this.tracks[0].arrive >= this.breakClear_s.PK05 && this.tracks[1].arrive >= this.breakClear_s.PK06, 'TWIN_STAFF_BREAK_MUST_CLEAR_BEFORE_HELPER');
            this.duration_s = Math.max(...this.tracks.map(track => track.returnArrive));
        } catch (error) {
            this.restoreTracks();
            owners.delete(scene);
            throw error;
        }
    }
    private live() {
        need(!this.disposed, 'TWIN_STAFF_DISPOSED');
    }
    private restoreTracks() {
        for (const track of this.tracks) {
            restore(track.saved);
            track.root.updateWorldMatrix(true, true);
        }
    }
    private frame(track: Track, variant: Variant, time: number): StaffFrame {
        const helper = track.targetStation !== null;
        const state: StaffFrame = {gait: null, phase: 'waiting', available: true, station: track.homeStation, sourcePost: true};
        if (track.stationary || helper && variant === 'A') return state;
        if (time < track.depart) {
            if (!helper && time >= 30) return {...state, phase: 'break_walk', available: false, station: null, sourcePost: false};
            return state;
        }
        if (time >= track.returnArrive) return {...state, phase: 'end_hold'};
        if (time < track.arrive) {
            return {gait: track.outbound!.sample(time - track.depart), phase: helper ? 'walking_to_help' : 'break_walk', available: false, station: null, sourcePost: false};
        }
        if (time < track.returnDepart) {
            return {gait: track.outbound!.sample(track.outbound!.duration_s), phase: helper ? 'waiting' : 'break', available: helper, station: track.targetStation, sourcePost: false};
        }
        return {gait: track.returning!.sample(time - track.returnDepart), phase: helper ? 'returning' : 'break_return', available: false, station: null, sourcePost: false};
    }
    private activity(track: Track, variant: Variant, time: number, workingStations: readonly string[]): TwinStaffActivity {
        const state = this.frame(track, variant, time);
        const position = state.gait?.root_world ?? track.home;
        const yaw = state.gait?.yaw_rad ?? new THREE.Euler().setFromQuaternion(track.saved[0].quaternion, 'YXZ').y;
        const head = track.headLocal.clone().applyMatrix4(worldPose(position, yaw));
        const working = state.available && state.station !== null && workingStations.includes(state.station) && state.phase !== 'end_hold';
        const phase = working ? 'working' : state.phase;
        return {
            actor_id: track.id, role: 'packer', phase, position: [...position],
            head_position: head.toArray() as XYZ, station_id: state.station,
            available: state.available, source_post_available: state.sourcePost,
            message: activityMessage(phase, state.station, track),
        };
    }
    sample(variant: Variant, time: number, workingStations: readonly string[] = []) {
        this.live();
        checkTime(variant, time);
        need(Array.isArray(workingStations) && workingStations.every(value => typeof value === 'string'), 'TWIN_STAFF_WORKING_STATIONS_REQUIRED');
        const workers = this.tracks.map(track => this.activity(track, variant, time, workingStations));
        return {
            variant, at_s: time, source_kind: 'visual_fixture' as const,
            engine_operation: false as const, operational_admission: false as const,
            source_worker_count: 24 as const, workers,
            working_count: workers.filter(worker => worker.phase === 'working').length,
            hotpost_staff_count: workers.filter(worker => worker.available && (worker.station_id === 'PK05' || worker.station_id === 'PK06')).length,
            stationReady_s: this.stationReady_s, breakClear_s: this.breakClear_s, duration_s: this.duration_s,
            assumptions: {
                no_other_PK01_PK02_jobs: true, helper_work_until_s: HELPER_RETURN,
                common_break_return_depart_s: BREAK_RETURN, original_S02_patrol_disabled_in_demo: true,
                work_pose_basis: 'existing_original542_arm_channels_with_neutral_palm_roll', material_or_force_admission: false,
            },
        };
    }
    apply(variant: Variant, time: number, workingStations: readonly string[] = []) {
        const sampled = this.sample(variant, time, workingStations);
        for (const track of this.tracks) {
            restore(track.saved);
            const state = this.frame(track, variant, time);
            if (state.gait) {
                const matrix = worldPose(state.gait.root_world, state.gait.yaw_rad);
                if (track.root.parent) matrix.premultiply(track.root.parent.matrixWorld.clone().invert());
                matrix.decompose(track.root.position, track.root.quaternion, track.root.scale);
                for (const [name, quaternion] of Object.entries(state.gait.joint_rotations)) track.root.getObjectByName(name)!.quaternion.fromArray(quaternion);
            }
            if (sampled.workers.find(worker => worker.actor_id === track.id)!.phase === 'working') workPose(track, time);
            track.root.traverse(node => node.updateMatrix());
            track.root.updateWorldMatrix(true, true);
        }
        this.current = sampled;
        return structuredClone(sampled);
    }
    actorActivity(variant: Variant, time: number, id: string, workingStations: readonly string[] = []) {
        return this.sample(variant, time, workingStations).workers.find(worker => worker.actor_id === id) ?? null;
    }
    actorPosition(variant: Variant, id: string, time: number) {
        return this.sample(variant, time).workers.find(worker => worker.actor_id === id)?.head_position ?? null;
    }
    snapshot() {
        this.live();
        return structuredClone(this.current ?? this.sample('A', 0));
    }
    dispose() {
        if (this.disposed) return;
        this.restoreTracks();
        owners.delete(this.scene);
        this.disposed = true;
    }
    publicAPI() {
        return Object.freeze({
            apply: this.apply.bind(this), sample: this.sample.bind(this),
            actorActivity: this.actorActivity.bind(this), actorPosition: this.actorPosition.bind(this),
            dynamicRoots: Object.freeze(this.tracks.map(track => track.root)),
            stationReady_s: this.stationReady_s, breakClear_s: this.breakClear_s, duration_s: this.duration_s,
            timings: Object.freeze(this.tracks.filter(track => !track.stationary).map(track => Object.freeze({
                actor_id: track.id, depart_s: track.depart, arrival_s: track.arrive,
                return_depart_s: track.returnDepart, return_arrival_s: track.returnArrive,
                outbound_arc_ids: [...track.outboundArcIds], return_arc_ids: [...track.returnArcIds],
            }))),
            snapshot: this.snapshot.bind(this), dispose: this.dispose.bind(this),
        });
    }
}

/** Existing packers in a declared finite visual staffing episode. */
export async function createTwinStaffResponse(scene: THREE.Scene, bundle: WarehouseBundle, policy: RoutePolicy) {
    need(!owners.has(scene), 'TWIN_STAFF_SCENE_BUSY');
    return new StaffController(scene, prepareContext(scene, bundle, policy)).publicAPI();
}

export type TwinStaffResponse = Awaited<ReturnType<typeof createTwinStaffResponse>>;
