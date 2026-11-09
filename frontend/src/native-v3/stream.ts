/** ADR0099 raw authentication and bounded recorded-state projection. */
export type Json = Record<string, unknown>;
export type ArmName = 'baseline' | 'candidate';
export type Fraction = {
    numerator: number | bigint;
    denominator: number | bigint;
};
export type BeltPose = {
    edge_id: string;
    progress: Fraction;
    yaw_quarters: Fraction;
};
export type Operation = {
    kind: string;
    start_tick: number;
    planned_end_tick: number;
    source_node: string;
    target_node: string;
    route: {
        node_ids: string[];
        arc_ids: string[];
    };
};
export type Relocation = {
    actor_id: string;
    job_id: string;
    hu_id: string;
    source_owner: string;
    destination_owner: string;
    status: string;
    taken_tick: number | null;
    placed_tick: number | null;
    returned_tick: number | null;
};
export type BeltEvent = {
    job_id: string;
    hu_id: string;
    payload_id: string;
    kind: string;
    tick: number;
    planned_end_tick: number | null;
    pose: BeltPose | null;
};
export type NativeEvent = {
    seq: number;
    tick: number;
    kind: string;
    actor_id: string | null;
    order_id: string | null;
    operation: Operation | null;
    relocation: Relocation | null;
    belt_event: BeltEvent | null;
};
export type Carrier = {
    job_id: string;
    hu_id: string;
    payload_id: string;
    status: string;
    pose: BeltPose | null;
    motion: {
        start: BeltPose;
        end: BeltPose;
        start_tick: number;
        planned_end_tick: number;
    } | null;
};
export type Worker = {
    actor_id: string;
    node: string | null;
    operation: Operation | null;
};
export type Capture = {
    tick: number;
    last_seq: number;
    workers: Worker[];
    carriers: Carrier[];
    relocations: Relocation[];
};
export type Descriptor = {
    path: string;
    bytes: number;
    sha256: string;
};
export type ArmData = {
    header: Json;
    catalog: Json;
    captures: Capture[];
    events: NativeEvent[];
    retainedBytes: number;
};
type Options = {
    budgetBytes?: number;
    signal?: AbortSignal;
    progress?: (loaded: number, total: number) => void;
};
const MAX_MEMBER = 4 * 1024 * 1024;
const MAX_LINE = 6 * 1024 * 1024;
const encoder = new TextEncoder();
export function need(value: unknown, message: string): asserts value {
    if (!value)
        throw Error(message);
}
export function object(value: unknown): Json { need(value && typeof value === 'object' && !Array.isArray(value), 'Expected native object'); return value as Json; }
export function integer(value: unknown, minimum = 0): number { need(Number.isSafeInteger(value) && (value as number) >= minimum, 'Invalid native integer tick or bytes'); return value as number; }
const text = (value: unknown): string => { need(typeof value === 'string' && value.length > 0, 'Missing native identity'); return value; };
const digestText = (value: unknown): string => { need(typeof value === 'string' && /^[a-f0-9]{64}$/.test(value), 'Invalid native hash identity'); return value; };
const rows = (value: unknown): unknown[] => { need(Array.isArray(value), 'Missing native table'); return value; };
export function canonical(value: unknown): string {
    if (typeof value === 'bigint')
        return value.toString();
    if (Array.isArray(value))
        return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object')
        return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical((value as Json)[key])).join(',') + '}';
    need(typeof value !== 'number' || Number.isFinite(value), 'Nonfinite native value');
    return JSON.stringify(value);
}
export async function sha256(raw: Uint8Array): Promise<string> {
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array(raw)))].map(n => n.toString(16).padStart(2, '0')).join('');
}
/** Keep large native rational integers exact until the presentation conversion. */
export function parseNativeJSON(raw: string): unknown {
    let prefix = 'qoima-integer-' + crypto.randomUUID() + '-';
    while (raw.includes(prefix))
        prefix += 'x';
    const exact = new Map<string, bigint>(), pieces: string[] = [];
    let i = 0, start = 0;
    while (i < raw.length) {
        if (raw[i] === '"') {
            i++;
            for (;;) {
                const end = raw.indexOf('"', i);
                need(end >= 0, 'Unterminated native JSON string');
                let escapes = 0;
                for (let p = end - 1; raw[p] === '\\'; p--)
                    escapes++;
                i = end + 1;
                if (escapes % 2 === 0)
                    break;
            }
        }
        else if (raw[i] === '-' || /[0-9]/.test(raw[i])) {
            const from = i;
            while (i < raw.length && /[0-9eE+.\-]/.test(raw[i]))
                i++;
            const token = raw.slice(from, i);
            need(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(token), 'Invalid native JSON number syntax');
            if (/^-?\d+$/.test(token) && !Number.isSafeInteger(Number(token))) {
                const key = prefix + exact.size;
                exact.set(key, BigInt(token));
                pieces.push(raw.slice(start, from), JSON.stringify(key));
                start = i;
            }
        }
        else
            i++;
    }
    pieces.push(raw.slice(start));
    return JSON.parse(pieces.join(''), (_key, value: unknown) => typeof value === 'string' && exact.has(value) ? exact.get(value) : value);
}
function descriptor(value: unknown, maximum = MAX_MEMBER): Descriptor {
    const row = object(value), path = text(row.path), bytes = integer(row.bytes);
    need(/^(manifest\.json|catalog\.json|inputs\.json|events\/\d{8}\.json|snapshots\/\d{16}\.json)$/.test(path), 'Unknown native member path');
    need(bytes > 0 && bytes <= maximum, 'Native descriptor bytes exceed limit');
    return { path, bytes, sha256: digestText(row.sha256) };
}
function header(value: unknown, pair: string, arm: ArmName): {
    value: Json;
    descriptors: Map<string, Descriptor>;
} {
    const h = object(value);
    need(h.record_type === 'header' && h.schema_version === 'qoima-saved-relocation-arm-ndjson-0.1.0', 'Unsupported native stream version');
    need(h.pair_id === digestText(pair), 'Native pair identity differs');
    need(h.arm === arm, 'Native arm identity differs');
    need(h.origin === 'verified_saved_native_pair', 'Unsupported native origin');
    for (const key of ['native_run_id', 'input_hash', 'pair_input_hash', 'common_input_hash', 'registry_common_hash'])
        digestText(h[key]);
    const m = object(h.transport_manifest);
    need(m.schema_version === 'qoima-relocation-run-0.1.0' && m.transport_version === 'qoima-relocation-run-bundle-0.1.0' && m.engine_version === 'qoima-manual-relocation-proposal-1', 'Unsupported native transport version');
    need(m.run_id === h.native_run_id, 'Native run identity differs');
    for (const key of ['input_hash', 'common_input_hash', 'registry_common_hash'])
        need(m[key] === h[key], 'Native input identity differs');
    const input = descriptor(m.inputs, 64 * 1024 * 1024);
    need(input.path === 'inputs.json' && input.sha256 === h.input_hash, 'Omitted input descriptor differs');
    const expected = [descriptor(m.catalog), ...rows(m.event_chunks).map(v => descriptor(v)), ...rows(m.snapshot_chunks).map(v => descriptor(v))];
    need(expected[0].path === 'catalog.json' && expected.length < 128, 'Invalid native descriptor membership');
    need(new Set(expected.map(row => row.path)).size === expected.length, 'Duplicate native manifest member');
    const descriptions = rows(h.stream_descriptors).map(v => descriptor(v));
    need(descriptions.length === expected.length + 1, 'Incomplete native stream descriptors');
    const map = new Map(descriptions.map(v => [v.path, v]));
    need(map.size === descriptions.length && map.has('manifest.json') && !map.has('inputs.json'), 'Duplicate or omitted member descriptor');
    for (const row of expected)
        need(canonical(map.get(row.path)) === canonical(row), 'Native member descriptor mismatch');
    need(descriptions.reduce((sum, row) => sum + row.bytes, 0) <= 128 * 1024 * 1024, 'Native stream bytes limit exceeded');
    return { value: h, descriptors: map };
}
function operation(value: unknown): Operation | null {
    if (value === null || value === undefined)
        return null;
    const o = object(value), route = o.route ? object(o.route) : { node_ids: [o.source_node], arc_ids: [] };
    const start = integer(o.start_tick), end = integer(o.planned_end_tick);
    need(end >= start, 'Invalid operation interval');
    return { kind: text(o.kind), start_tick: start, planned_end_tick: end, source_node: text(o.source_node), target_node: text(o.target_node), route: { node_ids: rows(route.node_ids).map(text), arc_ids: rows(route.arc_ids).map(text) } };
}
function relocation(value: unknown): Relocation | null {
    if (value === null || value === undefined)
        return null;
    const r = object(value), nullable = (v: unknown) => v === null ? null : integer(v);
    return { actor_id: text(r.actor_id), job_id: text(r.job_id), hu_id: text(r.hu_id), source_owner: text(r.source_owner), destination_owner: text(r.destination_owner), status: text(r.status), taken_tick: nullable(r.taken_tick), placed_tick: nullable(r.placed_tick), returned_tick: nullable(r.returned_tick) };
}
function pose(value: unknown): BeltPose | null {
    if (value === null || value === undefined)
        return null;
    const p = object(value), exact = (v: unknown): number | bigint => { need(typeof v === 'bigint' || Number.isSafeInteger(v), 'Invalid native exact fraction integer'); return v as number | bigint; };
    const fraction = (v: unknown): Fraction => { const f = object(v), numerator = exact(f.numerator), denominator = exact(f.denominator); need(BigInt(denominator) > 0n, 'Invalid native fraction denominator'); return { numerator, denominator }; };
    const progress = fraction(p.progress);
    need(BigInt(progress.numerator) >= 0n && BigInt(progress.numerator) <= BigInt(progress.denominator), 'Invalid native belt progress');
    return { edge_id: text(p.edge_id), progress, yaw_quarters: fraction(p.yaw_quarters) };
}
function beltEvent(value: unknown): BeltEvent | null {
    if (!value)
        return null;
    const e = object(value);
    return { job_id: text(e.job_id), hu_id: text(e.hu_id), payload_id: text(e.payload_id), kind: text(e.kind), tick: integer(e.tick), planned_end_tick: e.planned_end_tick == null ? null : integer(e.planned_end_tick), pose: pose(e.pose) };
}
function event(value: unknown): NativeEvent {
    const e = object(value);
    return { seq: integer(e.seq), tick: integer(e.tick), kind: text(e.kind), actor_id: e.actor_id == null ? null : text(e.actor_id), order_id: e.order_id == null ? null : text(e.order_id), operation: operation(e.operation), relocation: relocation(e.relocation), belt_event: beltEvent(e.belt_event) };
}
function capture(value: unknown, outcomeKind: unknown): Capture {
    const s = object(value), belt = object(s.belt);
    const workers = rows(s.workers).map(value => { const w = object(value); return { actor_id: text(w.actor_id), node: w.node === null ? null : text(w.node), operation: operation(w.operation) }; });
    const carriers = rows(belt.carriers).map(value => {
        const c = object(value), motion = c.motion ? object(c.motion) : null;
        return { job_id: text(c.job_id), hu_id: text(c.hu_id), payload_id: text(c.payload_id), status: text(c.status), pose: pose(c.pose), motion: motion ? { start: pose(motion.start)!, end: pose(motion.end)!, start_tick: integer(motion.start_tick), planned_end_tick: integer(motion.planned_end_tick) } : null };
    });
    return { tick: integer(s.tick), last_seq: integer(s.last_seq, -1), workers, carriers, relocations: rows(outcomeKind === 'base_noop' && s.relocations === undefined ? [] : s.relocations).map(v => relocation(v)!) };
}
async function member(row: Json, expected: Map<string, Descriptor>, seen: Set<string>): Promise<{
    path: string;
    data: unknown;
}> {
    need(row.record_type === 'file', 'Expected native file record');
    const d = descriptor(row), declared = expected.get(d.path);
    need(declared && canonical(d) === canonical(declared), 'Unknown native member or descriptor');
    need(!seen.has(d.path), 'Duplicate native member');
    need(typeof row.body_base64 === 'string' && row.body_base64.length <= 6 * 1024 * 1024, 'Invalid native base64 member');
    const encoded = row.body_base64;
    need(encoded.length % 4 === 0 && !/[^A-Za-z0-9+/=]/.test(encoded) && !/=./.test(encoded.replace(/==$/, '=')), 'Invalid native base64 member');
    const decoded = atob(encoded), raw = Uint8Array.from(decoded, c => c.charCodeAt(0));
    need(raw.length === d.bytes, 'Native member bytes differ');
    need(await sha256(raw) === d.sha256, 'Native member hash differs');
    seen.add(d.path);
    return { path: d.path, data: parseNativeJSON(new TextDecoder('utf-8', { fatal: true }).decode(raw)) };
}
async function* lines(body: ReadableStream<Uint8Array>, signal?: AbortSignal): AsyncGenerator<string> {
    const reader = body.getReader(), decoder = new TextDecoder('utf-8', { fatal: true });
    let pending = '', transferred = 0, completed = false;
    try {
        for (;;) {
            signal?.throwIfAborted();
            const chunk = await reader.read();
            if (chunk.done)
                break;
            transferred += chunk.value.byteLength;
            need(transferred <= 192 * 1024 * 1024, 'Native transfer bytes limit exceeded');
            pending += decoder.decode(chunk.value, { stream: true });
            let end = pending.indexOf('\n');
            while (end >= 0) {
                need(end <= MAX_LINE, 'Native record bytes limit exceeded');
                yield pending.slice(0, end);
                pending = pending.slice(end + 1);
                end = pending.indexOf('\n');
            }
            need(pending.length <= MAX_LINE, 'Native record bytes limit exceeded');
        }
        pending += decoder.decode();
        if (pending)
            yield pending;
        completed = true;
    }
    finally {
        if (!completed)
            await reader.cancel().catch(() => undefined);
        reader.releaseLock();
    }
}
function finish(data: ArmData): void {
    const h = data.header, c = data.catalog;
    need(c.run_id === h.native_run_id && c.input_hash === h.input_hash && c.common_input_hash === h.common_input_hash && c.registry_common_hash === h.registry_common_hash, 'Native catalog identity differs');
    const end = integer(c.observed_until_tick);
    need(['complete', 'partial'].includes(text(c.status)), 'Unsupported native outcome status');
    data.captures.sort((a, b) => a.tick - b.tick);
    need(data.captures[0]?.tick === 0 && new Set(data.captures.map(s => s.tick)).size === data.captures.length, 'Missing initial capture or duplicate tick');
    need(data.captures.every(s => s.tick <= end), 'Capture exceeds observed end');
    data.events.sort((a, b) => a.seq - b.seq);
    need(data.events.every((e, i) => e.seq === i && e.tick <= end && (!i || e.tick >= data.events[i - 1].tick)), 'Native event sequence differs');
    for (const capture of data.captures) {
        const settled = data.events.reduce((last, event) => event.tick <= capture.tick ? event.seq : last, -1);
        need(capture.last_seq === settled, 'Captured native event watermark differs');
    }
}
function checkCaptureMetadata(frame: Capture, path: string, h: Json): void {
    const manifest = object(h.transport_manifest);
    const declared = rows(manifest.snapshot_chunks).map(object).find(row => row.path === path);
    need(declared && frame.tick === integer(declared.tick) && frame.last_seq === integer(declared.last_seq, -1), 'Native capture tick or watermark descriptor differs');
    need(path === 'snapshots/' + String(frame.tick).padStart(16, '0') + '.json', 'Native capture path tick differs');
}
function checkEventMetadata(batch: NativeEvent[], path: string, h: Json): void {
    const manifest = object(h.transport_manifest);
    const declared = rows(manifest.event_chunks).map(object).find(row => row.path === path);
    need(declared && batch.length > 0, 'Native event chunk descriptor missing');
    const start = integer(declared.start_tick), end = integer(declared.end_tick);
    need(start < end && batch.every(event => event.tick >= start && event.tick < end), 'Native event chunk tick interval differs');
    need(batch[0].seq === integer(declared.first_seq) && batch.at(-1)!.seq === integer(declared.last_seq), 'Native event chunk sequence descriptor differs');
}
export async function decodeArmStream(body: ReadableStream<Uint8Array>, pair: string, arm: ArmName, options: Options = {}): Promise<ArmData> {
    need(arm === 'baseline' || arm === 'candidate', 'Unknown native arm');
    const budget = options.budgetBytes ?? 64 * 1024 * 1024;
    need(Number.isSafeInteger(budget) && budget > 0 && budget <= 64 * 1024 * 1024, 'Invalid retained cache budget');
    let accepted: ReturnType<typeof header> | undefined;
    const seen = new Set<string>(), data: ArmData = { header: {}, catalog: {}, captures: [], events: [], retainedBytes: 0 };
    for await (const line of lines(body, options.signal)) {
        need(line.length > 0, 'Empty native stream record');
        const row = object(parseNativeJSON(line));
        if (!accepted) {
            accepted = header(row, pair, arm);
            data.header = accepted.value;
            data.retainedBytes = encoder.encode(line).length;
            continue;
        }
        const checked = await member(row, accepted.descriptors, seen);
        let projected: unknown = null;
        if (checked.path === 'manifest.json')
            need(canonical(checked.data) === canonical(data.header.transport_manifest), 'Native transport manifest differs');
        else if (checked.path === 'catalog.json') {
            data.catalog = object(checked.data);
            projected = checked.data;
        }
        else if (checked.path.startsWith('snapshots/')) {
            need(data.catalog.outcome_kind === 'base_noop' || data.catalog.outcome_kind === 'relocation', 'Catalog must precede native captures');
            const frame = capture(checked.data, data.catalog.outcome_kind);
            checkCaptureMetadata(frame, checked.path, data.header);
            data.captures.push(frame);
            projected = frame;
        }
        else {
            const content = Array.isArray(checked.data) ? checked.data : rows(object(checked.data).events);
            const batch = content.map(event);
            checkEventMetadata(batch, checked.path, data.header);
            data.events.push(...batch);
            projected = batch;
        }
        data.retainedBytes += encoder.encode(canonical(projected)).length;
        need(data.retainedBytes <= budget, 'Native retained cache budget exceeded');
        options.progress?.(seen.size, accepted.descriptors.size);
    }
    need(accepted && seen.size === accepted.descriptors.size, 'Missing members in incomplete native stream');
    finish(data);
    return data;
}
export function verifyArmPair(a: ArmData, b: ArmData): void {
    need(a.header.arm === 'baseline' && b.header.arm === 'candidate', 'Native pair arms differ');
    for (const key of ['pair_id', 'pair_input_hash', 'common_input_hash', 'registry_common_hash'])
        need(a.header[key] === b.header[key], 'Native pair input identity differs');
    need(a.retainedBytes + b.retainedBytes <= 64 * 1024 * 1024, 'Native pair cache budget exceeded');
}
