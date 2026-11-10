import type { VisualEvent, VisualFrame } from './types';
export type SoundCategory = 'ambience' | 'mechanical' | 'feedback';
type Cue = { id: string; source: string; category: SoundCategory; frequency: number; duration: number; priority: number; texture?: 'step' | 'tape' };
const cues: Record<string, Omit<Cue, 'id' | 'source'>> = {
  sku_picked: { category: 'feedback', frequency: 780, duration: .09, priority: 2 },
  tote_inducted: { category: 'mechanical', frequency: 190, duration: .12, priority: 1 },
  order_packed: { category: 'feedback', frequency: 620, duration: .16, priority: 2 },
  parcel_scanned: { category: 'feedback', frequency: 980, duration: .07, priority: 3 },
  pallet_sealed: { category: 'mechanical', frequency: 140, duration: .18, priority: 1 },
  order_dispatched: { category: 'feedback', frequency: 880, duration: .23, priority: 4 },
  receipt_accepted: { category: 'mechanical', frequency: 240, duration: .13, priority: 1 },
  pallet_putaway: { category: 'mechanical', frequency: 170, duration: .12, priority: 1 },
  visual_footstep: { category: 'mechanical', frequency: 420, duration: .065, priority: 0, texture: 'step' },
  visual_tape: { category: 'mechanical', frequency: 1400, duration: .16, priority: 1, texture: 'tape' },
};

/** Pure limiter is testable without an AudioContext or audible output. */
export class CueScheduler {
  private seen = new Set<string>();
  private cooldown = new Map<string, number>();
  private voices: { cue: Cue; until: number }[] = [];
  private acceleratedAt = -Infinity;
  emitted = 0;
  dropped = 0;
  reset() { this.seen.clear(); this.cooldown.clear(); this.voices = []; this.acceleratedAt = -Infinity; }
  stop() { this.voices = []; }
  count(now: number) { this.voices = this.voices.filter(v => v.until > now); return this.voices.length; }
  plan(events: VisualEvent[], now: number, speed: number): Cue[] {
    this.count(now);
    const result: Cue[] = [];
    const candidates = speed >= 10 ? [...events].sort((a, b) => (cues[b.kind]?.priority ?? 0) - (cues[a.kind]?.priority ?? 0)) : events;
    for (const e of candidates) {
      const key = e.seq + ':' + e.at_s + ':' + e.kind + ':' + e.entity_id;
      if (this.seen.has(key)) continue;
      this.seen.add(key);
      const definition = cues[e.kind]; if (!definition) continue;
      const source = String(e.payload.actor_id ?? e.entity_id);
      if (now - (this.cooldown.get(source) ?? -Infinity) < .22 || speed >= 10 && now - this.acceleratedAt < 1.5) { this.dropped++; continue; }
      const cue: Cue = { ...definition, id: key, source };
      if (this.voices.length >= 4) {
        const lowest = this.voices.reduce((best, v, i, list) => v.cue.priority < list[best].cue.priority ? i : best, 0);
        if (this.voices[lowest].cue.priority >= cue.priority) { this.dropped++; continue; }
        this.voices.splice(lowest, 1);
      }
      this.voices.push({ cue, until: now + cue.duration }); this.cooldown.set(source, now); this.acceleratedAt = now; this.emitted++; result.push(cue);
    }
    // Bound dedup memory during multi-hour playback. Controller already supplies
    // crossed-only events; this set is just defensive for repeated UI delivery.
    if (this.seen.size > 4096) this.seen = new Set([...this.seen].slice(-2048));
    return result;
  }
}

export function createSfxController(options: { createContext?: () => AudioContext } = {}) {
  const scheduler = new CueScheduler();
  let context: AudioContext | undefined, muted = true, unlocked = false, volume = .18, disposed = false;
  let categories: Record<SoundCategory, boolean> = { ambience: true, mechanical: true, feedback: true };
  const active = new Map<string, { source: OscillatorNode | AudioBufferSourceNode; gain: GainNode; priority: number }>();
  const motionCursors = new Map<string, number>();
  let currentLoopCategory: SoundCategory | undefined;
  const persist = () => { try { localStorage.setItem('qoima-audio-v2', JSON.stringify({ volume, categories })); } catch { /* Optional browser preference. */ } };
  try { const saved = JSON.parse(localStorage.getItem('qoima-audio-v2') || 'null'); if (saved && typeof saved.volume === 'number') volume = Math.max(0, Math.min(1, saved.volume)); if (saved?.categories) for (const key of Object.keys(categories) as SoundCategory[]) if (typeof saved.categories[key] === 'boolean') categories[key] = saved.categories[key]; } catch { /* Node tests/private browsing. */ }
  const stop = () => { for (const voice of active.values()) { try { voice.source.stop(); } catch { /* Already ended. */ } voice.gain.disconnect(); } active.clear(); scheduler.stop(); currentLoopCategory = undefined; motionCursors.clear(); };
  const sound = (cue: Cue) => {
    if (!context || muted || !unlocked || !categories[cue.category]) return;
    if (active.size >= 4) { const lowest = [...active.entries()].sort((a, b) => a[1].priority - b[1].priority)[0]; if (lowest[1].priority >= cue.priority) return; lowest[1].source.stop(); active.delete(lowest[0]); }
    const gain = context.createGain(), now = context.currentTime;
    let source: OscillatorNode | AudioBufferSourceNode;
    let filter: BiquadFilterNode | undefined;
    if (cue.texture) {
      // Original, deterministic noise synthesis. No sampled/third-party media.
      const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * cue.duration), context.sampleRate);
      const data = buffer.getChannelData(0); let seed = 1977;
      for (let i = 0; i < data.length; i++) { seed = (Math.imul(seed, 1664525) + 1013904223) | 0; data[i] = seed / 2147483648 * (cue.texture === 'step' ? .35 : .2); }
      const noise = context.createBufferSource(); noise.buffer = buffer; source = noise;
      filter = context.createBiquadFilter(); filter.type = cue.texture === 'step' ? 'lowpass' : 'bandpass'; filter.frequency.value = cue.frequency; filter.Q.value = .7;
      noise.connect(filter); filter.connect(gain);
    } else {
      const oscillator = context.createOscillator(); source = oscillator;
      oscillator.type = cue.category === 'mechanical' ? 'triangle' : 'sine'; oscillator.frequency.setValueAtTime(cue.frequency, now); oscillator.frequency.exponentialRampToValueAtTime(cue.frequency * .82, now + cue.duration); oscillator.connect(gain);
    }
    gain.gain.setValueAtTime(0, now); gain.gain.linearRampToValueAtTime(Math.min(.08, volume * .25), now + .008); gain.gain.exponentialRampToValueAtTime(.0001, now + cue.duration);
    gain.connect(context.destination); active.set(cue.id, { source, gain, priority: cue.priority });
    source.onended = () => { gain.disconnect(); filter?.disconnect(); active.delete(cue.id); }; source.start(now); source.stop(now + cue.duration + .01);
  };
  const syncMotor = (frame: VisualFrame) => {
    if (!context) return;
    const forkliftMoving = Object.values(frame.actors).some(a => a.role === 'forklift_driver' && a.state === 'TRAVEL');
    const beltMoving = !frame.line.blocked && Object.values(frame.cargo).some(c => c.visible && c.stage.includes('conveyor'));
    const category: SoundCategory | undefined = forkliftMoving ? 'mechanical' : beltMoving ? 'ambience' : undefined;
    const previous = active.get('loop:motor');
    if (previous && (category !== currentLoopCategory || !category || !categories[category])) { previous.source.stop(); active.delete('loop:motor'); currentLoopCategory = undefined; }
    if (!category || !categories[category] || active.has('loop:motor') || active.size >= 4) return;
    const source = context.createOscillator(), gain = context.createGain();
    source.type = 'sine'; source.frequency.value = forkliftMoving ? 82 : 58;
    gain.gain.setValueAtTime(volume * .025, context.currentTime); source.connect(gain); gain.connect(context.destination);
    active.set('loop:motor', { source, gain, priority: -1 }); currentLoopCategory = category;
    source.onended = () => { gain.disconnect(); if (active.get('loop:motor')?.source === source) active.delete('loop:motor'); }; source.start();
  };
  return {
    async unlock() { if (disposed) return false; try { context ??= options.createContext?.() ?? new AudioContext(); await context.resume(); unlocked = context.state === 'running'; return unlocked; } catch { return false; } },
    setMuted(value: boolean) { muted = value; if (muted) stop(); },
    setVolume(value: number) { volume = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0)); stop(); persist(); },
    setCategory(category: SoundCategory, enabled: boolean) { categories = { ...categories, [category]: enabled }; if (!enabled) stop(); persist(); },
    stop,
    update(frame: VisualFrame, options: { playing: boolean; speed: number; discontinuity?: boolean }, wallSeconds = typeof performance !== 'undefined' ? performance.now() / 1000 : 0) {
      if (disposed) return;
      if (options.discontinuity) { stop(); scheduler.reset(); return; }
      if (!options.playing) { stop(); return; }
      // Muted/unlocked checks happen before scheduling so automated QA stays silent.
      if (muted || !unlocked) return;
      const events = [...frame.events];
      if (options.speed < 10) for (const [index, actor] of Object.values(frame.actors).entries()) {
        const kind = actor.state === 'TRAVEL' && actor.role !== 'forklift_driver' ? 'visual_footstep' : actor.state === 'BUSY_SERVICE' && actor.operation === 'pack' ? 'visual_tape' : undefined;
        if (!kind) continue;
        const cursor = Math.floor(frame.time * (kind === 'visual_footstep' ? 2.2 : 1));
        const key = actor.id + ':' + kind, previous = motionCursors.get(key); motionCursors.set(key, cursor);
        if (previous !== undefined && previous !== cursor) events.push({ seq: -1000000 - index * 10000 - cursor, at_s: frame.time, phase: 0, kind, entity_id: actor.id, payload: { actor_id: actor.id } });
      }
      for (const cue of scheduler.plan(events, wallSeconds, options.speed)) sound(cue);
      syncMotor(frame);
    },
    getState: () => ({ muted, unlocked, volume, categories: { ...categories }, voices: active.size, cues: scheduler.emitted, dropped: scheduler.dropped, disposed }),
    dispose() { stop(); disposed = true; if (context) void context.close(); },
  };
}
