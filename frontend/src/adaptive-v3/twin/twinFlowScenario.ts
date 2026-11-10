import type { WarehouseBundle, XYZ } from '../warehouseTypes';
import type { AtmoEvent } from './twinScenario';
export type FlowVariant = 'A' | 'B';
export type FlowStationId = 'PK03' | 'PK05' | 'PK06';
export type FlowCargoFrame = {
    id: string;
    visible: boolean;
    payload: 'tote' | 'parcel';
    phase: string;
    position: XYZ;
    yaw: number;
    source_edge_id: string;
    station_id: FlowStationId;
    wait_reason: string | null;
    occupied_cell_ids: string[];
    reserved_resource_ids: string[];
};
export type FlowStationFrame = {
    station_id: FlowStationId;
    status: 'unavailable' | 'outage' | 'idle' | 'reserved' | 'processing';
    available: boolean;
    current_job_id: string | null;
    staff_ready_s: number | null;
    packed_count: number;
};
export type FlowFrame = {
    at_s: number;
    variant: FlowVariant;
    phase: string;
    source_kind: 'visual_fixture';
    engine_operation: false;
    operational_admission: false;
    cargoFrames: FlowCargoFrame[];
    counts: {
        arrived: number;
        waiting: number;
        in_service: number;
        in_transit: number;
        completed: number;
        packed: number;
    };
    queue: {
        total: number;
        main: number;
        upstream: number;
        byStation: Record<FlowStationId, number>;
    };
    stations: FlowStationFrame[];
    decision: {
        at_s: number;
        applied: boolean;
        rerouted_count: number;
        message: string;
    };
    outage: {
        station_id: 'PK03';
        from_s: number;
        to_s: number;
        active: boolean;
    };
};
export type FlowJob = {
    id: string;
    arrival_s: number;
    service_work_s: number;
};
export type FlowReservation = {
    resource_id: string;
    job_id: string;
    from_s: number;
    to_s: number;
    open_at_end?: boolean;
};
export type FlowAudit = {
    activities: readonly {
        job_id: string;
        station_id: FlowStationId;
        phase: string;
        from_s: number;
        to_s: number;
        source_edge_id: string;
    }[];
    reservations: readonly FlowReservation[];
    routes: readonly {
        job_id: string;
        station_id: FlowStationId;
        decision_at_s: number | null;
        decision_x: number | null;
    }[];
};
export type FlowChapter = {
    at_s: number;
    id: string;
    label: string;
};
export type FlowOptions = {
    staffReady_s?: Partial<Record<'PK05' | 'PK06', number>>;
    staffLeave_s?: Partial<Record<'PK05' | 'PK06', number>>;
    decisionEnabled?: boolean;
    duration_s?: number;
};
export type TwinFlowScenario = {
    source_kind: 'visual_fixture';
    engine_operation: false;
    operational_admission: false;
    duration_s: number;
    comparison_horizon_s: 240;
    work_basis_s: 7.5;
    assumptions: Readonly<Record<string, unknown>>;
    collection_clearance_s: 2;
    completed_scope: 'left_packing_line_at_declared_collection_boundary';
    atmosphere_events: Record<FlowVariant, readonly AtmoEvent[]>;
    chapters: readonly FlowChapter[];
    jobs: readonly FlowJob[];
    sample(variant: FlowVariant, at_s: number): FlowFrame;
    audit(variant: FlowVariant): FlowAudit;
};
type Edge = {
    edge_id: string;
    from_node_id: string;
    to_node_id: string;
    length_m: number;
    resource_id: string;
    path_kind: string;
    turn_timing?: string;
    centre?: XYZ;
    radius_m?: number;
    theta_start_rad?: number;
    theta_end_rad?: number;
};
type Cell = {
    cell_id: string;
    resource_id: string;
    position?: XYZ;
    length_m?: number;
    theta_range?: [
        number,
        number
    ];
};
type Resource = {
    resource_id: string;
    capacity: number;
    member_cell_ids: string[];
};
type Conveyor = {
    edges: Edge[];
    nodes: {
        node_id: string;
        world_pos: XYZ;
    }[];
    cells: Cell[];
    resources: Resource[];
    source_assumptions: {
        speed_m_s: number;
        transfer_dwell_s: number;
    };
};
type Vertex = {
    id: string;
    position: XYZ;
};
type Arc = {
    id: string;
    from: Vertex;
    to: Vertex;
    edge: Edge;
    u0: number;
    u1: number;
};
type Network = {
    source: Conveyor;
    vertices: Map<string, Vertex>;
    outgoing: Map<string, Arc[]>;
    edges: Map<string, Edge>;
};
type Segment = {
    from_s: number;
    to_s: number;
    phase: string;
    from: Vertex;
    to: Vertex;
    edge: Edge;
    u0: number;
    u1: number;
    yaw0: number;
    yaw1: number;
    arc?: Arc;
};
type Wait = {
    open_at_end?: boolean;
    from_s: number;
    to_s: number;
    reason: string;
    vertex: Vertex;
    yaw: number;
    edge_id: string;
};
type Job = FlowJob & {
    station: FlowStationId;
    vertex: Vertex;
    yaw: number;
    mode: 'inbound' | 'service' | 'outbound' | 'terminal' | 'done';
    path: Arc[];
    active?: Segment;
    segments: Segment[];
    waits: Wait[];
    wait?: Wait;
    inducted_s?: number;
    packed_s?: number;
    completed_s?: number;
    service_remaining: number;
    spur: string | null;
    readyPivot: string | null;
    afterPivot: Arc | null;
    pathDirty: boolean;
    decision_at_s: number | null;
    decision_x: number | null;
    held: Set<string>;
    reservations: FlowReservation[];
    last_edge: Edge;
};
type Simulation = {
    network: Network;
    variant: FlowVariant;
    options: FlowOptions;
    jobs: Job[];
    holders: Map<string, Job>;
    open: Map<string, FlowReservation>;
    reservations: FlowReservation[];
    duration: number;
    decisionDone: boolean;
};
const EPS = 1e-8, DECISION = 46, OUTAGE_START = 30, OUTAGE_END = 150, WORK = 7.5;
const RADIUS = Math.hypot(.6, .4) / 2;
const STATIONS: FlowStationId[] = ['PK03', 'PK05', 'PK06'];
const need = (value: unknown, message: string): void => {
    if (!value)
        throw Error(message);
};
const stationNumber = (id: FlowStationId) => id.slice(2);
const stationNode = (id: FlowStationId, kind: string) => 'v3:conv:' + id + ':' + kind;
function edgePosition(edge: Edge, progress: number, network: Network): XYZ {
    const a = network.vertices.get(edge.from_node_id)!.position, b = network.vertices.get(edge.to_node_id)!.position;
    if (edge.path_kind === 'arc') {
        const angle = edge.theta_start_rad! + (edge.theta_end_rad! - edge.theta_start_rad!) * progress;
        return [edge.centre![0] + edge.radius_m! * Math.cos(angle), edge.centre![1], edge.centre![2] + edge.radius_m! * Math.sin(angle)];
    }
    return a.map((v, i) => v + (b[i]! - v) * progress) as XYZ;
}
function edgeYaw(edge: Edge, progress: number) {
    if (edge.path_kind === 'arc')
        return progress * Math.PI / 2;
    if (edge.resource_id === 'V3_FEED')
        return 0;
    return edge.resource_id.startsWith('V3_SPUR') || edge.turn_timing ? Math.PI : Math.PI / 2;
}
function edgeCuts(edge: Edge, network: Network) {
    if (edge.path_kind === 'arc')
        return [.125, .375, .625, .875].map(u => ({ u, id: edge.edge_id + ':' + u }));
    const a = network.vertices.get(edge.from_node_id)!.position, b = network.vertices.get(edge.to_node_id)!.position;
    const delta = b.map((v, i) => v - a[i]!), norm = delta.reduce((sum, v) => sum + v * v, 0), cuts = [];
    for (const cell of network.source.cells) {
        if (!cell.position)
            continue;
        const u = cell.position.reduce((sum, v, i) => sum + (v - a[i]!) * delta[i]!, 0) / norm;
        const distance = Math.hypot(...cell.position.map((v, i) => v - a[i]! - delta[i]! * u));
        if (u > EPS && u < 1 - EPS && distance < EPS)
            cuts.push({ u, id: 'flow:' + cell.cell_id });
    }
    return cuts.sort((left, right) => left.u - right.u);
}
function buildNetwork(bundle: WarehouseBundle): Network {
    const source = bundle.layout.data.conveyor as Conveyor;
    need(bundle.source_kind === 'visual_fixture' && !bundle.engine_operation, 'Validated visual source required');
    need(source.source_assumptions.speed_m_s === .55 && source.source_assumptions.transfer_dwell_s === .8, 'Unexpected source conveyor timing');
    for (const id of ['V3_CURVE_EXCLUSIVE', 'V3_FEED', 'V3_T03', 'V3_T05', 'V3_T06', 'V3_SPUR03', 'V3_SPUR05', 'V3_SPUR06'])
        need(source.resources.find(row => row.resource_id === id)?.capacity === 1, 'Source exclusive capacity required: ' + id);
    need(bundle.registry.clips.find(clip => clip.clip_id === 'packer_finish')?.duration_s === WORK, 'Source finishing-work reference required');
    const network: Network = {
        source,
        vertices: new Map(),
        outgoing: new Map(),
        edges: new Map(source.edges.map(edge => [edge.edge_id, edge]))
    };
    for (const node of source.nodes)
        network.vertices.set(node.node_id, { id: node.node_id, position: [...node.world_pos] });
    for (const edge of [...source.edges].sort((a, b) => a.edge_id.localeCompare(b.edge_id))) {
        const cuts = [{ u: 0, id: edge.from_node_id }, ...edgeCuts(edge, network), { u: 1, id: edge.to_node_id }];
        for (const cut of cuts)
            if (!network.vertices.has(cut.id))
                network.vertices.set(cut.id, { id: cut.id, position: edgePosition(edge, cut.u, network) });
        for (let i = 1; i < cuts.length; i++) {
            const from = cuts[i - 1]!, to = cuts[i]!;
            const arc: Arc = {
                id: edge.edge_id + ':' + i,
                from: network.vertices.get(from.id)!,
                to: network.vertices.get(to.id)!,
                edge,
                u0: from.u,
                u1: to.u
            };
            const list = network.outgoing.get(from.id) ?? [];
            list.push(arc);
            network.outgoing.set(from.id, list);
        }
    }
    return network;
}
function route(network: Network, from: Vertex, to: string): Arc[] | null {
    const queue = [from.id], seen = new Set(queue), parents = new Map<string, Arc>();
    for (let i = 0; i < queue.length && !seen.has(to); i++)
        for (const arc of network.outgoing.get(queue[i]!) ?? []) {
            if (seen.has(arc.to.id))
                continue;
            seen.add(arc.to.id);
            parents.set(arc.to.id, arc);
            queue.push(arc.to.id);
        }
    if (!seen.has(to))
        return null;
    const result: Arc[] = [];
    for (let node = to; node !== from.id;) {
        const arc = parents.get(node)!;
        result.unshift(arc);
        node = arc.from.id;
    }
    return result;
}
function keysForBounds(network: Network, a: XYZ, b: XYZ) {
    const lo = [Math.min(a[0], b[0]) - RADIUS, Math.min(a[2], b[2]) - RADIUS];
    const hi = [Math.max(a[0], b[0]) + RADIUS, Math.max(a[2], b[2]) + RADIUS], keys = new Set<string>();
    for (const cell of network.source.cells) {
        if (!cell.position)
            continue;
        const alongX = cell.resource_id === 'V3_MAIN' || cell.resource_id.startsWith('V3_T');
        const hx = alongX ? (cell.length_m ?? 1) / 2 : .41, hz = alongX ? .41 : (cell.length_m ?? 1) / 2;
        if (hi[0]! <= cell.position[0] - hx + EPS || lo[0]! >= cell.position[0] + hx - EPS || hi[1]! <= cell.position[2] - hz + EPS || lo[1]! >= cell.position[2] + hz - EPS)
            continue;
        keys.add(cell.cell_id);
        if (cell.resource_id !== 'V3_MAIN')
            keys.add(cell.resource_id);
    }
    if (hi[0]! > 128.5 && lo[0]! < 129.75 && hi[1]! > 3 && lo[1]! < 4.25) {
        const curve = network.source.resources.find(row => row.resource_id === 'V3_CURVE_EXCLUSIVE')!;
        keys.add(curve.resource_id);
        for (const id of curve.member_cell_ids)
            keys.add(id);
    }
    return keys;
}
function retainedKeys(sim: Simulation, job: Job) {
    const keys = keysForBounds(sim.network, job.vertex.position, job.vertex.position);
    if (job.spur) {
        keys.add(job.spur);
        for (const id of sim.network.source.resources.find(row => row.resource_id === job.spur)!.member_cell_ids)
            keys.add(id);
    }
    return keys;
}
function acquire(sim: Simulation, job: Job, keys: Set<string>, at: number) {
    if ([...keys].some(key => sim.holders.has(key) && sim.holders.get(key) !== job))
        return false;
    for (const key of keys)
        if (!job.held.has(key)) {
            job.held.add(key);
            sim.holders.set(key, job);
            const row = {
                resource_id: key,
                job_id: job.id,
                from_s: at,
                to_s: sim.duration
            };
            sim.open.set(key, row);
            sim.reservations.push(row);
            job.reservations.push(row);
        }
    return true;
}
function releaseUnused(sim: Simulation, job: Job, at: number, keep = retainedKeys(sim, job)) {
    for (const key of [...job.held])
        if (!keep.has(key)) {
            sim.open.get(key)!.to_s = at;
            sim.open.delete(key);
            sim.holders.delete(key);
            job.held.delete(key);
        }
}
function waiting(job: Job, at: number, reason: string) {
    if (job.wait?.reason === reason)
        return;
    if (job.wait)
        job.wait.to_s = at;
    const row = {
        from_s: at,
        to_s: Infinity,
        reason,
        vertex: job.vertex,
        yaw: job.yaw,
        edge_id: job.last_edge.edge_id
    };
    job.wait = row;
    job.waits.push(row);
}
function startSegment(job: Job, segment: Segment) {
    if (job.wait) {
        job.wait.to_s = segment.from_s;
        job.wait = undefined;
    }
    job.active = segment;
    job.segments.push(segment);
}
function stationReady(sim: Simulation, station: FlowStationId, at: number) {
    if (station === 'PK03')
        return at < OUTAGE_START || at >= OUTAGE_END;
    const ready = sim.options.staffReady_s?.[station], leave = sim.options.staffLeave_s?.[station] ?? 260;
    return sim.variant === 'B' && sim.options.decisionEnabled !== false && ready !== undefined && at >= ready && at < leave;
}
function applyDecision(sim: Simulation, at: number) {
    if (sim.decisionDone || at < DECISION)
        return;
    sim.decisionDone = true;
    if (sim.variant !== 'B' || sim.options.decisionEnabled === false)
        return;
    const assigned = { PK05: 0, PK06: 0 };
    for (const job of sim.jobs) {
        if (job.packed_s !== undefined || job.spur)
            continue;
        const vertex = job.active?.to ?? job.vertex;
        const choices = (['PK05', 'PK06'] as const).filter(station => route(sim.network, vertex, stationNode(station, 'WORK')) !== null);
        choices.sort((a, b) => assigned[a] - assigned[b] || b.localeCompare(a));
        const station = choices[0];
        if (!station)
            continue;
        job.station = station;
        assigned[station]++;
        job.pathDirty = true;
        job.decision_at_s = at;
        job.decision_x = vertex.position[0];
    }
}
function finishSegment(sim: Simulation, job: Job, at: number) {
    const segment = job.active!;
    job.active = undefined;
    job.vertex = segment.to;
    job.yaw = segment.yaw1;
    job.last_edge = segment.edge;
    if (segment.phase === 'pivot_in')
        job.readyPivot = segment.arc!.id;
    if (segment.phase === 'pivot_out') {
        job.afterPivot = null;
        job.spur = null;
    }
    if (segment.phase === 'packing') {
        job.service_remaining = Math.max(0, job.service_remaining - (segment.to_s - segment.from_s));
        if (job.service_remaining <= EPS) {
            job.packed_s = at;
            job.mode = 'outbound';
            job.path = route(sim.network, job.vertex, 'v3:conv:output')!;
        }
    }
    if (segment.phase === 'output_clearance') {
        job.completed_s = at;
        job.mode = 'done';
        releaseUnused(sim, job, at, new Set());
        return;
    }
    if (segment.phase === 'travel' && segment.arc?.u1 === 1 && segment.edge.turn_timing === 'after_edge')
        job.afterPivot = segment.arc;
    if (!job.path.length && job.mode === 'inbound' && job.vertex.id === stationNode(job.station, 'WORK'))
        job.mode = 'service';
    if (!job.path.length && job.mode === 'outbound' && job.vertex.id === 'v3:conv:output')
        job.mode = 'terminal';
    if (job.pathDirty && job.mode === 'inbound') {
        job.path = route(sim.network, job.vertex, stationNode(job.station, 'WORK'))!;
        job.pathDirty = false;
    }
    releaseUnused(sim, job, at);
}
function fixedSegment(job: Job, at: number, duration: number, phase: string, yaw1 = job.yaw, arc?: Arc): Segment {
    return {
        from_s: at,
        to_s: at + duration,
        phase,
        from: job.vertex,
        to: job.vertex,
        edge: arc?.edge ?? job.last_edge,
        u0: arc?.u0 ?? 0,
        u1: arc?.u0 ?? 0,
        yaw0: job.yaw,
        yaw1,
        ...(arc ? { arc } : {})
    };
}
function tryService(sim: Simulation, job: Job, at: number) {
    if (!stationReady(sim, job.station, at)) {
        waiting(job, at, job.station === 'PK03' ? 'PK03_OUTAGE' : 'STAFF_NOT_READY');
        return;
    }
    const boundary = job.station === 'PK03' && at < OUTAGE_START ? OUTAGE_START : job.station === 'PK03' ? sim.duration + WORK : sim.options.staffLeave_s?.[job.station] ?? 260;
    const duration = Math.min(job.service_remaining, boundary - at);
    if (duration > EPS)
        startSegment(job, fixedSegment(job, at, duration, 'packing'));
}
function transferReservation(sim: Simulation, job: Job, at: number, keys: Set<string>) {
    for (const pad of [...keys].filter(key => /^V3_T\d\d$/.test(key))) {
        const station = ('PK' + pad.slice(-2)) as FlowStationId;
        if (job.mode === 'inbound' && station === job.station) {
            if (!job.spur && !stationReady(sim, station, at)) {
                waiting(job, at, station === 'PK03' ? 'PK03_OUTAGE' : 'STAFF_NOT_READY');
                return false;
            }
            const spur = 'V3_SPUR' + stationNumber(station);
            keys.add(spur);
            for (const id of sim.network.source.resources.find(row => row.resource_id === spur)!.member_cell_ids)
                keys.add(id);
        }
        else {
            const west = sim.network.vertices.get(stationNode(station, 'W'))!;
            for (const key of keysForBounds(sim.network, west.position, west.position))
                keys.add(key);
        }
    }
    return true;
}
function tryTravel(sim: Simulation, job: Job, at: number) {
    if (job.pathDirty) {
        job.path = route(sim.network, job.vertex, stationNode(job.station, 'WORK'))!;
        job.pathDirty = false;
    }
    const arc = job.path[0];
    need(arc, 'Finite source route ended unexpectedly');
    const keys = keysForBounds(sim.network, arc!.from.position, arc!.to.position);
    if (!transferReservation(sim, job, at, keys))
        return;
    if (!acquire(sim, job, keys, at)) {
        waiting(job, at, 'DOWNSTREAM_RESERVED');
        return;
    }
    if (job.mode === 'inbound' && keys.has('V3_SPUR' + stationNumber(job.station)))
        job.spur = 'V3_SPUR' + stationNumber(job.station);
    if (arc!.u0 === 0 && arc!.edge.turn_timing === 'before_edge' && job.readyPivot !== arc!.id) {
        startSegment(job, fixedSegment(job, at, .8, 'pivot_in', Math.PI, arc));
        return;
    }
    job.path.shift();
    job.readyPivot = null;
    startSegment(job, {
        from_s: at,
        to_s: at + arc!.edge.length_m * (arc!.u1 - arc!.u0) / .55,
        phase: 'travel',
        from: arc!.from,
        to: arc!.to,
        edge: arc!.edge,
        u0: arc!.u0,
        u1: arc!.u1,
        yaw0: edgeYaw(arc!.edge, arc!.u0),
        yaw1: edgeYaw(arc!.edge, arc!.u1),
        arc
    });
}
function tryJob(sim: Simulation, job: Job, at: number) {
    if (job.arrival_s > at + EPS || job.active || job.mode === 'done')
        return;
    if (job.inducted_s === undefined) {
        if (!acquire(sim, job, retainedKeys(sim, job), at)) {
            waiting(job, at, 'UPSTREAM_FEED');
            return;
        }
        job.inducted_s = at;
    }
    if (job.mode === 'service') {
        tryService(sim, job, at);
        return;
    }
    if (job.mode === 'terminal') {
        startSegment(job, fixedSegment(job, at, 2, 'output_clearance'));
        return;
    }
    if (job.afterPivot) {
        startSegment(job, fixedSegment(job, at, .8, 'pivot_out', Math.PI / 2, job.afterPivot));
        return;
    }
    tryTravel(sim, job, at);
}
function makeJobs(network: Network): Job[] {
    const arrivals = [...Array.from({ length: 6 }, (_, i) => -100 + i * 5.5), ...Array.from({ length: 12 }, (_, i) => i * 5.5)];
    return arrivals.map((arrival_s, index) => {
        const vertex = network.vertices.get('v3:conv:intake')!;
        return {
            id: 'twin-visual-carrier-' + (index + 1),
            arrival_s,
            service_work_s: WORK,
            station: 'PK03',
            vertex,
            yaw: 0,
            mode: 'inbound',
            path: route(network, vertex, stationNode('PK03', 'WORK'))!,
            segments: [],
            waits: [],
            service_remaining: WORK,
            spur: null,
            readyPivot: null,
            afterPivot: null,
            pathDirty: false,
            decision_at_s: null,
            decision_x: null,
            held: new Set(),
            reservations: [],
            last_edge: network.edges.get('v3:conv:feed')!
        };
    });
}
function simulate(network: Network, variant: FlowVariant, options: FlowOptions, duration: number) {
    const sim: Simulation = {
        network,
        variant,
        options,
        jobs: makeJobs(network),
        holders: new Map(),
        open: new Map(),
        reservations: [],
        duration,
        decisionDone: false
    };
    let at = sim.jobs[0]!.arrival_s, turns = 0;
    const boundaries = [DECISION, OUTAGE_START, OUTAGE_END, 260, duration, ...Object.values(options.staffReady_s ?? {}), ...Object.values(options.staffLeave_s ?? {})];
    while (at <= duration + EPS) {
        need(turns++ < 20000, 'Finite packing schedule failed to advance');
        for (const job of sim.jobs)
            if (job.active && job.active.to_s <= at + EPS)
                finishSegment(sim, job, at);
        applyDecision(sim, at);
        if (at >= duration)
            break;
        const priority = [...sim.jobs].sort((a, b) => Number(b.mode === 'outbound') - Number(a.mode === 'outbound') || a.vertex.position[0] - b.vertex.position[0] || a.arrival_s - b.arrival_s);
        for (const job of priority)
            tryJob(sim, job, at);
        const future = [...boundaries, ...sim.jobs.flatMap(job => [job.arrival_s, job.active?.to_s ?? duration])].filter(value => value > at + EPS);
        need(future.length > 0, 'Packing schedule has no finite next cut');
        at = Math.min(...future);
    }
    for (const row of sim.open.values())
        row.open_at_end = true;
    for (const job of sim.jobs)
        if (job.wait) {
            job.wait.to_s = duration;
            job.wait.open_at_end = true;
        }
    sim.reservations = sim.reservations.filter(row => row.to_s > row.from_s + EPS);
    return sim;
}
function atInterval(at: number, from: number, to: number) {
    return at >= from - EPS && at < to - EPS;
}
function sampledJob(sim: Simulation, job: Job, at: number) {
    const arrived = at >= job.arrival_s - EPS;
    const inducted = job.inducted_s !== undefined && at >= job.inducted_s - EPS;
    const completed = job.completed_s !== undefined && at >= job.completed_s - EPS;
    const segment = job.segments.find(row => atInterval(at, row.from_s, row.to_s));
    const wait = job.waits.find(row => atInterval(at, row.from_s, row.to_s) || row.open_at_end && at === sim.duration);
    const ended = [...job.segments].reverse().find(row => row.to_s <= at + EPS);
    let position: XYZ = [...(wait?.vertex.position ?? ended?.to.position ?? sim.network.vertices.get('v3:conv:intake')!.position)];
    let yaw = wait?.yaw ?? ended?.yaw1 ?? 0;
    if (segment) {
        const progress = Math.min(1, Math.max(0, (at - segment.from_s) / (segment.to_s - segment.from_s)));
        position = segment.phase === 'travel' ? edgePosition(segment.edge, segment.u0 + (segment.u1 - segment.u0) * progress, sim.network) : [...segment.from.position];
        yaw = segment.yaw0 + (segment.yaw1 - segment.yaw0) * progress;
    }
    const reserved = job.reservations.filter(row => atInterval(at, row.from_s, row.to_s) || row.open_at_end && at === sim.duration).map(row => row.resource_id);
    const stationary = !!wait && (at - wait.from_s >= 2 - EPS || wait.reason !== 'DOWNSTREAM_RESERVED');
    const frame: FlowCargoFrame = {
        id: job.id,
        visible: arrived && inducted && !completed,
        payload: job.packed_s !== undefined && at >= job.packed_s - EPS ? 'parcel' : 'tote',
        phase: completed ? 'left_packing_line' : !arrived ? 'not_arrived' : !inducted ? 'upstream_feed' : segment?.phase ?? 'waiting',
        position,
        yaw,
        source_edge_id: segment?.edge.edge_id ?? wait?.edge_id ?? ended?.edge.edge_id ?? 'v3:conv:feed',
        station_id: job.decision_at_s !== null && at >= job.decision_at_s ? job.station : 'PK03',
        wait_reason: wait?.reason ?? null,
        occupied_cell_ids: arrived && inducted && !completed ? [...keysForBounds(sim.network, position, position)].filter(key => sim.network.source.cells.some(cell => cell.cell_id === key)) : [],
        reserved_resource_ids: reserved,
    };
    return {
        frame,
        arrived,
        inducted,
        completed,
        stationary,
        packing: segment?.phase === 'packing'
    };
}
function sampledStations(sim: Simulation, at: number, cargo: ReturnType<typeof sampledJob>[]): FlowStationFrame[] {
    return STATIONS.map(station => {
        const resource = 'V3_SPUR' + stationNumber(station);
        const current = cargo.find(row => row.frame.reserved_resource_ids.includes(resource));
        const available = stationReady(sim, station, at);
        return {
            station_id: station,
            status: !available ? station === 'PK03' ? 'outage' : 'unavailable' : current?.packing ? 'processing' : current ? 'reserved' : 'idle',
            available,
            current_job_id: current?.frame.id ?? null,
            staff_ready_s: station === 'PK03' ? 0 : sim.options.staffReady_s?.[station] ?? null,
            packed_count: cargo.filter(row => row.frame.station_id === station && row.frame.payload === 'parcel').length,
        };
    });
}
function sampledCounts(cargo: ReturnType<typeof sampledJob>[], waitingCount: number) {
    const arrived = cargo.filter(row => row.arrived).length;
    const inService = cargo.filter(row => row.packing).length;
    const completed = cargo.filter(row => row.completed).length;
    return {
        arrived,
        waiting: waitingCount,
        in_service: inService,
        in_transit: arrived - waitingCount - inService - completed,
        completed,
        packed: cargo.filter(row => row.frame.payload === 'parcel').length
    };
}
function sampleSimulation(sim: Simulation, at: number): FlowFrame {
    const cargo = sim.jobs.map(job => sampledJob(sim, job, at));
    const waiting = cargo.filter(row => row.arrived && !row.completed && (!row.inducted || row.stationary));
    const main = waiting.filter(row => row.inducted && Math.abs(row.frame.position[2] - 3) < .01);
    const byStation = {
        PK03: 0,
        PK05: 0,
        PK06: 0
    };
    for (const row of waiting)
        byStation[row.frame.station_id]++;
    const diverted = sim.jobs.filter(job => job.decision_at_s !== null && at >= job.decision_at_s).length;
    return {
        at_s: at,
        variant: sim.variant,
        phase: at < OUTAGE_START ? 'common_preroll' : at < DECISION ? 'outage_queue' : diverted && at < Math.min(...Object.values(sim.options.staffReady_s ?? {})) ? 'staff_response' : waiting.length ? 'packing_queue' : 'flowing',
        source_kind: 'visual_fixture',
        engine_operation: false,
        operational_admission: false,
        cargoFrames: cargo.map(row => row.frame),
        counts: sampledCounts(cargo, waiting.length),
        queue: {
            total: waiting.length,
            main: main.length,
            upstream: waiting.filter(row => !row.inducted).length,
            byStation
        },
        stations: sampledStations(sim, at, cargo),
        decision: {
            at_s: DECISION,
            applied: diverted > 0,
            rerouted_count: diverted,
            message: diverted ? 'Only upstream uncommitted goods assigned to PK05/PK06; service waits for actual staff arrival' : 'Common goods remain assigned to PK03'
        },
        outage: {
            station_id: 'PK03',
            from_s: OUTAGE_START,
            to_s: OUTAGE_END,
            active: at >= OUTAGE_START && at < OUTAGE_END
        },
    };
}
function pressure(frame: FlowFrame): AtmoEvent['state'] {
    if (frame.queue.total >= 8)
        return 'sos';
    return frame.queue.total >= 3 || frame.outage.active ? 'danger' : 'control';
}
function eventCuts(sim: Simulation) {
    const cuts = new Set([0, DECISION, OUTAGE_START, OUTAGE_END, sim.duration]);
    for (const job of sim.jobs) {
        for (const row of job.segments) {
            cuts.add(row.from_s);
            cuts.add(row.to_s);
        }
        for (const row of job.waits) {
            cuts.add(row.from_s);
            cuts.add(row.from_s + 2);
            cuts.add(row.to_s);
        }
    }
    return [...cuts].filter(at => at >= 0 && at <= sim.duration).sort((a, b) => a - b);
}
function atmosphereCause(frame: FlowFrame, state: AtmoEvent['state']) {
    const pressure = state === 'sos' ? 'Достигнут порог SOS — 8 ожидающих.' : state === 'danger' ? 'Очередь от 3 грузов или недоступность поста.' : 'Очередь линии под контролем.';
    const station = frame.outage.active ? ' PK03 недоступен.' : ' PK03 доступен.';
    const decision = frame.decision.applied ? ' B направляет новые грузы на PK05/PK06, работа начинается после прибытия помощи.' : ' Назначение на PK03 сохранено.';
    return pressure + station + decision;
}
function atmosphere(sim: Simulation): AtmoEvent[] {
    const cuts = eventCuts(sim), events: AtmoEvent[] = [];
    let state: AtmoEvent['state'] | undefined, recoveringSince: number | null = null;
    for (let index = 0; index < cuts.length; index++) {
        const at = cuts[index]!, frame = sampleSimulation(sim, at);
        let next = pressure(frame);
        if (next === 'control' && state && state !== 'control') {
            recoveringSince ??= at;
            if (at < recoveringSince + 5 - EPS) {
                const deadline = recoveringSince + 5;
                if (deadline <= sim.duration && !cuts.some(cut => Math.abs(cut - deadline) < EPS)) {
                    cuts.push(deadline);
                    cuts.sort((a, b) => a - b);
                }
                next = state;
            }
        }
        else if (next !== 'control')
            recoveringSince = null;
        const marked = [OUTAGE_START, OUTAGE_END, DECISION, ...Object.values(sim.options.staffReady_s ?? {})].some(cut => Math.abs(cut - at) < EPS);
        if (next === state && !marked)
            continue;
        state = next;
        events.push({
            at_s: at,
            zone_id: 'PACKING_LIGHT_LINE',
            state: next,
            resource_id: 'PK03',
            cause: atmosphereCause(frame, next)
        });
    }
    return events;
}
function checkSample(variant: FlowVariant, at: number, duration: number) {
    need(variant === 'A' || variant === 'B', 'Unknown packing variant');
    need(Number.isFinite(at) && at >= 0 && at <= duration, 'Packing time outside finite episode');
}
function scenarioChapters(ready: number, duration: number) {
    return Object.freeze(([{
            at_s: 0,
            id: 'initial',
            label: 'Общий входной поток'
        }, {
            at_s: OUTAGE_START,
            id: 'outage',
            label: 'PK03 недоступен'
        }, {
            at_s: DECISION,
            id: 'decision',
            label: 'B направляет помощь'
        }, {
            at_s: ready,
            id: 'staff_ready',
            label: 'Помощь прибыла'
        }, {
            at_s: OUTAGE_END,
            id: 'restart',
            label: 'PK03 возобновляет работу'
        }, {
            at_s: 240,
            id: 'comparison',
            label: 'Срез 240 секунд'
        }, {
            at_s: duration,
            id: 'end',
            label: 'Конец эпизода'
        }] as FlowChapter[]).map(row => Object.freeze(row)));
}
function scenarioAssumptions(jobs: readonly FlowJob[]) {
    return Object.freeze({
        work_basis: 'source_packer_finish_explanatory_visual_clock',
        full_packing_recipe: false,
        queue_dwell_s: 2,
        danger_queue_min: 3,
        sos_queue_min: 8,
        recovery_dwell_s: 5,
        outage_s: Object.freeze([30, 150]),
        preroll_arrivals_s: Object.freeze(jobs.filter(job => job.arrival_s < 0).map(job => job.arrival_s)),
        terminal_handoff: 'unmodelled_external_collection_boundary',
        shipping_admission: false,
        reservation_footprint: 'circumscribed_source_0.6x0.4m_envelope',
        whole_spur_capacity: 1
    });
}
function auditSimulation(sim: Simulation): FlowAudit {
    return {
        activities: sim.jobs.flatMap(job => job.segments.map(segment => ({
            job_id: job.id,
            station_id: job.decision_at_s !== null && segment.from_s >= job.decision_at_s ? job.station : 'PK03' as FlowStationId,
            phase: segment.phase,
            from_s: segment.from_s,
            to_s: segment.to_s,
            source_edge_id: segment.edge.edge_id
        }))),
        reservations: sim.reservations.map(row => ({ ...row })),
        routes: sim.jobs.map(job => ({
            job_id: job.id,
            station_id: job.station,
            decision_at_s: job.decision_at_s,
            decision_x: job.decision_x
        }))
    };
}
export function compileTwinFlowScenario(bundle: WarehouseBundle, options: FlowOptions = {}): TwinFlowScenario {
    const duration = options.duration_s ?? 360;
    need(Number.isFinite(duration) && duration >= 240 && duration <= 900, 'Bounded packing episode required');
    for (const time of [...Object.values(options.staffReady_s ?? {}), ...Object.values(options.staffLeave_s ?? {})])
        need(Number.isFinite(time) && time >= 0 && time <= duration, 'Invalid staff availability time');
    need(options.decisionEnabled === undefined || typeof options.decisionEnabled === 'boolean', 'Invalid decision flag');
    const captured = {
        decisionEnabled: options.decisionEnabled,
        staffReady_s: { ...options.staffReady_s },
        staffLeave_s: { ...options.staffLeave_s }
    };
    const network = buildNetwork(bundle), simulations = { A: simulate(network, 'A', captured, duration), B: simulate(network, 'B', captured, duration) };
    const events = Object.freeze({ A: Object.freeze(atmosphere(simulations.A).map(row => Object.freeze(row))), B: Object.freeze(atmosphere(simulations.B).map(row => Object.freeze(row))) });
    const ready = Math.max(DECISION, ...Object.values(captured.staffReady_s));
    return Object.freeze({
        source_kind: 'visual_fixture' as const,
        engine_operation: false,
        operational_admission: false,
        duration_s: duration,
        comparison_horizon_s: 240,
        work_basis_s: 7.5,
        collection_clearance_s: 2,
        assumptions: scenarioAssumptions(simulations.A.jobs),
        completed_scope: 'left_packing_line_at_declared_collection_boundary',
        atmosphere_events: events,
        chapters: scenarioChapters(ready, duration),
        jobs: Object.freeze(simulations.A.jobs.map(({ id, arrival_s, service_work_s }) => Object.freeze({
            id,
            arrival_s,
            service_work_s
        }))),
        sample(variant: FlowVariant, at: number) {
            checkSample(variant, at, duration);
            return sampleSimulation(simulations[variant], at);
        },
        audit(variant: FlowVariant) {
            checkSample(variant, 0, duration);
            return auditSimulation(simulations[variant]);
        },
    });
}
