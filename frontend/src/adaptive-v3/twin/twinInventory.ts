import {decodeV3Table} from '../warehouseAdapter';
import {createWarehouseCargo, type BoundCargo} from '../warehouseCargo';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {InitialCargo, V3Record, WarehouseBundle, WarehouseLayout, WarehouseModule, WarehouseSlot, XYZ} from '../warehouseTypes';

export type TwinInventoryMode = 'source530' | 'populated-demo-v1';
export type TwinInventoryCargo = BoundCargo & {
  origin: 'source' | 'populated-demo';
  prototype_hu_id: string;
};
export type TwinInventoryCounts = {
  handling_units: number;
  source_handling_units: number;
  added_handling_units: number;
  quantity_units: number;
  gross_mass_kg: number;
  occupied_slots: number;
  usable_slots: number;
  excluded_slots: number;
  empty_usable_slots: number;
  sku_count: number;
};
export type TwinInventoryVariant = {
  cargo: readonly TwinInventoryCargo[];
  additions: readonly TwinInventoryCargo[];
  counts: TwinInventoryCounts;
};
export type TwinInventory = {
  mode: TwinInventoryMode;
  comparison_scope: 'source530' | 'capacity_fill_visual';
  variants: {A: TwinInventoryVariant; B: TwinInventoryVariant};
  reserved_empty_slots: readonly {slot_id: string; reason: string}[];
};

const WORKFLOW_EMPTY = [
  {address: 'STANDARD_E:016', reason: 'R01 receiving destination and original comparison fragile-crate destination'},
  {address: 'HEAVY_E:001', reason: 'Original pallet inbound destination'},
  {address: 'HEAVY_E:002', reason: 'Additional IBC inbound destination'},
  {address: 'HEAVY_E:007', reason: 'Additional heavy-box inbound and original comparison destination'},
  {address: 'HEAVY_E:008', reason: 'Original comparison IBC destination'},
  {address: 'HEAVY_E:009', reason: 'Standalone pallet-transfer destination'},
  {address: 'LONG_E:006', reason: 'Original comparison LONG destination'},
  {address: 'FLEX_W:003', reason: 'Recorded relocation destination'},
  {address: 'FLEX_W:004', reason: 'Original comparison small-carton destination'},
].map(row => ({slot_id: `v3:slot:${row.address}:L1:B1`, reason: row.reason}));

function requireValue(value: unknown, reason: string): asserts value {
  if (!value) throw Error(reason);
}
function freeze<T>(value: T): T {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}
const compareId = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
const near = (a: readonly number[], b: readonly number[]) => a.length === b.length && a.every((value, index) => Math.abs(value - b[index]) < 1e-7);
const volume = (cargo: InitialCargo) => cargo.dimensions_xyz_m.reduce((total, value) => total * value, 1);

function relocate(point: XYZ, from: WarehouseModule, to: WarehouseModule): XYZ {
  const dx = point[0] - from.world_pos[0], dz = point[2] - from.world_pos[2];
  const c = Math.cos(from.yaw_rad), s = Math.sin(from.yaw_rad);
  const x = c * dx - s * dz, z = s * dx + c * dz;
  return [to.world_pos[0] + Math.cos(to.yaw_rad) * x + Math.sin(to.yaw_rad) * z, to.world_pos[1] + point[1] - from.world_pos[1], to.world_pos[2] - Math.sin(to.yaw_rad) * x + Math.cos(to.yaw_rad) * z];
}
function rigidBounds(box: WarehouseModule['outer_bounds_world'], from: WarehouseModule, to: WarehouseModule) {
  const corners: XYZ[] = [];
  for (const x of [box.min[0], box.max[0]]) for (const y of [box.min[1], box.max[1]]) for (const z of [box.min[2], box.max[2]]) corners.push(relocate([x, y, z], from, to));
  return {min: [0, 1, 2].map(index => Math.min(...corners.map(point => point[index]))), max: [0, 1, 2].map(index => Math.max(...corners.map(point => point[index])))};
}

function plannedLayout(bundle: WarehouseBundle, plan: WarehouseLayoutPlan | null): WarehouseLayout {
  if (!plan) return bundle.layout;
  requireValue(plan.source_kind === 'visual_fixture' && plan.engine_operation === false && plan.source_layout_content_hash === bundle.layout.layout_content_hash, 'INVENTORY_LAYOUT_SOURCE_MISMATCH');
  const sourceModules = new Map(bundle.layout.modules.map(module => [module.module_id, module]));
  const sourceSlots = new Map(bundle.layout.slots.map(slot => [slot.slot_id, slot]));
  const modules = plan.modules.map(module => {
    const prototype = sourceModules.get(module.prototype_module_id);
    requireValue(prototype && prototype.family === module.family && module.world_pos.every(Number.isFinite) && Number.isFinite(module.yaw_rad), 'INVENTORY_LAYOUT_MODULE_INVALID');
    requireValue(module.is_new ? !sourceModules.has(module.module_id) : sourceModules.has(module.module_id), 'INVENTORY_LAYOUT_MODULE_IDENTITY');
    const next = {...prototype, module_id: module.module_id, world_pos: [...module.world_pos] as XYZ, yaw_rad: module.yaw_rad, outer_bounds_world: structuredClone(module.outer_bounds_world)};
    const expected = rigidBounds(prototype.outer_bounds_world, prototype, next);
    requireValue(near(next.outer_bounds_world.min, expected.min) && near(next.outer_bounds_world.max, expected.max), 'INVENTORY_LAYOUT_MODULE_BOUNDS');
    return next;
  });
  const moduleIndex = new Map(modules.map((module, index) => [module.module_id, index]));
  requireValue(moduleIndex.size === modules.length && [...sourceModules.keys()].every(id => moduleIndex.has(id)), 'INVENTORY_LAYOUT_DUPLICATE_OR_MISSING_MODULE');
  const slots = plan.slots.map(slot => {
    const prototype = sourceSlots.get(slot.source_slot_id), index = moduleIndex.get(slot.module_id);
    requireValue(prototype && index !== undefined, 'INVENTORY_LAYOUT_SLOT_INVALID');
    const sourceModule = bundle.layout.modules[prototype.module_index], targetModule = plan.modules[index];
    requireValue(sourceModule.module_id === targetModule.prototype_module_id && slot.prototype_module_id === sourceModule.module_id, 'INVENTORY_LAYOUT_SLOT_PROTOTYPE');
    const expectedBounds = rigidBounds(prototype.usable_bounds_world, sourceModule, modules[index]);
    requireValue(near(slot.bin_anchor_world, relocate(prototype.bin_anchor, sourceModule, modules[index])) && near(slot.usable_bounds_world.min, expectedBounds.min) && near(slot.usable_bounds_world.max, expectedBounds.max), 'INVENTORY_LAYOUT_SUPPORT_FRAME');
    requireValue(slot.is_new === targetModule.is_new && (slot.is_new ? !sourceSlots.has(slot.slot_id) : slot.slot_id === prototype.slot_id), 'INVENTORY_LAYOUT_SLOT_IDENTITY');
    requireValue(slot.reserve_only === prototype.reserve_only && slot.retrieval_blocked === prototype.retrieval_blocked && slot.max_payload_kg === prototype.max_payload_kg && slot.max_handling_units === prototype.max_handling_units && JSON.stringify(slot.usable_dimensions_xyz_m) === JSON.stringify(prototype.usable_dimensions_xyz_m), 'INVENTORY_LAYOUT_SLOT_POLICY_CHANGED');
    return {...prototype, slot_id: slot.slot_id, module_index: index, bin_anchor: [...slot.bin_anchor_world] as XYZ, usable_bounds_world: structuredClone(slot.usable_bounds_world), usable_dimensions_xyz_m: [...slot.usable_dimensions_xyz_m] as XYZ};
  });
  requireValue(new Set(slots.map(slot => slot.slot_id)).size === slots.length && [...sourceSlots.keys()].every(id => slots.some(slot => slot.slot_id === id)), 'INVENTORY_LAYOUT_DUPLICATE_OR_MISSING_SLOT');
  const storage = bundle.layout.data.storage as V3Record;
  const table = storage.slots as {columns: string[]; rows: unknown[][]};
  const policies = new Map(decodeV3Table(table).map(row => [row.slot_id as string, row]));
  const rows = slots.map((slot, index) => {
    const policy = {...policies.get(plan.slots[index].source_slot_id)!, ...slot};
    return table.columns.map(column => policy[column as keyof typeof policy]);
  });
  // This transient placement view is passed only to cargo admission. It does not
  // replace the source bundle or lend the old route graph to the B layout.
  return {...bundle.layout, layout_content_hash: plan.plan_sha256, modules, slots, data: {...bundle.layout.data, storage: {...storage, slots: {...table, rows}}}};
}

function additionalCargo(template: InitialCargo, slot: WarehouseSlot, module: WarehouseModule, clearance: number): InitialCargo {
  const dimensions = template.dimensions_xyz_m;
  const shift = slot.usable_dimensions_xyz_m[2] / 2 - clearance - dimensions[2] / 2;
  const position: XYZ = [slot.bin_anchor[0] + Math.sin(module.yaw_rad) * shift, slot.bin_anchor[1], slot.bin_anchor[2] + Math.cos(module.yaw_rad) * shift];
  const delta = position.map((value, index) => value - module.world_pos[index]);
  const c = Math.cos(module.yaw_rad), s = Math.sin(module.yaw_rad);
  return {
    ...template,
    handling_unit_id: `v3:HU:populated-demo-v1:${slot.slot_id}`,
    lot_id: `v3:lot:populated-demo-v1:${template.sku_id}`,
    dimensions_xyz_m: [...dimensions],
    location: {
      kind: 'storage_slot', slot_id: slot.slot_id, module_id: module.module_id,
      placement: {
        centre_local_xyz_m: [c * delta[0] - s * delta[2], delta[1] + dimensions[1] / 2, s * delta[0] + c * delta[2]],
        bottom_y_m: delta[1], top_y_m: delta[1] + dimensions[1], support_gap_m: 0,
      },
    },
  };
}

function populate(bundle: WarehouseBundle, layout: WarehouseLayout, mode: TwinInventoryMode): {stock: InitialCargo[]; prototypes: Map<string, string>} {
  const stock = [...bundle.fixture.inputs.initial_stock];
  const prototypes = new Map(stock.map(cargo => [cargo.handling_unit_id, cargo.handling_unit_id]));
  if (mode === 'source530') return {stock, prototypes};
  const occupied = new Set(stock.map(cargo => cargo.location.slot_id));
  const reserved = new Set(WORKFLOW_EMPTY.map(row => row.slot_id));
  const policies = new Map(decodeV3Table((layout.data.storage as V3Record).slots).map(row => [row.slot_id as string, row]));
  const definitions = (layout.data.storage as V3Record).module_definitions as Record<string, {module_payload: number}>;
  const moduleMass = new Map<string, number>();
  for (const cargo of stock) moduleMass.set(cargo.location.module_id, (moduleMass.get(cargo.location.module_id) ?? 0) + cargo.gross_mass_kg);
  const templates = [...stock].sort((a, b) => volume(b) - volume(a) || compareId(a.handling_unit_id, b.handling_unit_id));
  const vacancies = layout.slots.filter(slot => !slot.reserve_only && !slot.retrieval_blocked && !occupied.has(slot.slot_id) && !reserved.has(slot.slot_id)).sort((a, b) => compareId(a.slot_id, b.slot_id));
  for (const slot of vacancies) {
    const policy = policies.get(slot.slot_id)!, module = layout.modules[slot.module_index];
    const clearance = policy.clearance_each_side_m as number;
    requireValue(Number.isFinite(clearance) && clearance >= 0 && slot.max_handling_units === 1, 'INVENTORY_PLACEMENT_POLICY_INVALID');
    const template = templates.find(cargo =>
      (policy.allowed_cargo_archetype_ids as string[]).includes(cargo.archetype_id) &&
      (policy.allowed_orientation_ids as string[]).includes('upright_xyz_in_module') &&
      cargo.orientation_id === 'upright_xyz' && cargo.model_scale_factor === 1 &&
      cargo.dimensions_xyz_m.every((size, index) => size + 2 * clearance <= slot.usable_dimensions_xyz_m[index] + 1e-9) &&
      cargo.gross_mass_kg <= slot.max_payload_kg &&
      (moduleMass.get(module.module_id) ?? 0) + cargo.gross_mass_kg <= definitions[module.family].module_payload + 1e-9,
    );
    requireValue(template, 'NO_COMPATIBLE_DEMO_CARGO:' + slot.slot_id);
    const cargo = additionalCargo(template, slot, module, clearance);
    requireValue(!prototypes.has(cargo.handling_unit_id), 'INVENTORY_DUPLICATE_HU');
    stock.push(cargo);
    prototypes.set(cargo.handling_unit_id, template.handling_unit_id);
    moduleMass.set(module.module_id, (moduleMass.get(module.module_id) ?? 0) + cargo.gross_mass_kg);
  }
  return {stock, prototypes};
}

function variant(bundle: WarehouseBundle, layout: WarehouseLayout, plan: WarehouseLayoutPlan | null, mode: TwinInventoryMode): TwinInventoryVariant {
  const {stock, prototypes} = populate(bundle, layout, mode);
  const admissionBundle = freeze({...bundle, layout, fixture: {...bundle.fixture, fixture_id: `${bundle.fixture.fixture_id}:${mode}`, inputs: {...bundle.fixture.inputs, initial_stock: stock}}});
  const original = new Set(bundle.fixture.inputs.initial_stock.map(cargo => cargo.handling_unit_id));
  const frames = new Map(plan?.HUs.map(frame => [frame.handling_unit_id, frame]) ?? []);
  if (plan) requireValue(frames.size === original.size && frames.size === plan.HUs.length && [...original].every(id => frames.has(id)), 'INVENTORY_LAYOUT_HU_IDENTITIES');
  const cargo: TwinInventoryCargo[] = createWarehouseCargo(admissionBundle).snapshot().map(bound => {
    const isSource = original.has(bound.handling_unit_id);
    const frame = frames.get(bound.handling_unit_id);
    if (frame) {
      requireValue(frame.source_slot_id === bound.cargo.location.slot_id && frame.target_slot_id === frame.source_slot_id && frame.target_module_id === bound.cargo.location.module_id && near(frame.position_world, bound.position) && Math.abs(frame.yaw_rad - bound.yaw_rad) < 1e-8, 'INVENTORY_LAYOUT_SOURCE_HU_POSE');
    }
    return {...bound, ...(frame ? {position: [...frame.position_world] as XYZ, yaw_rad: frame.yaw_rad} : {}), origin: isSource ? 'source' : 'populated-demo', prototype_hu_id: prototypes.get(bound.handling_unit_id)!};
  });
  const additions = cargo.filter(row => row.origin === 'populated-demo');
  const usable = layout.slots.filter(slot => !slot.reserve_only && !slot.retrieval_blocked).length;
  return freeze({
    cargo, additions,
    counts: {
      handling_units: cargo.length, source_handling_units: original.size, added_handling_units: additions.length,
      quantity_units: cargo.reduce((sum, row) => sum + row.cargo.quantity_units, 0),
      gross_mass_kg: cargo.reduce((sum, row) => sum + row.cargo.gross_mass_kg, 0),
      occupied_slots: new Set(cargo.map(row => row.destination.kind === 'storage_slot' ? row.destination.slot_id : '')).size,
      usable_slots: usable, excluded_slots: layout.slots.length - usable, empty_usable_slots: usable - cargo.length,
      sku_count: new Set(cargo.map(row => row.cargo.sku_id)).size,
    },
  });
}

/** Explicit capacity-fill stock. Original objects and recorded source authority
 * stay in the caller's immutable bundle, while this model owns its extra HUs. */
export function createTwinInventory(bundle: WarehouseBundle, layoutPlan: WarehouseLayoutPlan | null, mode: TwinInventoryMode = 'populated-demo-v1'): TwinInventory {
  requireValue(mode === 'source530' || mode === 'populated-demo-v1', 'INVALID_INVENTORY_MODE');
  requireValue(Object.isFrozen(bundle) && bundle.fixture.inputs.initial_stock.length === 530 && bundle.fixture.inputs.initial_stock.every(Object.isFrozen), 'IMMUTABLE_SOURCE530_REQUIRED');
  createWarehouseCargo(bundle);
  const occupied = new Set(bundle.fixture.inputs.initial_stock.map(cargo => cargo.location.slot_id));
  requireValue(WORKFLOW_EMPTY.every(row => !occupied.has(row.slot_id) && bundle.layout.slots.some(slot => slot.slot_id === row.slot_id && !slot.reserve_only && !slot.retrieval_blocked)), 'INVENTORY_WORKFLOW_EMPTY_UNAVAILABLE');
  const B = plannedLayout(bundle, layoutPlan);
  return freeze({mode, comparison_scope: mode === 'source530' ? 'source530' : 'capacity_fill_visual', variants: {A: variant(bundle, bundle.layout, null, mode), B: variant(bundle, B, layoutPlan, mode)}, reserved_empty_slots: WORKFLOW_EMPTY.map(row => ({...row}))});
}