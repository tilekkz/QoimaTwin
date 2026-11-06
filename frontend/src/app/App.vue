<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { expected, fixtureRun, layout } from '../contracts';

const canvasHost = ref<HTMLDivElement>();
const status = ref('Проверка WebGL и локального GLB…');
const phase = ref<'loading' | 'ready' | 'error'>('loading');
const diagnostics = ref<Record<string, unknown>>({});
let dispose: (() => void) | undefined;
let active = true;

onMounted(async () => {
  try {
    const { mountCalibration } = await import('../scene/calibration');
    if (!active) return;
    const mounted = await mountCalibration(canvasHost.value!);
    if (!active) { mounted.dispose(); return; }
    dispose = mounted.dispose;
    diagnostics.value = mounted.diagnostics;
    phase.value = 'ready';
    status.value = 'Окружение готово: WebGL, метр, оси и GLB проверены';
  } catch (error) {
    if (!active) return;
    phase.value = 'error';
    status.value = error instanceof Error ? error.message : String(error);
  }
});

onBeforeUnmount(() => { active = false; dispose?.(); });
</script>

<template>
  <main :data-phase="phase">
    <h1>QoimaTwin · проверка окружения</h1>
    <p>Технический стенд перед дизайном склада. Показана калибровочная модель, не готовый twin.</p>
    <p role="status">{{ status }}</p>
    <div ref="canvasHost" class="canvas-host" aria-label="Калибровка масштаба и осей в 3D"></div>
    <dl>
      <dt>Контракт</dt><dd>{{ layout.schema_version }} / {{ layout.layout_version }}</dd>
      <dt>Геометрия</dt><dd>{{ layout.slots.length }} ячеек · {{ layout.nodes.length }} узел · {{ layout.edges.length }} ребра</dd>
      <dt>Ручная фикстура</dt><dd>{{ fixtureRun.scenario.provenance }}</dd>
      <dt>Контрольные числа</dt><dd>{{ expected.route_distance_m }} м · завершение {{ expected.completed_s.toFixed(7) }} с</dd>
    </dl>
    <details><summary>Результат калибровки</summary><pre id="diagnostics">{{ JSON.stringify(diagnostics, null, 2) }}</pre></details>
  </main>
</template>

<style>
body { margin: 0; background: #f3f4f5; color: #20252a; font: 16px/1.5 system-ui, sans-serif; }
main { max-width: 1100px; margin: auto; padding: 24px; }
h1 { font-size: 26px; }
.canvas-host { height: 360px; border: 1px solid #c9cfd4; background: #e7ebee; }
.canvas-host canvas { display: block; }
dl { display: grid; grid-template-columns: 190px 1fr; gap: 8px 16px; }
dd { margin: 0; overflow-wrap: anywhere; }
dt { font-weight: 600; }
pre { white-space: pre-wrap; }
[data-phase="error"] [role="status"] { color: #a12222; }
@media (max-width: 600px) { main { padding: 16px; } dl { grid-template-columns: 1fr; } }
</style>
