import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import {createServer} from 'node:http';

const root=path.resolve('..'),cache=path.join(root,'work/v3/action-source-check');
const output=path.join(root,'docs/adaptive-v3/evidence/W05.5.1-checks.json');
const sha=b=>createHash('sha256').update(b).digest('hex'),input_hashes={},positives=[],negatives=[];
async function source(p){const bytes=await readFile(path.join(root,p));input_hashes[p]=sha(bytes);return bytes;}
await mkdir(cache,{recursive:true});
const manifest=JSON.parse((await source('frontend/src/adaptive-v3/warehouseActionSourceManifest.json')).toString());
const support=JSON.parse((await source('frontend/src/adaptive-v3/warehouseSupportBindings.json')).toString());
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter','warehouseCargoHolders','warehouseActionTimeline','warehouseActionSources']){
 let code=ts.transpileModule((await source('frontend/src/adaptive-v3/'+name+'.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '(\.\/\w+)'/g,"from '$1.mjs'");
 code=code.replace("import supportBindings from './warehouseSupportBindings.json';",'const supportBindings='+JSON.stringify(support)+';');
 code=code.replace("import manifest from './warehouseActionSourceManifest.json';",'const manifest='+JSON.stringify(manifest)+';');
 await writeFile(path.join(cache,name+'.mjs'),code);
}
for(const p of ['frontend/tools/check-warehouse-action-sources-v3.mjs','docs/adaptive-v3/specs/W05.5.1.md','tools/visual/v3/build_action_browser_sources.py'])await source(p);
const {createWarehouseActionSourceReader,ActionSourceError,warehouseActionSourcePaths}=await import(pathToFileURL(path.join(cache,'warehouseActionSources.mjs')));
const {adaptWarehouseV3}=await import(pathToFileURL(path.join(cache,'warehouseAdapter.mjs')));
const {compileCargoHolders}=await import(pathToFileURL(path.join(cache,'warehouseCargoHolders.mjs')));
const {registerWarehouseActionCatalogue}=await import(pathToFileURL(path.join(cache,'warehouseActionTimeline.mjs')));
const byUrl=new Map(manifest.entries.map(e=>[e.url,e])),bySource=new Map(manifest.entries.map(e=>[e.source_path,e])),payload=new Map();
for(const row of manifest.entries){
 const original=await source(row.source_path),deployed=await source('frontend/public/'+row.url);
 assert.equal(sha(original),row.sha256);assert.equal(original.length,row.bytes);assert.deepEqual(deployed,original);
 assert(!row.url.includes('..')&&!row.url.includes('@fs')&&!row.url.startsWith('/'));payload.set(row.url,deployed);
}
assert.equal(manifest.entries.length,30);assert.equal(new Set(warehouseActionSourcePaths).size,30);
positives.push('all30_static_URLs_serve_exact_canonical_bytes_without_dev_filesystem');
let requests=[];
const actualFetch=async(url,options)=>{assert(byUrl.has(url));requests.push({url,signal:options.signal});return new Response(payload.get(url),{headers:{'content-length':String(payload.get(url).length)}});};
const reader=createWarehouseActionSourceReader({fetcher:actualFetch});
assert.equal(requests.length,0);positives.push('no_import_or_factory_autofetch');
const texts={};for(const [key,p] of Object.entries({fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'}))texts[key]=new TextDecoder().decode(await reader.readSource(p));
const bundle=await adaptWarehouseV3(texts),cartPath='frontend/public/models/v3/picking-cart-tote-fixture.glb';
const holders=compileCargoHolders(bundle,[{destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'},positions:{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},max_handling_units:1,max_payload_kg:12,support_tare_kg:3,max_total_gross_kg:15,source_refs:{[cartPath]:bySource.get(cartPath).sha256}}]);
const catalogue=await registerWarehouseActionCatalogue(bundle,reader.readSource,holders);
assert.deepEqual(catalogue.counts,{actors:24,vehicles:2,posts:6,carts:1,handling_units:530});assert.equal(catalogue.clips.length,16);
assert.equal(requests.length,30);assert.equal(reader.snapshot().cached_sources,30);positives.push('actual_action_factory_registers_all16_clips_optional_cart_with_only30_deployed_fetches');
const production=new Map();
for(const row of manifest.entries){const bytes=await readFile(path.join(root,'frontend/dist',row.url));assert.equal(sha(bytes),row.sha256,'Production build source drift: '+row.url);production.set('/'+row.url,bytes);}
let httpRequests=0;
const server=createServer((request,response)=>{const bytes=production.get(request.url);if(!bytes){response.writeHead(404).end();return;}httpRequests++;response.writeHead(200,{'content-type':'application/octet-stream','content-length':bytes.length});response.end(bytes);});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
try{
 const address=server.address(),base='http://127.0.0.1:'+address.port+'/';
 const httpReader=createWarehouseActionSourceReader({fetcher:(url,options)=>fetch(new URL(url,base),options)});
 try{const actualCatalogue=await registerWarehouseActionCatalogue(bundle,httpReader.readSource,holders);assert.deepEqual(actualCatalogue.counts,catalogue.counts);assert.equal(actualCatalogue.clips.length,16);assert.equal(httpRequests,30);assert.equal(httpReader.snapshot().cached_sources,30);}
 finally{httpReader.dispose();}
}finally{await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}
positives.push('actual_HTTP_registration_from30_normal_production_static_URLs_with_native_fetch_streaming');
const first=warehouseActionSourcePaths[0],firstRow=bySource.get(first),expected=payload.get(firstRow.url);
const bytes=await reader.readSource(first);bytes[0]^=255;assert.deepEqual(await reader.readSource(first),new Uint8Array(expected));assert.equal(requests.length,30);
positives.push('cached_bytes_defensively_copied_and_never_refetched');
reader.dispose();reader.dispose();assert.equal(reader.snapshot().cached_sources,0);assert.equal(reader.snapshot().disposed,true);
positives.push('idempotent_disposal_releases_cache');
async function rejects(label,promise,reason){await assert.rejects(promise,error=>error instanceof ActionSourceError&&error.reason===reason,label);negatives.push({case_id:label,reason});}
await rejects('disposed_reader',reader.readSource(first),'READER_DISPOSED');
for(const p of ['../contracts/actors.example.json','C:/Users/private/auth.json','frontend/public/../secret','http://example.invalid','contracts/not-declared.json']){
 const r=createWarehouseActionSourceReader({fetcher:()=>{throw Error('Unknown sources must not fetch');}});await rejects('unknown_source_'+p,r.readSource(p),'UNKNOWN_SOURCE');r.dispose();
}
requests=[];const dedup=createWarehouseActionSourceReader({fetcher:async(...args)=>{await new Promise(resolve=>setTimeout(resolve,2));return actualFetch(...args);}});
const copies=await Promise.all([dedup.readSource(first),dedup.readSource(first),dedup.readSource(first)]);assert.equal(requests.length,1);assert.notEqual(copies[0],copies[1]);copies[0][0]^=255;assert.deepEqual(copies[1],new Uint8Array(expected));dedup.dispose();
positives.push('three_inflight_reads_deduplicate_without_shared_return_buffers');
for(const [label,response,reason] of [
 ['HTTP404',()=>new Response('missing',{status:404}),'SOURCE_FETCH_FAILED'],
 ['wrong_digest_same_length',()=>new Response(new Uint8Array(firstRow.bytes)),'SOURCE_INTEGRITY'],
 ['short_body',()=>new Response(new Uint8Array(firstRow.bytes-1)),'SOURCE_INTEGRITY'],
 ['oversize_body',()=>new Response(new Uint8Array(firstRow.bytes+1)),'SOURCE_INTEGRITY'],
 ['oversize_body_rejecting_cancel',()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(firstRow.bytes+1));},cancel(){return Promise.reject(Error('synthetic rejecting cleanup'));}})),'SOURCE_INTEGRITY'],
 ['oversize_body_never_finishing_cancel',()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(firstRow.bytes+1));},cancel(){return new Promise(()=>{});}})),'SOURCE_INTEGRITY'],
 ['false_content_length',()=>new Response(expected,{headers:{'content-length':'1'}}),'SOURCE_INTEGRITY'],
 ['network_failure',()=>{throw Error('network');},'SOURCE_FETCH_FAILED'],
]){
 let attempt=0,capturedSignal;const r=createWarehouseActionSourceReader({fetcher:async(url,options)=>{capturedSignal=options.signal;return ++attempt===1?response():actualFetch(url,options);}});
 await rejects(label,r.readSource(first),reason);assert.equal(r.snapshot().cached_sources,0);assert(capturedSignal.aborted,'Failed request must be canceled');
 assert.deepEqual(await r.readSource(first),new Uint8Array(expected));assert.equal(attempt,2);r.dispose();positives.push(label+'_can_retry_without_failed_cache');
}
let timeoutSignal;const timed=createWarehouseActionSourceReader({timeout_ms:10,fetcher:async(_url,options)=>{timeoutSignal=options.signal;return new Promise(()=>{});}});
await rejects('deadline_even_when_fetch_ignores_abort',timed.readSource(first),'SOURCE_TIMEOUT');assert(timeoutSignal.aborted);timed.dispose();
let resolveLate;const lifetime=new AbortController();const aborted=createWarehouseActionSourceReader({signal:lifetime.signal,fetcher:async()=>new Promise(resolve=>{resolveLate=resolve;})});
const waiting=aborted.readSource(first);lifetime.abort();await rejects('external_abort_ignoring_fetch',waiting,'SOURCE_ABORTED');resolveLate(new Response(expected));await new Promise(resolve=>setTimeout(resolve,0));assert.equal(aborted.snapshot().cached_sources,0);aborted.dispose();
const pre=new AbortController();pre.abort();const preReader=createWarehouseActionSourceReader({signal:pre.signal,fetcher:()=>{throw Error('Preabort must not fetch');}});await rejects('already_aborted',preReader.readSource(first),'SOURCE_ABORTED');preReader.dispose();
for(const ending of ['dispose','timeout']){
 let resolveFetch,cancelCalls=0;const stream=new ReadableStream({pull(){return new Promise(()=>{});},cancel(){cancelCalls++;}});
 const late=createWarehouseActionSourceReader({timeout_ms:10,fetcher:async()=>new Promise(resolve=>{resolveFetch=resolve;})});
 const pending=late.readSource(first);if(ending==='dispose')late.dispose();
 await rejects('late_hanging_stream_after_'+ending,pending,ending==='dispose'?'READER_DISPOSED':'SOURCE_TIMEOUT');
 resolveFetch(new Response(stream));await new Promise(resolve=>setTimeout(resolve,0));assert.equal(cancelCalls,1,'Late body must actually be canceled');assert.equal(stream.locked,false,'No reader may remain attached');assert.equal(late.snapshot().cached_sources,0);late.dispose();
}
let resolveDisposed;const disposed=createWarehouseActionSourceReader({fetcher:async()=>new Promise(resolve=>{resolveDisposed=resolve;})});const disposedRead=disposed.readSource(first);disposed.dispose();await rejects('dispose_inflight_ignoring_fetch',disposedRead,'READER_DISPOSED');resolveDisposed(new Response(expected));await new Promise(resolve=>setTimeout(resolve,0));assert.equal(disposed.snapshot().cached_sources,0);
for(const value of [0,-1,NaN,Infinity,true,1.5,30001]){assert.throws(()=>createWarehouseActionSourceReader({timeout_ms:value}),RangeError);negatives.push({case_id:'invalid_timeout_'+String(value),reason:'RangeError'});}
const result={task_id:'W05.5.1',passed:true,source_kind:'visual_fixture',engine_operation:false,physical_join:false,completed_jobs:0,entries:30,proof_copies:10,production_HTTP_sources:30,total_source_bytes:manifest.total_source_bytes,proof_copy_bytes:manifest.proof_copy_bytes,positive_cases:positives,negative_cases:negatives,input_hashes,scope:'Production-relative accepted byte sources and disposable fetch reader only. Actual UI/renderer workflows and engine execution remain separate.'};
const blob=JSON.stringify(result,null,2)+'\n';
if(process.argv.includes('--check-only'))assert.equal(await readFile(output,'utf8'),blob,'Stale action-source evidence; no evidence files written');
else{await writeFile(output+'.tmp',blob);await rename(output+'.tmp',output);}
console.log(JSON.stringify({passed:true,check_only:process.argv.includes('--check-only'),entries:30,positive_cases:positives.length,negative_cases:negatives.length,actual_registered_clips:16,engine_operation:false,physical_join:false}));
