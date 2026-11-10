import { integer, need, type ArmData, type BeltPose, type Carrier, type NativeEvent, type Operation, type Relocation, type Worker } from './stream';
export type XYZ = [
    number,
    number,
    number
];
export type Geometry = {
    nodes: Map<string, XYZ>;
    arcs: Map<string, [
        string,
        string
    ]>;
    slots: Map<string, {
        position: XYZ;
        yaw: number;
    }>;
    edges: Map<string, {
        from: XYZ;
        to: XYZ;
        centre?: XYZ;
        radius?: number;
        startAngle?: number;
        endAngle?: number;
    }>;
};
export type ActorFrame = {
    actor_id: string;
    position: XYZ;
    yaw: number;
    operation: string | null;
};
export type PlaybackFrame = {
    tick: number;
    actors: ActorFrame[];
    carriers: {
        job_id: string;
        hu_id: string;
        payload_id: string;
        position: XYZ;
        yaw: number;
        status: string;
    }[];
    relocations: (Relocation & {
        custody: string;
        position: XYZ;
        yaw: number;
    })[];
};
function roundedQuotient(n: bigint, d: bigint): bigint {
    const q = n / d, twiceRemainder = 2n * (n % d);
    return q + (twiceRemainder > d || twiceRemainder === d && q % 2n !== 0n ? 1n : 0n);
}
const ratio = (value: {
    numerator: number | bigint;
    denominator: number | bigint;
}) => {
    let projected: number;
    if (typeof value.numerator === 'bigint' || typeof value.denominator === 'bigint') {
        const n = BigInt(value.numerator), d = BigInt(value.denominator);
        need(d > 0n, 'Invalid native fraction denominator');
        const sign = n < 0n ? -1 : 1, magnitude = n < 0n ? -n : n;
        if (magnitude === 0n)
            projected = 0;
        else {
            // Scale by the ratio's exponent, preserving significant rather than absolute bits.
            let exponent = magnitude.toString(2).length - d.toString(2).length;
            if (exponent >= 0 ? magnitude < (d << BigInt(exponent)) : (magnitude << BigInt(-exponent)) < d)
                exponent--;
            if (exponent > 1023)
                projected = sign * Infinity;
            else if (exponent < -1075)
                projected = sign * 0;
            else if (exponent < -1022)
                projected = sign * Number(roundedQuotient(magnitude << 1074n, d)) * Number.MIN_VALUE;
            else {
                const shift = 52 - exponent;
                const significand = shift >= 0 ? roundedQuotient(magnitude << BigInt(shift), d) : roundedQuotient(magnitude, d << BigInt(-shift));
                projected = sign * (Number(significand) / 2 ** 52) * 2 ** exponent;
            }
        }
    }
    else {
        need(value.denominator > 0, 'Invalid native fraction denominator');
        projected = value.numerator / value.denominator;
    }
    need(Number.isFinite(projected), 'Nonfinite native fraction projection');
    return projected;
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const point = (a: XYZ, b: XYZ, t: number): XYZ => {
    const position: XYZ = [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
    need(position.every(Number.isFinite), 'Nonfinite native geometry projection');
    return position;
};
function quarters(value: BeltPose['yaw_quarters']): number {
    if (typeof value.numerator === 'bigint' || typeof value.denominator === 'bigint') {
        const n = BigInt(value.numerator), d = BigInt(value.denominator);
        need(d > 0n, 'Invalid native fraction denominator');
        // Orientation is periodic; retain the exact raw rational in ArmData.
        return ratio({ numerator: n % (4n * d), denominator: d });
    }
    return ratio(value);
}
function interpolatedQuarters(start: BeltPose['yaw_quarters'], end: BeltPose['yaw_quarters'], elapsed: number, duration: number): number {
    if ([start.numerator, start.denominator, end.numerator, end.denominator].some(n => typeof n === 'bigint')) {
        const sn = BigInt(start.numerator), sd = BigInt(start.denominator), en = BigInt(end.numerator), ed = BigInt(end.denominator);
        const ticks = BigInt(elapsed), span = BigInt(duration);
        // Interpolate the exact phase first. Reducing the delta before this step loses rotations.
        return quarters({ numerator: sn * ed * (span - ticks) + en * sd * ticks, denominator: sd * ed * span });
    }
    return lerp(ratio(start), ratio(end), elapsed / duration);
}
const clamp = (n: number) => Math.max(0, Math.min(1, n));
function routePoints(operation: Operation, geometry: Geometry): XYZ[] {
    const ids = operation.route.node_ids;
    need(ids.length > 0 && ids[0] === operation.source_node && ids.at(-1) === operation.target_node, 'Native route endpoint differs');
    need(operation.route.arc_ids.length === ids.length - 1, 'Native route arc count differs');
    operation.route.arc_ids.forEach((id, i) => { const arc = geometry.arcs.get(id); need(arc && arc[0] === ids[i] && arc[1] === ids[i + 1], 'Native geometry arc differs'); });
    return ids.map(id => { const p = geometry.nodes.get(id); need(p, 'Unknown native geometry node ' + id); return p; });
}
function routePose(operation: Operation, tick: number, geometry: Geometry): {
    position: XYZ;
    yaw: number;
} {
    const points = routePoints(operation, geometry), lengths = points.slice(1).map((p, i) => Math.hypot(...p.map((v, j) => v - points[i][j])));
    const total = lengths.reduce((sum, n) => sum + n, 0);
    let distance = total * clamp((tick - operation.start_tick) / Math.max(1, operation.planned_end_tick - operation.start_tick));
    for (let i = 0; i < lengths.length; i++) {
        if (distance <= lengths[i] || i === lengths.length - 1)
            return { position: point(points[i], points[i + 1], lengths[i] ? distance / lengths[i] : 0), yaw: Math.atan2(points[i + 1][0] - points[i][0], points[i + 1][2] - points[i][2]) };
        distance -= lengths[i];
    }
    return { position: [...points[0]], yaw: 0 };
}
function beltPose(pose: BeltPose, geometry: Geometry): {
    position: XYZ;
    yaw: number;
} {
    const edge = geometry.edges.get(pose.edge_id);
    need(edge, 'Unknown native conveyor edge ' + pose.edge_id);
    const progress = ratio(pose.progress), yaw = quarters(pose.yaw_quarters) * Math.PI / 2;
    need(Number.isFinite(yaw), 'Nonfinite native conveyor yaw');
    if (edge.centre && edge.radius !== undefined && edge.startAngle !== undefined && edge.endAngle !== undefined) {
        const theta = lerp(edge.startAngle, edge.endAngle, progress);
        const position: XYZ = [edge.centre[0] + edge.radius * Math.cos(theta), edge.centre[1], edge.centre[2] + edge.radius * Math.sin(theta)];
        need(position.every(Number.isFinite), 'Nonfinite native curved geometry projection');
        return { position, yaw };
    }
    return { position: point(edge.from, edge.to, progress), yaw };
}
function sampledCarrier(carrier: Carrier, tick: number, geometry: Geometry) {
    let pose = carrier.pose;
    const motion = carrier.motion;
    if (motion && tick >= motion.start_tick && tick <= motion.planned_end_tick) {
        const elapsed = tick - motion.start_tick, duration = Math.max(1, motion.planned_end_tick - motion.start_tick), t = clamp(elapsed / duration);
        pose = { edge_id: motion.start.edge_id, progress: { numerator: lerp(ratio(motion.start.progress), ratio(motion.end.progress), t), denominator: 1 }, yaw_quarters: { numerator: interpolatedQuarters(motion.start.yaw_quarters, motion.end.yaw_quarters, elapsed, duration), denominator: 1 } };
    }
    if (!pose)
        return null;
    return { job_id: carrier.job_id, hu_id: carrier.hu_id, payload_id: carrier.payload_id, ...beltPose(pose, geometry), status: carrier.status };
}
function applyEvent(event: NativeEvent, workers: Map<string, Worker>, carriers: Map<string, Carrier>, relocations: Map<string, Relocation>, ends: Map<string, BeltPose>): void {
    if (event.actor_id && event.operation) {
        const worker = workers.get(event.actor_id);
        need(worker, 'Unknown recorded actor ' + event.actor_id);
        if (event.kind === 'operation_started') {
            worker.operation = event.operation;
            worker.node = null;
        }
        if (event.kind === 'operation_completed') {
            worker.node = event.operation.target_node;
            worker.operation = null;
        }
    }
    if (event.relocation)
        relocations.set(event.relocation.job_id, event.relocation);
    const e = event.belt_event;
    if (!e)
        return;
    const previous = carriers.get(e.job_id);
    const next: Carrier = { job_id: e.job_id, hu_id: e.hu_id, payload_id: e.payload_id, pose: e.pose ?? previous?.pose ?? null, status: e.kind, motion: previous?.motion ?? null };
    if (e.kind === 'motion_started' || e.kind === 'pivot_started') {
        const end = ends.get(e.job_id + '|' + e.planned_end_tick + '|' + e.kind.replace('_started', '_completed'));
        need(e.pose && end && e.planned_end_tick !== null, 'Native motion endpoint unavailable');
        next.motion = { start: e.pose, end, start_tick: e.tick, planned_end_tick: e.planned_end_tick };
    }
    else if (e.kind === 'motion_completed' || e.kind === 'pivot_completed' || e.kind === 'completed')
        next.motion = null;
    carriers.set(e.job_id, next);
}
function validateGeometry(data: ArmData, geometry: Geometry): void {
    const xyz = (value: XYZ) => need(Array.isArray(value) && value.length === 3 && value.every(Number.isFinite), 'Nonfinite native geometry coordinates');
    for (const position of geometry.nodes.values())
        xyz(position);
    for (const slot of geometry.slots.values()) {
        xyz(slot.position);
        need(Number.isFinite(slot.yaw), 'Nonfinite native geometry yaw');
    }
    for (const edge of geometry.edges.values()) {
        xyz(edge.from);
        xyz(edge.to);
        if (edge.centre !== undefined)
            xyz(edge.centre);
        if (edge.radius !== undefined)
            need(Number.isFinite(edge.radius) && edge.radius > 0, 'Invalid native geometry radius');
        if (edge.startAngle !== undefined)
            need(Number.isFinite(edge.startAngle), 'Nonfinite native geometry angle');
        if (edge.endAngle !== undefined)
            need(Number.isFinite(edge.endAngle), 'Nonfinite native geometry angle');
    }
    const operations = [...data.events.map(e => e.operation), ...data.captures.flatMap(s => s.workers.map(w => w.operation))];
    for (const operation of operations)
        if (operation)
            routePoints(operation, geometry);
    for (const capture of data.captures)
        for (const worker of capture.workers)
            if (worker.node)
                need(geometry.nodes.has(worker.node), 'Unknown captured actor node');
    for (const capture of data.captures) {
        for (const carrier of capture.carriers) {
            if (carrier.pose)
                beltPose(carrier.pose, geometry);
            if (carrier.motion) {
                beltPose(carrier.motion.start, geometry);
                beltPose(carrier.motion.end, geometry);
            }
        }
        for (const relocation of capture.relocations)
            need(geometry.slots.has(relocation.source_owner) && geometry.slots.has(relocation.destination_owner), 'Unknown captured relocation geometry slot');
    }
    for (const event of data.events) {
        if (event.belt_event?.pose)
            beltPose(event.belt_event.pose, geometry);
        if (event.relocation)
            need(geometry.slots.has(event.relocation.source_owner) && geometry.slots.has(event.relocation.destination_owner), 'Unknown relocation geometry slot');
    }
}
function motionEndpoints(data: ArmData): Map<string, BeltPose> {
    const ends = new Map<string, BeltPose>();
    for (const event of data.events) {
        const e = event.belt_event;
        if (e?.pose && (e.kind === 'motion_completed' || e.kind === 'pivot_completed'))
            ends.set(e.job_id + '|' + e.tick + '|' + e.kind, e.pose);
    }
    for (const capture of data.captures)
        for (const carrier of capture.carriers)
            if (carrier.motion) {
                for (const kind of ['motion_completed', 'pivot_completed'])
                    if (!ends.has(carrier.job_id + '|' + carrier.motion.planned_end_tick + '|' + kind))
                        ends.set(carrier.job_id + '|' + carrier.motion.planned_end_tick + '|' + kind, carrier.motion.end);
            }
    for (const event of data.events) {
        const e = event.belt_event;
        if (e && (e.kind === 'motion_started' || e.kind === 'pivot_started')) {
            need(ends.has(e.job_id + '|' + e.planned_end_tick + '|' + e.kind.replace('_started', '_completed')), 'Unsupported partial motion: recorded display endpoint unavailable');
        }
    }
    return ends;
}
export function compilePlayback(data: ArmData, geometry: Geometry) {
    validateGeometry(data, geometry);
    const observed = integer(data.catalog.observed_until_tick), ends = motionEndpoints(data);
    function sample(tick: number): PlaybackFrame {
        integer(tick);
        need(tick <= observed, 'Tick exceeds observed boundary');
        const capture = [...data.captures].reverse().find(s => s.tick <= tick)!;
        const workers = new Map(structuredClone(capture.workers).map(w => [w.actor_id, w]));
        const carriers = new Map(structuredClone(capture.carriers).map(c => [c.job_id, c]));
        const relocations = new Map(capture.relocations.map(r => [r.job_id, r]));
        for (const event of data.events)
            if (event.seq > capture.last_seq && event.tick <= tick)
                applyEvent(event, workers, carriers, relocations, ends);
        const actors = [...workers.values()].map(w => {
            const base = w.node ? geometry.nodes.get(w.node) : undefined;
            const pose = w.operation ? routePose(w.operation, tick, geometry) : { position: base ? [...base] as XYZ : undefined, yaw: 0 };
            need(pose.position, 'Recorded actor has no display endpoint');
            return { actor_id: w.actor_id, position: pose.position, yaw: pose.yaw, operation: w.operation?.kind ?? null };
        });
        const moved = [...relocations.values()].map(r => {
            const source = geometry.slots.get(r.source_owner)!, target = geometry.slots.get(r.destination_owner)!;
            const placed = r.placed_tick !== null && tick >= r.placed_tick, taken = r.taken_tick !== null && tick >= r.taken_tick;
            const actor = actors.find(a => a.actor_id === r.actor_id);
            const position: XYZ = placed ? [...target.position] : taken && actor ? [actor.position[0], .9, actor.position[2]] : [...source.position];
            return { ...r, custody: placed ? r.destination_owner : taken ? 'actor:' + r.actor_id : r.source_owner, position, yaw: placed ? target.yaw : taken && actor ? actor.yaw : source.yaw };
        });
        const collected = new Set(data.events.filter(e => e.kind === 'output_collected' && e.tick <= tick).map(e => e.order_id));
        const visible = [...carriers.values()].filter(c => !collected.has(c.job_id)).map(c => sampledCarrier(c, tick, geometry)).filter((c): c is NonNullable<typeof c> => c !== null);
        return { tick, actors, carriers: visible, relocations: moved };
    }
    return Object.freeze({ observed, sample });
}
/** One microsecond clock drives recorded poses. Seeking has no network side effects. */
export function createPlaybackClock(observed: number) {
    integer(observed);
    let tick = 0, playing = false, rate = 1;
    return Object.freeze({ get tick() { return tick; }, get playing() { return playing; }, get rate() { return rate; },
        seek(value: number) {
            integer(value);
            need(value <= observed, 'Tick exceeds observed boundary');
            tick = value;
            if (tick === observed)
                playing = false;
        },
        play() {
            if (tick === observed)
                tick = 0;
            playing = true;
        }, pause() { playing = false; },
        setRate(value: number) { need([1, 4, 10, 30, 60].includes(value), 'Invalid playback rate'); rate = value; },
        advance(seconds: number) {
            need(Number.isFinite(seconds) && seconds >= 0, 'Invalid clock elapsed');
            if (playing) {
                tick = Math.min(observed, tick + Math.round(seconds * rate * 1000000));
                if (tick === observed)
                    playing = false;
            }
        },
    });
}
