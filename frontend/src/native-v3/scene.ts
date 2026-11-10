import * as THREE from 'three';
import { createWarehouseCargo } from '../adaptive-v3/warehouseCargo';
import type { WarehouseBundle, V3Record } from '../adaptive-v3/warehouseTypes';
import { need, type ArmData } from './stream';
import type { Geometry, PlaybackFrame, XYZ } from './playback';
const COMMON = '47ea8d54101f63b7dd2f958a41174c716607019a6f43a7379d2b80b3f42b3f99';
const REGISTRY = '753452460289b494f9e59583091245a5f1c7d2e8a2bcd28c670e4a0f620c70ab';
const LAYOUT = '407642632968cbd0e3f5ce1879177921c6fb7daa3292ecf375938012a0de2b71';
const RAW_LAYOUT = 'eb8afaf677864983a326af6ca47f4f41fbbd6ba162613fbce078feff0128f7db';
const Y = new THREE.Vector3(0, 1, 0), UNIT = new THREE.Vector3(1, 1, 1);
const transform = (position: XYZ, yaw: number) => new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromAxisAngle(Y, yaw), UNIT);
/** This registration binds the saved common input to its original A geometry. */
export function nativeGeometry(bundle: WarehouseBundle, data: ArmData): Geometry {
    need(data.header.common_input_hash === COMMON && data.header.registry_common_hash === REGISTRY, 'Native source profile is not registered for this geometry');
    need(bundle.layout.layout_content_hash === LAYOUT && bundle.fixture.layout_ref.sha256 === RAW_LAYOUT, 'Native geometry source hash differs');
    const nodes = new Map(bundle.layout.walk.nodes.map(n => [n.node_id, n.world_pos]));
    const arcs = new Map(bundle.layout.walk.arcs.map(a => [a.arc_id, [bundle.layout.walk.nodes[a.from_node_index].node_id, bundle.layout.walk.nodes[a.to_node_index].node_id] as [
            string,
            string
        ]]));
    const slots = new Map(bundle.layout.slots.map(s => [s.slot_id, { position: [...s.bin_anchor] as XYZ, yaw: bundle.layout.modules[s.module_index].yaw_rad }]));
    const stock = createWarehouseCargo(bundle), initial = stock.snapshot();
    const moves = [...data.captures.flatMap(s => s.relocations), ...data.events.flatMap(e => e.relocation ? [e.relocation] : [])];
    for (const move of new Map(moves.map(r => [r.hu_id, r])).values()) {
        const source = initial.find(h => h.handling_unit_id === move.hu_id);
        need(source && source.destination.kind === 'storage_slot' && source.destination.slot_id === move.source_owner, 'Native HU source does not match registered stock');
        slots.set(move.source_owner, { position: source.position, yaw: source.yaw_rad });
        const admission = stock.apply([{ handling_unit_id: move.hu_id, destination: { kind: 'storage_slot', slot_id: move.destination_owner } }]);
        need(admission.ok, 'Native destination geometry refused ' + admission.reason);
        const target = stock.snapshot().find(h => h.handling_unit_id === move.hu_id)!;
        slots.set(move.destination_owner, { position: target.position, yaw: target.yaw_rad });
        stock.reset();
    }
    const conveyor = bundle.layout.data.conveyor as V3Record;
    const beltNodes = new Map((conveyor.nodes as V3Record[]).map(n => [n.node_id as string, n.world_pos as XYZ]));
    const edges = new Map((conveyor.edges as V3Record[]).map(e => [e.edge_id as string, { from: beltNodes.get(e.from_node_id as string)!, to: beltNodes.get(e.to_node_id as string)!, ...(e.path_kind === 'arc' ? { centre: e.centre as XYZ, radius: e.radius_m as number, startAngle: e.theta_start_rad as number, endAngle: e.theta_end_rad as number } : {}) }]));
    return { nodes, arcs, slots, edges };
}
type Part = {
    mesh: THREE.InstancedMesh;
    index: number;
    matrix: THREE.Matrix4;
    world: THREE.Matrix4;
};
type Home = {
    node: THREE.Object3D;
    position: THREE.Vector3;
    quaternion: THREE.Quaternion;
    visible: boolean;
};
class NativeLayer {
    private readonly actors = new Map<string, THREE.Object3D>();
    private readonly parts = new Map<string, Part[]>();
    private readonly source;
    private readonly actorHomes: Home[] = [];
    private readonly group = new THREE.Group();
    private readonly geometry = new THREE.BoxGeometry(.6, .3, .4);
    private readonly tote = new THREE.MeshStandardMaterial({ color: '#1d6579', roughness: .7 });
    private readonly parcel = new THREE.MeshStandardMaterial({ color: '#c78b42', roughness: .85 });
    private readonly carriers = new Map<string, THREE.Mesh>();
    private readonly changed = new Set<Part>();
    private disposed = false;
    constructor(private readonly scene: THREE.Scene, private readonly bundle: WarehouseBundle) {
        this.source = new Map(createWarehouseCargo(bundle).snapshot().map(h => [h.handling_unit_id, h]));
        scene.updateMatrixWorld(true);
        scene.traverse(node => this.index(node));
        this.group.name = 'recorded-native-carriers';
        scene.add(this.group);
    }
    private index(node: THREE.Object3D) {
        if (node.userData.semanticKind === 'actor') {
            this.actors.set(node.userData.semanticId, node);
            this.actorHomes.push({ node, position: node.position.clone(), quaternion: node.quaternion.clone(), visible: node.visible });
        }
        if (!(node instanceof THREE.InstancedMesh) || node.userData.semanticKind !== 'HU')
            return;
        const ids = node.userData.semanticIds as string[];
        ids.forEach((id, index) => {
            const matrix = new THREE.Matrix4();
            node.getMatrixAt(index, matrix);
            const list = this.parts.get(id) ?? [];
            list.push({ mesh: node, index, matrix, world: node.matrixWorld.clone().multiply(matrix) });
            this.parts.set(id, list);
        });
    }
    private restoreCargo() {
        const meshes = new Set<THREE.InstancedMesh>();
        for (const part of this.changed) {
            part.mesh.setMatrixAt(part.index, part.matrix);
            meshes.add(part.mesh);
        }
        this.changed.clear();
        return meshes;
    }
    private applyCargo(frame: PlaybackFrame) {
        const meshes = this.restoreCargo();
        for (const move of frame.relocations) {
            const base = this.source.get(move.hu_id);
            need(base, 'Unknown native HU instance');
            const delta = transform(move.position, move.yaw).multiply(transform(base.position, base.yaw_rad).invert());
            for (const part of this.parts.get(move.hu_id) ?? []) {
                part.mesh.setMatrixAt(part.index, part.mesh.matrixWorld.clone().invert().multiply(delta).multiply(part.world));
                this.changed.add(part);
                meshes.add(part.mesh);
            }
        }
        for (const mesh of meshes) {
            mesh.instanceMatrix.needsUpdate = true;
            mesh.computeBoundingBox();
            mesh.computeBoundingSphere();
        }
    }
    private applyActors(frame: PlaybackFrame) {
        for (const row of frame.actors) {
            const node = this.actors.get(row.actor_id);
            need(node, 'Unknown native actor instance');
            const seated = this.bundle.registry.workers.find(w => w.actor_id === row.actor_id)?.assigned_vehicle_id;
            node.visible = !seated;
            if (!seated) {
                node.position.fromArray(row.position);
                node.rotation.y = row.yaw;
            }
        }
    }
    private applyCarriers(frame: PlaybackFrame) {
        for (const mesh of this.carriers.values())
            mesh.visible = false;
        for (const row of frame.carriers) {
            let mesh = this.carriers.get(row.job_id);
            if (!mesh) {
                mesh = new THREE.Mesh(this.geometry, this.tote);
                mesh.name = 'recorded-carrier-' + row.job_id;
                mesh.castShadow = true;
                this.group.add(mesh);
                this.carriers.set(row.job_id, mesh);
            }
            mesh.visible = true;
            mesh.material = row.payload_id.startsWith('P') ? this.parcel : this.tote;
            mesh.position.set(row.position[0], row.position[1] + .15, row.position[2]);
            mesh.rotation.y = row.yaw;
            mesh.userData = { job_id: row.job_id, hu_id: row.hu_id, payload_id: row.payload_id, presentation_glyph: true };
        }
    }
    apply(frame: PlaybackFrame) {
        need(!this.disposed, 'Native display layer is disposed');
        this.applyCargo(frame);
        this.applyActors(frame);
        this.applyCarriers(frame);
        this.scene.updateMatrixWorld(true);
    }
    dispose() {
        if (this.disposed)
            return;
        for (const mesh of this.restoreCargo()) {
            mesh.instanceMatrix.needsUpdate = true;
            mesh.computeBoundingBox();
            mesh.computeBoundingSphere();
        }
        for (const home of this.actorHomes) {
            home.node.position.copy(home.position);
            home.node.quaternion.copy(home.quaternion);
            home.node.visible = home.visible;
        }
        this.group.removeFromParent();
        this.geometry.dispose();
        this.tote.dispose();
        this.parcel.dispose();
        this.carriers.clear();
        this.disposed = true;
    }
}
/** Display matrices never enter the fixture custody or physical-admission API. */
export function createNativeLayer(scene: THREE.Scene, bundle: WarehouseBundle) {
    return new NativeLayer(scene, bundle);
}
