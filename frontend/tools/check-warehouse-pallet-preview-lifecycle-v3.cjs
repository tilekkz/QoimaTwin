/* COMPONENT_ONLY. CPU only; no browser, assets, renderer or public bootstrap.
 * Regression derived from immutable account2 component probes (20261108T152113Z).
 * Reproduce from repository root:
 * node frontend/tools/check-warehouse-pallet-preview-lifecycle-v3.cjs [--check-only]
 * The exact current preview module is transpiled in memory. Runtime imports, DOM,
 * RAF and timers are isolated stubs. import.meta.env.BASE_URL is replaced by '/'.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const checkOnly = process.argv.slice(2).includes('--check-only');
if(process.argv.slice(2).some(arg=>arg!=='--check-only'))throw Error('UNKNOWN_ARGUMENT');
const checkerPath='frontend/tools/check-warehouse-pallet-preview-lifecycle-v3.cjs';
const evidencePath='docs/adaptive-v3/evidence/W05.4.4-lifecycle-checks.json';
const sha256=value=>crypto.createHash('sha256').update(value).digest('hex');
const ts = require(path.join(root, 'frontend/node_modules/typescript/lib/typescript.js'));
const sourcePath = 'frontend/src/adaptive-v3/warehousePalletTransferPreview.ts';
const sourceBytes=fs.readFileSync(path.join(root,sourcePath));
const source=sourceBytes.toString('utf8');
const code = ts.transpileModule(source.replaceAll('import.meta.env.BASE_URL', "'/'"), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; };
class Element {
  constructor(tag='div') { this.tagName=tag;this.children=[];this.listeners=new Map();this.disabled=false;this.checked=false;this.value='';this.textContent=''; }
  addEventListener(type,fn,opts={}) {const rows=this.listeners.get(type)||[];rows.push({fn,capture:!!opts.capture,signal:opts.signal});this.listeners.set(type,rows);}
  fire(type) { for(const row of [...(this.listeners.get(type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture))) if(!row.signal?.aborted)row.fn({type,target:this}); }
  set innerHTML(value) { this.nodes = new Map();for(const match of value.matchAll(/<(\w+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){const e=new Element(match[1]);e.id=match[3];e.disabled=/\bdisabled\b/.test(match[2]);e.checked=/\bchecked\b/.test(match[2]);this.nodes.set(e.id,e);}this.nodes.get('pallet-speed').value='4'; }
  querySelector(q) {return this.nodes.get(q.slice(1));}
  querySelectorAll(q) {return q==='button'?this.children.filter(x=>x.tagName==='button'):[];}
  after(value) {this.inserted=value;}
  append(value) {this.children.push(value);}
  replaceChildren(...values) {this.children=values;}
  remove() {this.removed=true;}
}
function setup(options={}) {
  const nodes=new Map(['warehouse-holder-panel','route-select','holder-select','holder-reset'].map(x=>[x,new Element()]));
  const document=new Element();document.createElement=tag=>new Element(tag);document.getElementById=id=>nodes.get(id);
  const timers=new Map(),rafs=new Map();let nextId=0;
  const stats={readers:[],runs:[],begins:0,follows:[],refresh:0,fetches:0};
  const plan={duration_s:10,phases:[{phase_id:'source_lift_attached',start_s:2},{phase_id:'target_controlled_withdraw',start_s:8},{kind:'route',attached:true,start_s:3,end_s:7}]};
  const scene={
    prepareActionCatalogue:async(read,signal)=>options.prepare?options.prepare(signal):{},
    beginPalletTransfer:()=>{stats.begins++;let current=null,closed=false;const state={disposeCalls:0};const run={
      apply:(seconds)=>{if(closed)throw Error('CLOSED');if(options.failApply&&(typeof options.failApply!=='function'||options.failApply()))throw Error('CHANGED_NATIVE_BINDING');current={at_s:Math.max(0,Math.min(10,seconds)),phase_id:'loaded_route'};return current;},
      snapshot:()=>current,dispose:()=>{state.disposeCalls++;closed=true;current=null;},state
    };stats.runs.push(run);return run;},
    setFollowActor:id=>stats.follows.push(id)
  };
  const exports={};
  const context=vm.createContext({exports,require:id=>{
    if(id==='./warehouseActionSources')return {createWarehouseActionSourceReader:({signal})=>{const reader={disposed:false,signal,readSource:async()=>new Uint8Array(),dispose(){this.disposed=true;}};stats.readers.push(reader);return reader;}};
    if(id==='./warehouseRouting')return {validateRoutePolicy:async()=>({})};
    if(id==='./warehousePalletTransferPlan')return {compileWarehousePalletTransferPlan:()=>({ok:true,plan})};
    throw Error('Unexpected runtime import '+id);
  },document,AbortController,DOMException,Error,performance:{now:()=>0},matchMedia:()=>new Element(),
  setTimeout:(fn,ms)=>{const id=++nextId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
  requestAnimationFrame:fn=>{const id=++nextId;rafs.set(id,fn);return id;},cancelAnimationFrame:id=>rafs.delete(id),
  fetch:async(url,{signal})=>{stats.fetches++;if(options.fetch)return options.fetch(signal);if(signal.aborted)throw new DOMException('Aborted','AbortError');return {ok:true,text:async()=>'{"stub":true}'};}
  });
  vm.runInContext(code,context,{filename:sourcePath});
  if(options.before)options.before(nodes,stats);
  const preview=exports.createWarehousePalletTransferPreview({},scene,{stopOthers:options.stopOthers|| (async()=>{}),focusActor:()=>true,refresh:()=>stats.refresh++});
  return {preview,stats,nodes,panel:nodes.get('warehouse-holder-panel').inserted,timers,rafs};
}
const results=[];
async function check(id,fn){try {const detail=await fn();results.push({id,outcome:'PASS',...detail});}catch(e){results.push({id,outcome:'FAIL',error:e.stack});}}
const drain=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
(async()=>{
  await check('C01_DEFAULT_PAUSED_FINITE_TIME',async()=>{const h=setup();assert.equal(await h.preview.activate(),true);assert.equal(h.preview.snapshot().phase,'ready');assert.equal(h.preview.snapshot().playing,false);assert.equal(h.rafs.size,0);assert.equal(h.preview.seek(NaN),false);assert.equal(h.preview.seek(Infinity),false);assert.equal(h.preview.seek(-5),true);assert.equal(h.preview.snapshot().at_s,0);assert.equal(h.preview.seek(50),true);assert.equal(h.preview.snapshot().at_s,10);h.preview.stop();assert.equal(h.stats.runs[0].state.disposeCalls,1);return {classification:'bounded_no_additional_issue'};});
  await check('C02_ERROR_PERSISTENCE',async()=>{let fail=false;const h=setup({failApply:()=>fail});assert.equal(await h.preview.activate(),true);fail=true;assert.equal(h.preview.seek(2),false);const before=h.preview.snapshot();h.panel.querySelector('#pallet-reset').fire('click');const afterReset=h.preview.snapshot();h.preview.stop();const afterStop=h.preview.snapshot();assert.equal(before.error,'CHANGED_NATIVE_BINDING');assert.equal(afterReset.error,before.error);assert.equal(afterStop.error,before.error);assert.equal(afterStop.phase,'idle');assert.equal(h.panel.querySelector('#pallet-status').textContent,'Предыдущий показ остановлен из-за ошибки. Подготовьте перенос заново.');assert.ok(!h.panel.querySelector('#pallet-status').textContent.includes(before.error));assert.equal(h.stats.runs[0].state.disposeCalls,1);h.preview.stop();assert.equal(h.preview.snapshot().error,before.error);assert.equal(h.stats.runs[0].state.disposeCalls,1);for(const id of ['route-select','holder-select']){fail=false;assert.equal(await h.preview.activate(),true);assert.equal(h.preview.snapshot().error,null);fail=true;assert.equal(h.preview.seek(2),false);h.nodes.get(id).fire('change');assert.equal(h.preview.snapshot().error,before.error);assert.equal(h.preview.snapshot().phase,'idle');}h.preview.dispose();return {classification:'regression_green',finding:'W0544-A2-001',before,afterReset,afterStop,legacyCancellationRetainsDiagnostic:true};});
  await check('C03_FAILED_INITIAL_APPLY_OWNERSHIP',async()=>{const h=setup({failApply:true});const returned=await h.preview.activate();const snapshot=h.preview.snapshot(),disposeCalls=h.stats.runs[0].state.disposeCalls;assert.equal(returned,false);assert.equal(snapshot.phase,'error');assert.equal(snapshot.error,'CHANGED_NATIVE_BINDING');assert.equal(disposeCalls,1);assert.equal(h.stats.readers[0].disposed,true);assert.equal(snapshot.frame,null);assert.equal(snapshot.duration_s,null);assert.equal(h.panel.querySelector('#pallet-stages').children.length,0);assert.equal(h.rafs.size,0);h.preview.stop();assert.equal(h.stats.runs[0].state.disposeCalls,1);assert.equal(h.preview.snapshot().error,snapshot.error);h.preview.dispose();return {classification:'regression_green',finding:'W0544-A2-002',returned,snapshot,disposeCalls,readerDisposed:true};});
  await check('C04_DISPOSE_STOP_REACTIVATE',async()=>{const h=setup();h.preview.dispose();assert.equal(h.preview.snapshot().phase,'disposed');const refreshBefore=h.stats.refresh,followsBefore=h.stats.follows.length;h.preview.stop();const afterStop=h.preview.snapshot();const returned=await h.preview.activate();assert.equal(afterStop.phase,'disposed');assert.equal(returned,false);assert.equal(h.stats.begins,0);assert.equal(h.stats.readers.length,0);assert.equal(h.stats.refresh,refreshBefore);assert.equal(h.stats.follows.length,followsBefore);assert.equal(h.panel.removed,true);h.preview.dispose();assert.equal(h.preview.snapshot().phase,'disposed');return {classification:'regression_green',finding:'W0544-A2-003',afterStop,returned,panelRemoved:true};});
  await check('C05_STOP_DURING_PREPARE',async()=>{const d=deferred();const h=setup({prepare:()=>d.promise});const pending=h.preview.activate();await drain();h.preview.stop();d.resolve({});assert.equal(await pending,false);assert.equal(h.stats.begins,0);assert.equal(h.preview.snapshot().phase,'idle');return {classification:'bounded_no_additional_issue'};});
  await check('C06_DISPOSE_DURING_PREPARE',async()=>{const d=deferred();const h=setup({prepare:()=>d.promise});const pending=h.preview.activate();await drain();h.preview.dispose();d.resolve({});assert.equal(await pending,false);assert.equal(h.stats.begins,0);assert.equal(h.preview.snapshot().phase,'disposed');return {classification:'bounded_no_additional_issue'};});
  await check('C07_LATEST_REQUEST_WINS',async()=>{const d=deferred();let calls=0;const h=setup({prepare:()=>++calls===1?d.promise:Promise.resolve({})});const old=h.preview.activate();await drain();const latest=h.preview.activate();assert.equal(await latest,true);d.resolve({});assert.equal(await old,false);assert.equal(h.stats.begins,1);assert.equal(h.preview.snapshot().phase,'ready');h.preview.stop();return {classification:'bounded_no_additional_issue'};});
  await check('C08_POLICY_ABORT_DEADLINE',async()=>{const h=setup({fetch:signal=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}))});const pending=h.preview.activate();await drain();const timer=[...h.timers.values()].find(x=>x.ms===30000);assert.ok(timer);timer.fn();assert.equal(await pending,false);assert.equal(h.preview.snapshot().error,'PALLET_PREPARE_TIMEOUT');assert.equal(h.stats.readers[0].disposed,true);return {classification:'bounded_no_additional_issue',deadlineMs:30000};});
  await check('C09_CAPTURE_PHASE_LEGACY_SELECTORS',async()=>{const observations=[];const h=setup({before:(nodes,stats)=>{for(const id of ['route-select','holder-select'])nodes.get(id).addEventListener('change',()=>observations.push(stats.runs.at(-1).state.disposeCalls));}});await h.preview.activate();h.nodes.get('route-select').fire('change');await h.preview.activate();h.nodes.get('holder-select').fire('change');assert.deepEqual(observations,[1,1]);return {classification:'bounded_no_additional_issue',legacyBubbleObservedDisposeCounts:observations};});
  await check('C10_NONFINITE_SPEED_PAUSES',async()=>{const h=setup();await h.preview.activate();h.panel.querySelector('#pallet-speed').value='NaN';h.preview.setPlaying(true);const fn=[...h.rafs.values()][0];h.rafs.clear();fn(100);assert.equal(h.preview.snapshot().playing,false);assert.equal(h.preview.snapshot().at_s,0);h.preview.stop();return {classification:'bounded_no_additional_issue'};});
  await check('C11_NONCOOPERATIVE_PREPARE_DEADLINE',async()=>{const d=deferred();const h=setup({prepare:()=>d.promise});let settled=false;const pending=h.preview.activate().then(v=>{settled=true;return v;});await drain();[...h.timers.values()].find(x=>x.ms===30000).fn();await drain();assert.equal(settled,false);assert.equal(h.preview.snapshot().phase,'loading');const observed=h.preview.snapshot();d.resolve({});assert.equal(await pending,false);assert.equal(h.preview.snapshot().error,'PALLET_PREPARE_TIMEOUT');return {classification:'conditional_limitation',observedAfterDeadline:observed,settledAfterDeadline:false,explanation:'Abort-only outer deadline needs awaited dependency settlement. This stub does not prove an actual accepted support asset stalls.'};});
  const output={
    passed:results.every(row=>row.outcome==='PASS'),
    task_id:'W05.4.4',
    label:'COMPONENT_ONLY',
    source_kind:'visual_fixture',
    public_bootstrap:false,
    private_source_issuance:false,
    native_physical_admission:false,
    native_530_HU_scene:false,
    rendered_appearance:false,
    operational_admission:false,
    continuous_deadline_certificate:false,
    scope:'Exact current preview TypeScript transpiled in memory. DOM/event ordering, RAF, timers, reader, policy/compiler and scene/native controller are isolated component stubs.',
    input_hashes:{[checkerPath]:sha256(fs.readFileSync(path.join(root,checkerPath))),[sourcePath]:sha256(sourceBytes)},
    compiler:{dependency:'frontend/node_modules/typescript',version:ts.version},
    historical_red_reference:{
      path:'work/v3/pallet-preview-lifecycle-check/w0544-fix/component-results-red.json',
      sha256:'54224049e5d87c2941550894ecd1a301b475d0fd3040ff8c05db23be97b0fee4',
      source_sha256:'b0a27a32e5c5a7f947920121242b83ec82883be500a6a725808c510bea370b53',
      cases:11,passing:8,expected_failing:3,
      failing_cases:['C02_ERROR_PERSISTENCE','C03_FAILED_INITIAL_APPLY_OWNERSHIP','C04_DISPOSE_STOP_REACTIVATE'],
      note:'Immutable executed before-fix COMPONENT_ONLY RED result; provenance reference only. Not regenerated or a claim about any CLI completion.'
    },
    limitations:[
      'DOM is an event-order stub, not a browser.',
      'Catalogue, policy compiler, source reader and scene/native controller are dependency stubs.',
      'No public bootstrap, real private issuance, physical admission, real 530-HU scene, assets or rendered appearance established.',
      'C11 positively demonstrates the abort-only deadline limitation: a noncooperative awaited prepare remains loading after abort until its promise settles. It does not establish an actual accepted support asset stall or a hard wall-clock deadline certificate.'
    ],
    counts:{cases:results.length,passed:results.filter(r=>r.outcome==='PASS').length,failed:results.filter(r=>r.outcome!=='PASS').length,behavior_cases:results.filter(r=>r.classification!=='conditional_limitation').length,conditional_limitations:results.filter(r=>r.classification==='conditional_limitation').length},
    results
  };
  if(!output.passed){console.error(JSON.stringify(output,null,2));process.exitCode=1;return;}
  const bytes=Buffer.from(JSON.stringify(output,null,2)+'\n','utf8');
  if(checkOnly){
    const accepted=fs.readFileSync(path.join(root,evidencePath));
    if(!bytes.equals(accepted))throw Error('LIFECYCLE_EVIDENCE_MISMATCH: recomputed component report differs from accepted bytes');
  }else fs.writeFileSync(path.join(root,evidencePath),bytes);
  console.log(JSON.stringify({passed:true,check_only:checkOnly,label:output.label,counts:output.counts,input_hashes:output.input_hashes,evidence_sha256:sha256(bytes)}));
})().catch(e=>{console.error(e);process.exitCode=1;});
