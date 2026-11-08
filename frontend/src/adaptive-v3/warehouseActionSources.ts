import manifest from './warehouseActionSourceManifest.json';

export type ActionSourceReason = 'UNKNOWN_SOURCE'|'SOURCE_FETCH_FAILED'|'SOURCE_INTEGRITY'|'SOURCE_TIMEOUT'|'SOURCE_ABORTED'|'READER_DISPOSED';
export class ActionSourceError extends Error {
 constructor(readonly reason:ActionSourceReason){super(reason);this.name='ActionSourceError';}
}
type Entry={source_path:string;sha256:string;bytes:number;url:string;kind:string};
const entries=new Map<string,Readonly<Entry>>();
// Snapshot the bundled allowlist; callers never receive its mutable imported object.
for(const entry of structuredClone(manifest.entries)){
 if(entries.has(entry.source_path)||!/^[a-f0-9]{64}$/.test(entry.sha256)||!Number.isSafeInteger(entry.bytes)||entry.bytes<=0||entry.bytes>16*1024*1024||entry.url.startsWith('/')||entry.url.includes('..')||!entry.url.startsWith('data/')&&!entry.url.startsWith('models/'))throw Error('INVALID_BUNDLED_SOURCE_MANIFEST');
 entries.set(entry.source_path,Object.freeze(entry));
}
export const warehouseActionSourcePaths=Object.freeze([...entries.keys()]);
const digest=async(bytes:Uint8Array)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes as BufferSource))].map(n=>n.toString(16).padStart(2,'0')).join('');

/** No import-time fetch, filesystem URL, timer or scene effect. One disposable reader per load lifetime. */
export function createWarehouseActionSourceReader(options:{fetcher?:typeof fetch;signal?:AbortSignal;timeout_ms?:number}={}){
 const timeout=options.timeout_ms??15000;
 if(!Number.isSafeInteger(timeout)||timeout<=0||timeout>30000)throw new RangeError('Invalid source timeout');
 const fetcher=options.fetcher??globalThis.fetch.bind(globalThis),signal=options.signal;
 const cached=new Map<string,Uint8Array>(),pending=new Map<string,Promise<Uint8Array>>(),controllers=new Set<AbortController>();
 let disposed=false;
 function failure():ActionSourceReason{return disposed?'READER_DISPOSED':signal?.aborted?'SOURCE_ABORTED':'SOURCE_FETCH_FAILED';}
 function alive(){if(disposed)throw new ActionSourceError('READER_DISPOSED');if(signal?.aborted)throw new ActionSourceError('SOURCE_ABORTED');}
 function abortAll(){for(const controller of controllers)controller.abort();cached.clear();}
 function cancelBody(response:Response|undefined){if(response?.body&&!response.body.locked)void response.body.cancel().catch(()=>{});}
 signal?.addEventListener('abort',abortAll,{once:true});

 async function exactBody(response:Response,entry:Readonly<Entry>,controller:AbortController){
  const declared=response.headers.get('content-length');
  if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)!==entry.bytes))throw new ActionSourceError('SOURCE_INTEGRITY');
  if(!response.body){const empty=new Uint8Array(await response.arrayBuffer());if(empty.byteLength!==entry.bytes)throw new ActionSourceError('SOURCE_INTEGRITY');return empty;}
  const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
  const cancel=()=>{void reader.cancel().catch(()=>{});};controller.signal.addEventListener('abort',cancel,{once:true});
  try{
    if(controller.signal.aborted){cancel();throw new ActionSourceError('SOURCE_ABORTED');}
    while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>entry.bytes){cancel();throw new ActionSourceError('SOURCE_INTEGRITY');}chunks.push(part.value);}
  }finally{controller.signal.removeEventListener('abort',cancel);try{reader.releaseLock();}catch{/* Cleanup must not hide the original refusal. */}}
  if(size!==entry.bytes)throw new ActionSourceError('SOURCE_INTEGRITY');
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes;
 }

 async function request(entry:Readonly<Entry>){
  const controller=new AbortController();controllers.add(controller);let timedOut=false,response:Response|undefined;
  const canceled=new Promise<never>((_,reject)=>controller.signal.addEventListener('abort',()=>reject(new ActionSourceError(timedOut?'SOURCE_TIMEOUT':failure())),{once:true}));
  const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeout);
  try{
   const download=(async()=>{
    response=await fetcher(entry.url,{signal:controller.signal,credentials:'same-origin',cache:'no-cache'});
    if(controller.signal.aborted){cancelBody(response);throw new ActionSourceError(timedOut?'SOURCE_TIMEOUT':failure());}
    if(!response.ok)throw new ActionSourceError('SOURCE_FETCH_FAILED');
    const bytes=await exactBody(response,entry,controller);
    if(await digest(bytes)!==entry.sha256)throw new ActionSourceError('SOURCE_INTEGRITY');return bytes;
   })();
   const bytes=await Promise.race([download,canceled]);alive();if(controller.signal.aborted)throw new ActionSourceError(timedOut?'SOURCE_TIMEOUT':failure());
   cached.set(entry.source_path,bytes);return bytes;
  }catch(error){const cause=error instanceof ActionSourceError?error:new ActionSourceError(timedOut?'SOURCE_TIMEOUT':failure());controller.abort();cancelBody(response);throw cause;}
  finally{clearTimeout(timer);controllers.delete(controller);}
 }

 async function readSource(path:string):Promise<Uint8Array>{
  alive();const entry=entries.get(path);if(!entry)throw new ActionSourceError('UNKNOWN_SOURCE');
  const ready=cached.get(path);if(ready)return new Uint8Array(ready);
  let promise=pending.get(path);
  if(!promise){promise=request(entry);pending.set(path,promise);void promise.finally(()=>{if(pending.get(path)===promise)pending.delete(path);}).catch(()=>{});}
  const bytes=await promise;alive();return new Uint8Array(bytes);
 }
 function dispose(){if(disposed)return;disposed=true;signal?.removeEventListener('abort',abortAll);abortAll();pending.clear();}
 function snapshot(){return Object.freeze({disposed,aborted:signal?.aborted??false,cached_sources:cached.size,inflight_sources:pending.size,source_kind:'visual_fixture' as const,engine_operation:false as const,completed_jobs:0 as const});}
 return Object.freeze({readSource,dispose,snapshot});
}
