"""Canonical v2 design assembly, preserving linked reusable mesh geometry.

This is a static initial-design asset, not a replay or evidence of completed
operations. Business roots retain contract positions; explicitly tagged child
render offsets only separate coincident people and put packers beside tables.
"""
import json
import math

import bpy

from v2_common import ROOT, VERSION, xyz, reset, material, group, box, finish


PROTOTYPES = {
    'environment-shell': 'v2', 'rack-low': 'v2', 'dock': 'v2',
    'worker-low': 'v2', 'driver': 'v2', 'picking-cart': 'v2',
    'conveyor-low': 'v2', 'conveyor-corner': 'v2', 'conveyor-diverter': 'v2',
    'forklift': 'v2', 'packing-station': 'v2', 'buffer-pallet': 'v2',
}


def _read(name):
    return json.loads((ROOT / 'contracts' / name).read_text(encoding='utf-8'))


def _load(asset_id, namespace):
    folder = ROOT / 'frontend' / 'public' / 'models'
    path = (folder / 'v2' if namespace == 'v2' else folder) / (asset_id + '.glb')
    if not path.is_file():
        raise FileNotFoundError('Export all v2 prototypes before assembly: ' + str(path))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = set(bpy.data.objects) - before
    if not imported:
        raise RuntimeError('Empty prototype import: ' + asset_id)
    root = group('__prototype__' + asset_id)
    for obj in imported:
        if obj.parent not in imported:
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = world
    return root


def _clone(prototype, name, parent, position=(0, 0, 0), heading=0):
    originals = [prototype] + list(prototype.children_recursive)
    copies = {}
    for original in originals:
        copy = original.copy()
        bpy.context.collection.objects.link(copy)
        copies[original] = copy
        copy.name = name if original == prototype else name + '::' + original.name
    for original, copy in copies.items():
        copy.parent = copies.get(original.parent, parent if original == prototype else None)
        copy.matrix_parent_inverse = original.matrix_parent_inverse.copy()
        copy.matrix_basis = original.matrix_basis.copy()
    root = copies[prototype]
    root.location = xyz(position)
    root.rotation_mode = 'XYZ'
    root.rotation_euler = (0, 0, math.radians(heading))
    root['layout_version'] = VERSION
    return root


def _empty(name, parent, position, role, **props):
    root = group(name)
    root.parent = parent
    root.location = xyz(position)
    root['role'] = role
    for key, value in props.items():
        root[key] = value
    return root


def _tint_person(root, mat):
    # Object-linked material overrides keep shared geometry while distinguishing
    # roles, and never mutate the imported source prototype or other roles.
    for obj in root.children_recursive:
        if obj.type == 'MESH':
            for slot in obj.material_slots:
                if slot.material and any(key in slot.material.name for key in ('Personnel_Cloth', 'Personnel_Vest')):
                    slot.link = 'OBJECT'
                    slot.material = mat


def _triangle_count(root):
    result = 0
    for obj in root.children_recursive:
        if obj.type == 'MESH':
            obj.data.calc_loop_triangles()
            result += len(obj.data.loop_triangles)
    return result


def conveyor_visual_plan(layout):
    """Keep 179 logical cells; trim their meshes around 19 canonical junctions."""
    segments = layout['conveyor']['segments']
    points = [(item['at'][0], item['at'][2]) for item in layout['conveyor']['connections']]
    junctions, cells = [], []
    for index, point in enumerate(points, 1):
        arms = set()
        for segment in segments:
            start, end = segment['from'], segment['to']
            dx, dz = end[0] - start[0], end[2] - start[2]
            length = math.hypot(dx, dz)
            dx, dz = dx / length, dz / length
            ox, oz = point[0] - start[0], point[1] - start[2]
            along = ox * dx + oz * dz
            if along < -1e-5 or along > length + 1e-5 or abs(ox * dz - oz * dx) > 1e-5:
                continue
            if along > 1e-5:
                arms.add((-dx, -dz))
            if along < length - 1e-5:
                arms.add((dx, dz))
        if len(arms) not in (2, 3):
            raise ValueError('Unsupported visual conveyor junction: ' + str(point))
        base = [(0, -1), (1, 0)] + ([(0, 1)] if len(arms) == 3 else [])
        candidates = []
        for turn in range(4):
            yaw = turn * math.pi / 2
            rotated = [(x * math.cos(yaw) + z * math.sin(yaw),
                        -x * math.sin(yaw) + z * math.cos(yaw)) for x, z in base]
            error = sum(min((x - rx) ** 2 + (z - rz) ** 2 for rx, rz in rotated) for x, z in arms)
            candidates.append((error, turn * 90))
        error, heading = min(candidates)
        if error > 1e-4:
            raise ValueError('Conveyor junction arm mismatch at ' + str(point))
        junctions.append({'id': 'JUNCTION_%02d' % index, 'position': (point[0], 0, point[1]),
                          'model': 'conveyor-corner' if len(arms) == 2 else 'conveyor-diverter',
                          'heading': heading, 'arms': sorted(arms)})
    for segment in segments:
        start, end, count = segment['from'], segment['to'], segment['cell_count']
        direction = ((end[0] - start[0]) / count, (end[2] - start[2]) / count)
        for index in range(count):
            left = (start[0] + direction[0] * index, start[2] + direction[1] * index)
            right = (left[0] + direction[0], left[1] + direction[1])
            trim_start = .5 if any(math.dist(left, point) < 1e-5 for point in points) else 0
            trim_end = .5 if any(math.dist(right, point) < 1e-5 for point in points) else 0
            length = 1 - trim_start - trim_end
            if length <= 0:
                raise ValueError('Visual junctions consume a complete logical conveyor cell')
            cells.append({'id': '%s:%s' % (segment['segment_id'], index),
                          'segment_id': segment['segment_id'], 'index': index, 'length': length,
                          'position': (left[0] + direction[0] * (trim_start + length / 2), 0,
                                       left[1] + direction[1] * (trim_start + length / 2)),
                          'heading': math.degrees(math.atan2(direction[0], direction[1])),
                          'logical_from': (left[0], .9, left[1]), 'logical_to': (right[0], .9, right[1]),
                          'trim_start': trim_start, 'trim_end': trim_end})
    if len(cells) != 179 or len(junctions) != 19:
        raise ValueError('Expected 179 logical cells and 19 visual junctions')
    return cells, junctions


def build():
    layout, assignment, staffing = (_read(name) for name in
        ('layout.example.json', 'assignment.example.json', 'actors.example.json'))
    if any(doc['layout_version'] != VERSION for doc in (layout, assignment, staffing)):
        raise ValueError('All assembly inputs must use ' + VERSION)
    lots = assignment['initial_lots']
    if (len(layout['racks']), len(layout['slots']), len(lots),
            len(staffing['actors']), len(staffing['vehicles']),
            len(layout['pack_stations'])) != (288, 864, 600, 24, 2, 6):
        raise ValueError('Canonical v2 assembly counts do not match 288/864/600/24/2/6.')
    if sum(segment['cell_count'] for segment in layout['conveyor']['segments']) != 179:
        raise ValueError('Canonical v2 requires 179 conveyor cells.')
    if len({lot['slot_id'] for lot in lots}) != 600:
        raise ValueError('Each of the 600 initial lots must occupy a distinct slot.')

    prototypes = {name: _load(name, ns) for name, ns in PROTOTYPES.items()}
    crate_proto = group('__prototype__crate_symbol')
    carton = material('V2 master | low carton symbol', '#B98D55', .9)
    box('Exact_12_triangle_carton', (0, 0, 0), (.55, .45, .65), carton, crate_proto, 0)
    prototypes['crate-symbol'] = crate_proto

    root = group('warehouse_root__V2')
    root['role'] = 'initial_design_assembly_not_replay'
    root['floor_dimensions_m'] = [72., 48.]
    root['assignment_id'] = assignment['assignment_id']
    root['assignment_provenance'] = json.dumps(assignment['provenance'], ensure_ascii=False)
    root['tote_pool_count'] = 96
    root['tote_pool_mesh_policy'] = 'logical_pool_only_no_invented_active_cargo'
    root['lod_policy'] = 'rack-low,worker-low,12-triangle-stock-symbols,conveyor-low'
    root['render_offset_policy'] = 'cosmetic_only_business_roots_keep_contract_coordinates'
    _clone(prototypes['environment-shell'], 'environment_shell__V2', root)

    rack_roots, slot_roots, bin_anchors = {}, {}, []
    for item in layout['racks']:
        heading = 180 if item['rack_id'].endswith('_R') else 0
        rack = _clone(prototypes['rack-low'], 'rack__' + item['rack_id'], root, item['root'], heading)
        rack['role'] = 'rack_module'
        rack['rack_id'] = item['rack_id']
        rack_roots[item['rack_id']] = rack
    rack_positions = {item['rack_id']: item['root'] for item in layout['racks']}
    picker_nodes = {node['node_id']: node['pos'] for node in layout['picker_graph']['nodes']}
    for item in layout['slots']:
        # The bin is directly above the rack origin, so its vertical local offset
        # stays exact for both the left-facing and 180-degree right-facing racks.
        rack_pos = rack_positions[item['rack_id']]
        offset = [item['bin_anchor'][axis] - rack_pos[axis] for axis in range(3)]
        slot = _empty('slot__' + item['slot_id'], rack_roots[item['rack_id']],
                      offset, 'logical_storage_slot', slot_id=item['slot_id'],
                      level=item['level'], kind=item['kind'])
        slot['rack_id'] = item['rack_id']
        slot['selectable_bounds_m'] = [.82, 1.65, 1.4]
        slot_roots[item['slot_id']] = slot
        anchor = _empty('anchor_bin__' + item['slot_id'], slot, (0, 0, 0),
                        'bin_anchor', slot_id=item['slot_id'])
        bin_anchors.append((anchor, item['bin_anchor']))
        if item['service_node_id'] is not None:
            slot['service_node_id'] = item['service_node_id']
            _empty('anchor_pick__' + item['slot_id'], root, picker_nodes[item['service_node_id']],
                   'pick_service_anchor', slot_id=item['slot_id'], node_id=item['service_node_id'])
    lot_roots = []
    for lot in lots:
        if lot['slot_id'] not in slot_roots:
            raise ValueError('Initial lot references an unknown slot: ' + lot['slot_id'])
        item = _clone(crate_proto, 'lot__' + lot['lot_id'], slot_roots[lot['slot_id']])
        for key in ('lot_id', 'sku_id', 'slot_id', 'quantity'):
            item[key] = lot[key]
        item['role'] = 'initial_inventory_symbol'
        item['symbol_dimensions_are_not_capacity'] = True
        lot_roots.append(item)

    pack_roots = []
    for pack in layout['pack_stations']:
        station = _clone(prototypes['packing-station'], 'pack_station__' + pack['pack_id'],
                         root, pack['worker_pos'])
        station['pack_id'] = pack['pack_id']
        station['role'] = 'packing_station'
        for kind in ('input', 'output'):
            _empty('anchor_' + kind + '__' + pack['pack_id'], root, pack[kind + '_anchor'],
                   'packing_' + kind + '_anchor', pack_id=pack['pack_id'])
        pack_roots.append(station)

    yellow = material('V2 master | induction guard', '#C8A140', .8)
    for induction in layout['inductions']:
        anchor = induction['handoff_anchor']
        marker = _empty('induction__' + induction['induction_id'], root,
                        (anchor[0], 0, anchor[2]), 'induction_handoff',
                        induction_id=induction['induction_id'])
        _empty('anchor_handoff__' + induction['induction_id'], marker, (0, anchor[1], 0),
               'handoff_anchor')
        for sign in (-1, 1):
            box('Induction_side_guard', (sign * .48, .18, .15),
                (.07, .36, .34), yellow, marker, .004)

    visual_cells, visual_junctions = conveyor_visual_plan(layout)
    for item in visual_cells:
        cell = _clone(prototypes['conveyor-low'],
                      'conveyor_cell__%s_%03d' % (item['segment_id'], item['index']),
                      root, item['position'], item['heading'])
        # Runtime local Z is Blender local Y; only the visual straight is trimmed.
        cell.scale = (1, item['length'], 1)
        cell['role'] = 'conveyor_cell'
        cell['segment_id'] = item['segment_id']
        cell['cell_index'] = item['index']
        cell['cell_id'] = item['id']
        cell['visual_length_m'] = item['length']
        cell['trim_start_m'] = item['trim_start']
        cell['trim_end_m'] = item['trim_end']
        cell['belt_top_y'] = .9
        for port in ('from', 'to'):
            _empty('logical_port_%s__%s' % (port, item['id']), root, item['logical_' + port],
                   'logical_conveyor_cell_port', cell_id=item['id'], port_name=port)
    for item in visual_junctions:
        junction = _clone(prototypes[item['model']], 'conveyor_junction__' + item['id'],
                          root, item['position'], item['heading'])
        junction['role'] = 'conveyor_junction'
        junction['junction_id'] = item['id']
        junction['source_model'] = item['model']
        junction['canonical_arms_xz'] = json.dumps(item['arms'])
    conveyor_count = len(visual_cells)

    role_materials = {
        role: material('V2 master | ' + role + ' clothing', color, .86)
        for role, color in (
            ('picker', '#34737C'), ('packer', '#4A7194'),
            ('receiver', '#64856C'), ('shipper', '#BA8D47'),
        )
    }
    actor_roots, vehicle_roots = [], {}
    drivers = {actor['vehicle_id']: actor for actor in staffing['actors'] if actor['role'] == 'forklift_driver'}
    for vehicle in staffing['vehicles']:
        driver = drivers[vehicle['vehicle_id']]
        forklift = _clone(prototypes['forklift'], 'vehicle__' + vehicle['vehicle_id'],
                          root, driver['initial_pos'], 180)
        forklift['role'] = 'forklift_vehicle'
        forklift['vehicle_id'] = vehicle['vehicle_id']
        forklift['graph_id'] = vehicle['graph_id']
        vehicle_roots[vehicle['vehicle_id']] = forklift
    coincidence_counts = {}
    for actor in staffing['actors']:
        role = actor['role']
        if role == 'forklift_driver':
            actor_root = _empty('actor__' + actor['actor_id'], vehicle_roots[actor['vehicle_id']],
                                (0, 0, 0), role, actor_id=actor['actor_id'])
            actor_root['vehicle_id'] = actor['vehicle_id']
            visual = _clone(prototypes['driver'], 'visual__' + actor['actor_id'],
                            actor_root, (0, .99, -.65))
            visual['seat_anchor_runtime'] = [0, .99, -.65]
            offset = [0., 0., 0.]
        else:
            actor_root = _empty('actor__' + actor['actor_id'], root, actor['initial_pos'],
                                role, actor_id=actor['actor_id'])
            offset = [0., 0., 0.]
            if role == 'picker':
                key = tuple(actor['initial_pos'])
                index = coincidence_counts.get(key, 0)
                coincidence_counts[key] = index + 1
                offset = [-.35 if index % 2 == 0 else .35, 0., -.35 if index < 2 else .35]
            elif role == 'packer':
                offset = [0., 0., .85]
            visual = _clone(prototypes['worker-low'], 'visual__' + actor['actor_id'],
                            actor_root, offset, 180 if role == 'packer' else 0)
            _tint_person(visual, role_materials[role])
            if role == 'picker':
                cart = _clone(prototypes['picking-cart'], 'cart__' + actor['actor_id'],
                              actor_root, (offset[0], 0, offset[2] + .82))
                cart['role'] = 'picking_cart'
                cart['actor_id_owner'] = actor['actor_id']
        actor_root['initial_pos'] = actor['initial_pos']
        actor_root['render_offset'] = offset
        if 'home_node_id' in actor:
            actor_root['home_node_id'] = actor['home_node_id']
        if 'pack_id' in actor:
            actor_root['pack_id'] = actor['pack_id']
        actor_roots.append(actor_root)

    # Dock placements align with the shell's west Z36/east Z3 openings.
    for name, position, heading in (
        ('RECEIVING', (0, 0, 36), 90), ('SHIPPING', (72, 0, 3), -90),
    ):
        dock = _clone(prototypes['dock'], 'dock__' + name, root, position, heading)
        dock['role'] = 'loading_dock'
        dock['dock_id'] = name
    buffer = _clone(prototypes['buffer-pallet'], 'buffer__RELOCATION', root, (66, 0, 42))
    buffer['role'] = 'temporary_relocation_buffer'
    _empty('anchor_buffer__RELOCATION', root, (66, .3, 42), 'temporary_buffer_box_anchor')
    for index, z in enumerate((18, 26, 30), 1):
        pallet = _clone(prototypes['buffer-pallet'], 'STATIC_DECOR_receiving_%02d' % index,
                        root, (1.6, 0, z))
        pallet['role'] = 'static_set_dressing_not_receipt_inventory'
        pallet['static_decor_id'] = 'STATIC_DECOR_%02d' % index

    for prototype in prototypes.values():
        for obj in list(prototype.children_recursive) + [prototype]:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    counts = {'racks': len(rack_roots), 'slots': len(slot_roots), 'occupied_slots': len(lot_roots),
              'actors': len(actor_roots), 'vehicles': len(vehicle_roots),
              'pack_stations': len(pack_roots), 'conveyor_cells': conveyor_count,
              'conveyor_junctions': len(visual_junctions)}
    if list(counts.values()) != [288, 864, 600, 24, 2, 6, 179, 19]:
        raise RuntimeError('Assembly lost canonical objects: ' + json.dumps(counts))
    for anchor, expected in bin_anchors:
        if (anchor.matrix_world.translation - xyz(expected)).length > .02:
            raise RuntimeError('Bin anchor coordinate drift: ' + anchor.name)
    for actor_root in actor_roots:
        if (actor_root.matrix_world.translation - xyz(actor_root['initial_pos'])).length > .02:
            raise RuntimeError('Actor business coordinate drift: ' + actor_root.name)
    triangles = _triangle_count(root)
    if triangles > 350000:
        raise RuntimeError('Initial master exceeds 350k triangle budget: ' + str(triangles))
    root['counts'] = json.dumps(counts)
    root['instance_triangles'] = triangles
    print('V2_ASSEMBLY_VERIFIED ' + json.dumps(dict(counts, triangles=triangles)))
    return root


if __name__ == '__main__':
    reset()
    finish('large-warehouse', build(), batch_runtime=False)
