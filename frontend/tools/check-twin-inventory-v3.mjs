/** Real source fixtures, deterministic stock placement and existing cargo admission. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputIndex = process.argv.indexOf('--out');
const output = outputIndex < 0 ? await mkdtemp(path.join(tmpdir(), 'qoima-twin-inventory-')) : path.resolve(process.argv[outputIndex + 1]);
if (outputIndex >= 0) await mkdir(output, {recursive: false});
const cache = path.join(output, 'compiled');
await mkdir(path.join(cache, 'twin'), {recursive: true});
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const pins = {};
for (const name of ['workerRegistry', 'workerProfiles', 'warehouseAdapter', 'workerRoleAssignment', 'warehouseLayoutPlan', 'warehouseCargo', 'warehouseCargoHolders', 'twin/twinInventory']) {
  const filename = path.join(frontend, 'src/adaptive-v3', name + '.ts');
  const bytes = await readFile(filename);
  pins[filename] = hash(bytes);
  let code = ts.transpileModule(bytes.toString(), {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText;
  code = code.replace(/from (['"])(\.{1,2}\/[^'"]+)\1/g, (_, quote, specifier) => `from ${quote}${specifier}.mjs${quote}`);
  await writeFile(path.join(cache, name + '.mjs'), code, {flag: 'wx'});
}
const texts = {};
for (const [name, relative] of Object.entries({fixture: 'data/v3/warehouse-fixture-v3.json', layout: 'data/adaptive-v3/layout-manifest.json', registry: 'data/v3/worker-registry-v3.json', profiles: 'data/v3/worker-profiles-v3.json'})) {
  const filename = path.join(frontend, 'public', relative);
  const bytes = await readFile(filename);
  pins[filename] = hash(bytes);
  texts[name] = bytes.toString();
}
const {adaptWarehouseV3, decodeV3Table} = await import(pathToFileURL(path.join(cache, 'warehouseAdapter.mjs')));
const {createDenseWarehouseLayoutPlan} = await import(pathToFileURL(path.join(cache, 'warehouseLayoutPlan.mjs')));
const {createTwinInventory} = await import(pathToFileURL(path.join(cache, 'twin/twinInventory.mjs')));
const bundle = await adaptWarehouseV3(texts);
const layout = await createDenseWarehouseLayoutPlan(bundle, texts);
const beforeBundle = JSON.stringify(bundle), beforePlan = JSON.stringify(layout);
const original = new Map(bundle.fixture.inputs.initial_stock.map(row => [row.handling_unit_id, row]));
const inventory = createTwinInventory(bundle, layout);
assert.equal(inventory.variants.A.counts.handling_units, 579, 'A capacity fill must add49 compatible HUs while retaining9 workflow addresses');
assert.equal(inventory.variants.B.counts.handling_units, 899, 'B must populate320 added SMALL slots and the same49 source vacancies');
assert.equal(inventory.comparison_scope, 'capacity_fill_visual');
assert.equal(inventory.mode, 'populated-demo-v1');
assert.equal(inventory.reserved_empty_slots.length, 9);
assert.equal(new Set(inventory.reserved_empty_slots.map(row => row.slot_id)).size, 9);
const expectedReserved = ['STANDARD_E:016', 'HEAVY_E:001', 'HEAVY_E:002', 'HEAVY_E:007', 'HEAVY_E:008', 'HEAVY_E:009', 'LONG_E:006', 'FLEX_W:003', 'FLEX_W:004'].map(id => 'v3:slot:' + id + ':L1:B1').sort();
assert.deepEqual(inventory.reserved_empty_slots.map(row => row.slot_id).sort(), expectedReserved);
assert(inventory.reserved_empty_slots.every(row => typeof row.reason === 'string' && row.reason.length > 0));
const rawSlots = new Map(decodeV3Table(bundle.layout.data.storage.slots).map(row => [row.slot_id, row]));
const modules = new Map(bundle.layout.modules.map(row => [row.module_id, row]));
const Bslots = new Map(layout.slots.map(row => [row.slot_id, row]));
const Bmodules = new Map(layout.modules.map(row => [row.module_id, row]));
const reserved = new Set(expectedReserved);
const originalPoses = new Map(layout.HUs.map(row => [row.handling_unit_id, row]));
for (const copy of ['A', 'B']) {
  const variant = inventory.variants[copy], seen = new Set(), seenHU = new Set(), moduleMass = new Map();
  assert.equal(variant.counts.source_handling_units, 530);
  assert.equal(variant.counts.added_handling_units, copy === 'A' ? 49 : 369);
  assert.equal(variant.additions.length, copy === 'A' ? 49 : 369);
  assert.equal(variant.counts.usable_slots, copy === 'A' ? 588 : 908);
  assert.equal(variant.counts.excluded_slots, 188);
  assert.equal(variant.counts.empty_usable_slots, 9);
  assert.equal(variant.counts.occupied_slots, variant.cargo.length);
  assert.equal(variant.counts.quantity_units, copy === 'A' ? 13432 : 21112);
  assert(Math.abs(variant.counts.gross_mass_kg - (copy === 'A' ? 10079.55 : 10380.35)) < 1e-7);
  assert.equal(variant.counts.sku_count, 200);
  assert(Object.isFrozen(variant) && Object.isFrozen(variant.cargo) && Object.isFrozen(variant.additions) && Object.isFrozen(variant.counts));
  for (const row of variant.cargo) {
    assert.equal(row.destination.kind, 'storage_slot');
    const id = row.destination.slot_id;
    assert(!seen.has(id) && !seenHU.has(row.handling_unit_id) && !reserved.has(id));
    seen.add(id); seenHU.add(row.handling_unit_id);
    const slot = copy === 'A' ? bundle.layout.slots.find(slot => slot.slot_id === id) : Bslots.get(id);
    const policy = rawSlots.get(copy === 'A' ? id : slot.source_slot_id);
    assert(slot && policy && !slot.reserve_only && !slot.retrieval_blocked);
    const module = copy === 'A' ? bundle.layout.modules[slot.module_index] : Bmodules.get(slot.module_id);
    const sourceModule = modules.get(copy === 'A' ? module.module_id : module.prototype_module_id);
    const hu = row.cargo, template = original.get(row.prototype_hu_id);
    assert(template);
    assert.equal(row.handling_unit_id, hu.handling_unit_id);
    assert.equal(hu.model_scale_factor, 1); assert.equal(row.model_scale_factor, 1);
    assert.equal(hu.orientation_id, 'upright_xyz'); assert.equal(hu.location.placement.support_gap_m, 0);
    assert(policy.allowed_cargo_archetype_ids.includes(hu.archetype_id));
    assert(policy.allowed_orientation_ids.includes('upright_xyz_in_module'));
    assert(hu.dimensions_xyz_m.every((size, index) => size + 2 * policy.clearance_each_side_m <= slot.usable_dimensions_xyz_m[index] + 1e-9));
    assert(hu.gross_mass_kg <= slot.max_payload_kg);
    assert.equal(slot.max_handling_units, 1); assert.equal(policy.stacking_allowed, false);
    moduleMass.set(module.module_id, (moduleMass.get(module.module_id) ?? 0) + hu.gross_mass_kg);
    const anchor = copy === 'A' ? slot.bin_anchor : slot.bin_anchor_world;
    assert(Math.abs(row.position[1] - anchor[1]) < 1e-8);
    assert.equal(row.yaw_rad, module.yaw_rad);
    if (row.origin === 'source') {
      assert.strictEqual(hu, original.get(row.handling_unit_id));
      if (copy === 'B') assert.deepEqual(row.position, originalPoses.get(row.handling_unit_id).position_world);
    } else {
      assert.equal(row.origin, 'populated-demo');
      assert(!original.has(row.handling_unit_id));
      assert.deepEqual(hu.dimensions_xyz_m, template.dimensions_xyz_m);
      assert.equal(hu.gross_mass_kg, template.gross_mass_kg);
      assert.equal(hu.quantity_units, template.quantity_units);
      assert.equal(hu.sku_id, template.sku_id);
      assert.equal(hu.location.slot_id, id); assert.equal(hu.location.module_id, module.module_id);
    }
    assert(Object.isFrozen(row) && Object.isFrozen(hu));
    assert(sourceModule);
  }
  for (const [id, mass] of moduleMass) {
    const module = copy === 'A' ? modules.get(id) : Bmodules.get(id);
    assert(mass <= bundle.layout.data.storage.module_definitions[module.family].module_payload + 1e-9);
  }
}
const immutableExtra = inventory.variants.B.additions[0];
assert.throws(() => { immutableExtra.position[0] += 1; }, TypeError);
assert.throws(() => { immutableExtra.cargo.dimensions_xyz_m[0] += 1; }, TypeError);
assert.throws(() => { inventory.reserved_empty_slots[0].reason = 'changed'; }, TypeError);
const repeat = createTwinInventory(bundle, layout);
assert.deepEqual(inventory, repeat);
const source = createTwinInventory(bundle, layout, 'source530');
assert.equal(source.comparison_scope, 'source530');
for (const copy of ['A', 'B']) {
  assert.equal(source.variants[copy].cargo.length, 530);
  assert.equal(source.variants[copy].additions.length, 0);
  assert.equal(source.variants[copy].counts.quantity_units, 12256);
  assert(Math.abs(source.variants[copy].counts.gross_mass_kg - 9403.85) < 1e-7);
}
const flat = createTwinInventory(bundle, null);
assert.equal(flat.variants.A.cargo.length, 579); assert.equal(flat.variants.B.cargo.length, 579);
assert.deepEqual(flat.variants.A.additions.map(row => row.handling_unit_id), flat.variants.B.additions.map(row => row.handling_unit_id));
assert.throws(() => createTwinInventory(bundle, layout, 'random'), /MODE/);
const moved = structuredClone(layout); moved.HUs[0].position_world[0] += .01;
assert.throws(() => createTwinInventory(bundle, moved), /LAYOUT|POSE/);
const unblocked = structuredClone(layout), closed = unblocked.slots.find(slot => slot.reserve_only);
closed.reserve_only = false; closed.retrieval_blocked = false;
assert.throws(() => createTwinInventory(bundle, unblocked), /POLICY|LAYOUT/);
const shrunken = structuredClone(layout); shrunken.slots.find(slot => slot.is_new).usable_dimensions_xyz_m[0] = .1;
assert.throws(() => createTwinInventory(bundle, shrunken), /POLICY|LAYOUT|COMPATIBLE/);
const floating = structuredClone(layout); floating.slots.find(slot => slot.is_new).bin_anchor_world[1] += .1;
assert.throws(() => createTwinInventory(bundle, floating), /SUPPORT|LAYOUT/);
const badBounds = structuredClone(layout); badBounds.slots.find(slot => slot.is_new).usable_bounds_world.max[0] += .1;
assert.throws(() => createTwinInventory(bundle, badBounds), /SUPPORT|LAYOUT/);
const duplicates = structuredClone(layout); duplicates.slots[1].slot_id = duplicates.slots[0].slot_id;
assert.throws(() => createTwinInventory(bundle, duplicates), /DUPLICATE|LAYOUT/);
assert.equal(JSON.stringify(bundle), beforeBundle); assert.equal(JSON.stringify(layout), beforePlan);
assert.equal(bundle.fixture.inputs.initial_stock.length, 530);
for (const [filename, expected] of Object.entries(pins)) assert.equal(hash(await readFile(filename)), expected, 'Source bytes preserved ' + filename);
const report = {passed: true, A_HUs: 579, B_HUs: 899, original_HUs: 530, workflow_empty_slots: 9, excluded_each: 188, A_units: 13432, B_units: 21112, A_mass_kg: 10079.55, B_mass_kg: 10380.35, deterministic: true, source_objects_retained: true, source_and_plan_unchanged: true, source530_mode_verified: true, invalid_mode_and_layout_controls: 7, source_hashes: pins};
await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({passed: true, A_HUs: 579, B_HUs: 899, reserved: 9, original_HUs: 530}));