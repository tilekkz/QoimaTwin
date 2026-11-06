<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import type { AssetId, SceneStatus, ViewId } from '../scene/warehouse';
const calibration = new URLSearchParams(location.search).has('calibration');
const Calibration = defineAsyncComponent(() => import('./App.vue'));
const host=ref<HTMLDivElement>();
const phase=ref('loading'); const error=ref(''); const mode=ref<ViewId>('overview');
const gallery=ref(false); const status=ref<SceneStatus>();
const catalog=ref<{id:AssetId;label:string;note:string;reference:string}[]>([]);
let viewer: Awaited<ReturnType<typeof import('../scene/warehouse')['mountWarehouse']>> | undefined;
let active=true;
const current=computed(()=>catalog.value.find(a=>a.id===mode.value));
const base=import.meta.env.BASE_URL;
function choose(next:ViewId){mode.value=next;viewer?.setMode(next);gallery.value=false;}
onMounted(async()=>{
  if(calibration)return;
  try{
    const module=await import('../scene/warehouse');
    if(!active)return;
    catalog.value=[...module.assetCatalog];
    viewer=await module.mountWarehouse(host.value!,value=>{status.value=value;});
    if(!active){viewer.dispose();return;}
    phase.value='ready';
    Object.assign(window,{__QOIMA_VIEWER__:{getState:viewer.getState}});
  }catch(reason){error.value=reason instanceof Error?reason.message:String(reason);phase.value='error';}
});
onBeforeUnmount(()=>{active=false;viewer?.dispose();});
</script>

<template>
  <Calibration v-if="calibration" />
  <main v-else class="studio" :data-phase="phase">
    <header class="masthead">
      <a class="wordmark" href="./" aria-label="QoimaTwin, общий вид"><span class="brand-icon">Q</span>Qoima<span>Twin</span></a>
      <div class="project-meta"><b></b>Модель склада<i>/</i>20 × 18 м</div>
      <button class="text-button" @click="gallery=!gallery" :aria-expanded="gallery">{{gallery?'Вернуться к модели':'Референсы'}} <span>↗</span></button>
    </header>
    <section class="viewport" aria-label="Интерактивная 3D-модель склада">
      <div ref="host" class="scene-host"></div>
      <div class="scene-heading"><div class="eyebrow">КОЛЛЕКЦИЯ / 01</div><h1>{{current?.label||'Склад в миниатюре'}}</h1><p>{{current?.note||'Четыре прохода. Двадцать адресов. Каждая деталь на своём месте.'}}</p></div>
      <div v-if="phase!=='ready'" class="loading" role="status">{{error||'Собираем пространство…'}}</div>
      <nav class="camera-tools" aria-label="Камера"><button @click="choose('overview')" :disabled="phase!=='ready'">Обзор <span>↖</span></button><button @click="viewer?.top()" :disabled="phase!=='ready'">Сверху <span>⊞</span></button><button @click="viewer?.focusSlot('S_A1_B1')" :disabled="phase!=='ready'||mode!=='overview'">Детали <span>⌕</span></button></nav>
      <div v-if="status?.selected" class="selection-tag">{{status.selected}}<small>Ячейка комплектации</small></div>
      <div class="interaction-hint">↔ &nbsp; Вращайте сцену <i>·</i> Колесо — приближение <i>·</i> Нажмите на стеллаж</div>
      <span class="scene-caption">{{mode==='overview'?'Визуальная сборка · позы сотрудников иллюстративные':'Осмотр отдельной модели · масштаб в метрах'}}</span>
    </section>
    <footer class="asset-dock">
      <button class="overview-tile" :class="{active:mode==='overview'}" @click="choose('overview')"><b>▦</b><span>Весь склад<small>Общий обзор</small></span></button><div class="dock-divider"></div>
      <div class="asset-list" aria-label="Модели"><button v-for="(asset,index) in catalog" :key="asset.id" :data-asset="asset.id" :class="{active:mode===asset.id}" @click="choose(asset.id)"><small>{{String(index+1).padStart(2,'0')}}</small><span>{{asset.label}}</span></button></div>
    </footer>
    <aside v-if="gallery" class="reference-gallery" aria-label="Сгенерированные референсы">
      <div class="gallery-title"><div><div class="eyebrow">ART DIRECTION</div><h2>От референса к объёму</h2><p>Восемь отдельных листов. Согласованные материалы и несколько ракурсов каждого ассета.</p></div><button @click="gallery=false" aria-label="Закрыть референсы">×</button></div>
      <div class="gallery-grid"><figure v-for="asset in catalog" :key="asset.id"><a :href="`${base}references/${asset.reference}`" target="_blank" rel="noreferrer"><img :src="`${base}references/${asset.reference}`" :alt="`Референс: ${asset.label}, несколько ракурсов`" loading="lazy" /></a><figcaption><strong>{{asset.label}}</strong><span>{{asset.note}}</span><button @click="choose(asset.id)">Открыть 3D ↗</button></figcaption></figure></div>
    </aside>
  </main>
</template>

<style>
:root{font-family:'Segoe UI',Arial,sans-serif;color:#283b3b;background:#e9e7e0;font-synthesis:none}*{box-sizing:border-box}body{margin:0}button{font:inherit;color:inherit;cursor:pointer}button:disabled{opacity:.4;cursor:default}button:focus-visible,a:focus-visible{outline:2px solid #b47522;outline-offset:4px}
.studio{width:100%;height:100dvh;min-height:580px;display:flex;flex-direction:column;overflow:hidden}.masthead{height:78px;flex-shrink:0;margin:0 32px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #bac2bb70;position:relative;z-index:2}.wordmark{display:flex;align-items:center;gap:3px;font-size:22px;font-weight:650;color:#273f3e;text-decoration:none;letter-spacing:-.7px}.wordmark>span:last-child{font-weight:350}.brand-icon{display:grid;place-items:center;width:33px;height:33px;background:#2c4b46;color:#f7f0dc;border-radius:9px;font-size:22px;margin-right:10px;font-family:Georgia,serif;font-weight:400}.project-meta{display:flex;align-items:center;gap:10px;color:#6b7970;font-size:12px}.project-meta b{width:6px;height:6px;border-radius:50%;background:#6a8b70}.project-meta i{font-style:normal;opacity:.35;margin:0 7px}.text-button{border:0;background:transparent;font-size:12px}.text-button span{margin-left:16px}
.viewport{position:relative;flex:1;min-height:300px}.scene-host{position:absolute;inset:0;touch-action:none}.scene-host canvas{display:block;width:100%;height:100%}.scene-heading{position:absolute;top:28px;left:34px;pointer-events:none;max-width:430px}.viewport:has(.selection-tag) .scene-heading{visibility:hidden}.eyebrow{font-size:9px;letter-spacing:2.3px;color:#8b9586;font-weight:600}.scene-heading h1{font-size:clamp(24px,2.5vw,36px);margin:11px 0 8px;font-weight:420;letter-spacing:-1px}.scene-heading p{margin:0;font-size:11px;color:#788476;max-width:390px;line-height:1.6}.camera-tools{position:absolute;right:32px;top:32px;display:flex;gap:5px}.camera-tools button{border:1px solid #cbd0c4;border-radius:7px;background:#f5f3ebd9;padding:11px 13px;font-size:11px}.camera-tools button span{margin-left:18px;color:#87947f}.camera-tools button:hover:not(:disabled){background:#fffdf4}.interaction-hint{position:absolute;left:34px;bottom:16px;color:#899183;font-size:10px;pointer-events:none}.interaction-hint i{font-style:normal;margin:0 9px;color:#a1a895}.scene-caption{position:absolute;right:34px;bottom:20px;font-size:9px;color:#909788;pointer-events:none}.selection-tag{position:absolute;right:32px;top:90px;background:#fcf8eced;border-left:3px solid #d4a345;padding:14px 20px;font-size:13px;box-shadow:0 5px 30px #3b463718}.selection-tag small{display:block;font-size:10px;color:#88927d;margin-top:5px}.loading{position:absolute;inset:0;display:grid;place-items:center;background:#e9e7e0e8;font-size:15px}[data-phase=error] .loading{color:#9a463a;padding:30px}
.asset-dock{margin:0 28px 22px;height:88px;flex-shrink:0;display:flex;gap:18px;align-items:center;border:1px solid #d1d3c5;padding:10px 12px;background:#f5f3eccc;border-radius:12px}.overview-tile{min-width:146px;display:flex;align-items:center;gap:12px;border:0;background:transparent;padding:12px;text-align:left;font-size:12px;border-radius:8px}.overview-tile>b{font-size:30px;color:#8a9c89;font-weight:400}.overview-tile small{display:block;margin-top:4px;color:#899784;font-size:9px}.dock-divider{height:42px;width:1px;background:#d2d6c8;flex-shrink:0}.asset-list{display:flex;justify-content:space-around;flex:1;gap:5px;overflow-x:auto}.asset-list button{display:flex;flex-direction:column;gap:10px;align-items:flex-start;padding:12px 16px;border:0;background:transparent;text-align:left;white-space:nowrap;border-radius:7px;font-size:10px}.asset-list small{color:#95a18e;font-size:9px;font-variant-numeric:tabular-nums}.asset-list button.active,.overview-tile.active{background:#e3e8da;color:#345443}.asset-list button:hover{background:#e9ecdf}
.reference-gallery{position:absolute;inset:78px 0 0;z-index:5;overflow:auto;background:#eeede5;padding:30px}.gallery-title{display:flex;justify-content:space-between;max-width:1400px;margin:auto auto 28px}.gallery-title h2{font-size:30px;font-weight:400;margin:8px 0}.gallery-title p{font-size:12px;color:#809078}.gallery-title>button{border:0;background:transparent;font-size:30px;align-self:flex-start}.gallery-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;max-width:1400px;margin:auto}.gallery-grid figure{margin:0;background:#faf8f1;border:1px solid #d5d8ca}.gallery-grid img{display:block;width:100%;aspect-ratio:1.2;object-fit:contain;background:#bababa}.gallery-grid figcaption{padding:16px;display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center}.gallery-grid strong{font-size:13px;font-weight:500}.gallery-grid figcaption span{font-size:11px;color:#859177;flex:1}.gallery-grid figcaption button{border:0;background:transparent;font-size:11px}
@media(max-width:900px){.project-meta{display:none}.scene-caption{display:none}.asset-dock{margin:0 12px 12px;gap:8px}.asset-list button{padding:10px}.overview-tile{min-width:118px;padding:6px}.masthead{margin:0 20px;height:66px}.scene-heading{left:20px;top:20px}.scene-heading p{max-width:230px}.camera-tools{right:16px;top:110px}.interaction-hint{left:20px;font-size:9px}.reference-gallery{inset:66px 0 0}}@media(max-width:600px){.studio{min-height:620px}.gallery-grid{grid-template-columns:1fr}.reference-gallery{padding:20px}.scene-heading h1{font-size:28px}.scene-heading p{display:none}.camera-tools{left:20px;right:auto;top:100px}.overview-tile{min-width:100px}.overview-tile>b{display:none}.interaction-hint{font-size:8px}.interaction-hint i{margin:0 4px}}
</style>
