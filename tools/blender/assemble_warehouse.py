"""Assemble the complete editable design warehouse from the eight asset GLBs.

Run in a fresh background Blender after the individual asset exports. The
canonical layout is authoritative for all rack, SKU and service coordinates.
The two picker poses illustrate the design and are not simulation history.
"""
from pathlib import Path
import json
import math

import bpy

from asset_common import ROOT, VERSION, xyz, reset, group, finish


ASSETS = (
    'environment', 'rack-bay', 'crate', 'picker-cart',
    'packing-station', 'buffer-pallet', 'forklift', 'ibc-tote',
)


def _load_prototype(asset_id):
    path = ROOT / 'frontend' / 'public' / 'models' / (asset_id + '.glb')
    if not path.is_file():
        raise FileNotFoundError('Export the asset before assembly: ' + str(path))
    previous = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = set(bpy.data.objects) - previous
    if not imported:
        raise RuntimeError('Asset import produced no objects: ' + asset_id)
    container = group('__prototype__' + asset_id)
    container['source_asset'] = asset_id
    for obj in imported:
        if obj.parent not in imported:
            world = obj.matrix_world.copy()
            obj.parent = container
            obj.matrix_world = world
    return container


def _clone(prototype, name, parent, position=(0, 0, 0), heading=0):
    # Object copies preserve shared mesh/material datablocks. Parent mappings and
    # local matrices retain the imported glTF hierarchy without a second axis turn.
    originals = [prototype] + list(prototype.children_recursive)
    mapping = {}
    for original in originals:
        copy = original.copy()
        bpy.context.collection.objects.link(copy)
        mapping[original] = copy
        copy.name = name if original == prototype else name + '::' + original.name
    for original, copy in mapping.items():
        copy.parent = mapping.get(original.parent, parent if original == prototype else None)
        copy.matrix_parent_inverse = original.matrix_parent_inverse.copy()
        copy.matrix_basis = original.matrix_basis.copy()
    root = mapping[prototype]
    root.location = xyz(position)
    # Runtime Y-up heading corresponds to Blender Z-up heading.
    root.rotation_mode = 'XYZ'
    root.rotation_euler = (0, 0, math.radians(heading))
    root['layout_version'] = VERSION
    return root


def _anchor(name, parent, relative_position, role, **properties):
    obj = group(name)
    obj.parent = parent
    obj.location = xyz(relative_position)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .12
    obj['role'] = role
    for key, value in properties.items():
        obj[key] = value
    return obj


def _difference(point, origin):
    return tuple(float(point[index]) - float(origin[index]) for index in range(3))


def build():
    layout_path = ROOT / 'contracts' / 'layout.example.json'
    layout = json.loads(layout_path.read_text(encoding='utf-8'))
    if layout['layout_version'] != VERSION:
        raise ValueError('Layout version differs from asset helper: ' + layout['layout_version'])
    slots = layout['slots']
    identifiers = [slot['slot_id'] for slot in slots]
    if len(slots) != 20 or len(set(identifiers)) != 20:
        raise ValueError('Warehouse design requires exactly twenty unique slot IDs.')
    nodes = {node['node_id']: node['pos'] for node in layout['nodes']}
    for slot in slots:
        if slot['pick_node_id'] not in nodes:
            raise ValueError('Missing pick node for ' + slot['slot_id'])
    prototypes = {asset_id: _load_prototype(asset_id) for asset_id in ASSETS}

    root = group('warehouse_root')
    root['role'] = 'warehouse_design'
    root['layout_version'] = layout['layout_version']
    root['units'] = 'metres'
    root['coordinate_system'] = 'right_handed_Y_up'
    root['floor_size_m'] = [20., 18.]
    root['slot_count'] = 20
    root['pose_purpose'] = 'static_design_assembly_not_simulation_history'

    environment = _clone(prototypes['environment'], 'environment_root__ENV', root)
    environment['role'] = 'cutaway_warehouse_environment'
    # The environment GLB already contains the exact 20 x 18m floor at Y=0.
    # Do not add an overlapping floor or reposition its wall/door architecture.

    for slot in slots:
        slot_id = slot['slot_id']
        rack_position = slot['rack_center']
        wrapper = group('slot__' + slot_id)
        wrapper.parent = root
        wrapper.location = xyz(rack_position)
        wrapper['slot_id'] = slot_id
        wrapper['layout_version'] = layout['layout_version']
        wrapper['role'] = 'selectable_slot'
        wrapper['pick_node_id'] = slot['pick_node_id']
        wrapper['active_shelf_top_m'] = .675
        short_id = slot_id.removeprefix('S_')
        rack = _clone(prototypes['rack-bay'], 'rackbay__' + short_id, wrapper)
        rack['role'] = 'rack_bay'
        rack['slot_id'] = slot_id
        carton = _clone(prototypes['crate'], 'box__' + slot_id, wrapper,
                        _difference(slot['bin_anchor'], rack_position))
        carton['role'] = 'sku_container'
        carton['slot_id'] = slot_id
        # Only the active shelf receives a carton. Upper decorative decks stay empty.
        _anchor('anchor_pick__' + slot_id, wrapper,
                _difference(nodes[slot['pick_node_id']], rack_position),
                'pick_anchor', slot_id=slot_id, node_id=slot['pick_node_id'])
        _anchor('anchor_box__' + slot_id, wrapper,
                _difference(slot['bin_anchor'], rack_position),
                'box_anchor', slot_id=slot_id)

    pack_position = (9, 0, .6)
    pack = _clone(prototypes['packing-station'], 'pack_station__PACK', root, pack_position)
    pack['role'] = 'packing_station'
    _anchor('anchor_service__N_PACK', pack,
            _difference(nodes[layout['pack_node_id']], pack_position),
            'service_anchor', node_id=layout['pack_node_id'])

    buffer_position = (18, 0, .8)
    buffer = _clone(prototypes['buffer-pallet'], 'buffer_bed__BUFFER', root, buffer_position)
    buffer['role'] = 'temporary_transfer_buffer'
    _anchor('anchor_service__N_BUFFER', buffer,
            _difference(nodes[layout['buffer_node_id']], buffer_position),
            'service_anchor', node_id=layout['buffer_node_id'])
    _anchor('anchor_box__BUFFER', buffer,
            _difference(layout['buffer_bin_anchor'], buffer_position),
            'box_anchor')
    # Buffer starts empty; it is not a twenty-first permanent slot.

    for picker_id, position, heading in (
        ('P1', (3, 0, 6), 0),
        ('P2', (11, 0, 8), 180),
    ):
        picker = _clone(prototypes['picker-cart'], 'picker_root__' + picker_id,
                        root, position, heading)
        picker['role'] = 'picker_with_cart'
        picker['picker_id'] = picker_id
        picker['pose_purpose'] = 'illustrative_static_design_pose'
        picker['logical_start_node_id'] = layout['pack_node_id']

    forklift = _clone(prototypes['forklift'], 'forklift__STATIC', root,
                      (18.2, 0, 10.4), 180)
    forklift['role'] = 'parked_non_simulated_set_dressing'
    ibc = _clone(prototypes['ibc-tote'], 'ibc_tote__STATIC', root, (18.2, 0, 5.3))
    ibc['role'] = 'non_simulated_set_dressing'

    # Remove prototype objects after instancing; their linked mesh datablocks are
    # retained by the instances, so saved source has no duplicate hidden warehouse.
    for prototype in prototypes.values():
        for obj in list(prototype.children_recursive) + [prototype]:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()

    # Direct scene verification before finish saves the editable assembly.
    expected = {'slot__' + slot_id for slot_id in identifiers}
    actual = {obj.name for obj in root.children_recursive if obj.get('role') == 'selectable_slot'}
    if actual != expected:
        raise RuntimeError('Slot hierarchy does not match the canonical layout.')
    for slot in slots:
        for prefix, expected_point in (
            ('anchor_box__', slot['bin_anchor']),
            ('anchor_pick__', nodes[slot['pick_node_id']]),
        ):
            anchor = bpy.data.objects[prefix + slot['slot_id']]
            if (anchor.matrix_world.translation - xyz(expected_point)).length > .00001:
                raise RuntimeError('Anchor coordinate drift: ' + anchor.name)
    for name, expected_point in (
        ('anchor_service__N_PACK', nodes[layout['pack_node_id']]),
        ('anchor_service__N_BUFFER', nodes[layout['buffer_node_id']]),
        ('anchor_box__BUFFER', layout['buffer_bin_anchor']),
    ):
        anchor = bpy.data.objects[name]
        if (anchor.matrix_world.translation - xyz(expected_point)).length > .00001:
            raise RuntimeError('Service anchor coordinate drift: ' + name)
    return root


if __name__ == '__main__':
    reset()
    finish('warehouse', build(), batch_runtime=False)

