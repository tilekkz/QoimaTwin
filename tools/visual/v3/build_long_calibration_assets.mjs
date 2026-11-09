/** Portable native geometry generator. No renderer, Blender, network or prototype imports. */
import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir, lstat, realpath, link, unlink} from 'node:fs/promises';
import {createHash, randomUUID} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const SELF=fileURLToPath(import.meta.url);
const DEFAULT_ROOT=path.resolve(path.dirname(SELF),'../../..');
const DATA=path.resolve(path.dirname(SELF),'../../../assets/v3/long-calibration');
const RECIPE_SHA256='f3794963525118c30282c665d5151fbf60a950b6c6b5e09311b0f3a418fae248';
export const sha=b=>createHash('sha256').update(b).digest('hex');
const encode=x=>Buffer.from(JSON.stringify(x,null,2)+'\n');
const equal=(a,b,label)=>assert.deepEqual(a,b,label);
const pin=b=>({bytes:b.length,sha256:sha(b)});
function pinned(b,p,label){assert.equal(b.length,p.bytes,label+' byte count');assert.equal(sha(b),p.sha256,label+' SHA256');}
function integer(n,label){assert(Number.isSafeInteger(n)&&n>=0,label+' must be a nonnegative safe integer');return n;}
export function bounded(offset,length,total,label='range'){
  integer(offset,label+' offset');integer(length,label+' length');integer(total,label+' limit');
  assert(offset<=total&&length<=total-offset,label+' exceeds bounds');return offset+length;
}
export function unpack(b){
  assert(b.length>=28,'short GLB');assert.equal(b.readUInt32LE(0),0x46546c67);assert.equal(b.readUInt32LE(4),2);
  assert.equal(b.readUInt32LE(8),b.length,'GLB declared length');
  const n=b.readUInt32LE(12);assert.equal(n%4,0);assert.equal(b.readUInt32LE(16),0x4e4f534a);
  const jsonEnd=bounded(20,n,b.length,'JSON chunk');bounded(jsonEnd,8,b.length,'BIN header');
  assert.equal(b.readUInt32LE(jsonEnd+4),0x004e4942);
  const length=b.readUInt32LE(jsonEnd),start=jsonEnd+8;assert.equal(length%4,0);
  assert.equal(bounded(start,length,b.length,'BIN chunk'),b.length);
  const text=b.subarray(20,jsonEnd).toString('utf8'),json=JSON.parse(text),bin=b.subarray(start);
  assert.equal(json.buffers.length,1);assert.equal(json.buffers[0].uri,undefined);assert.equal(json.buffers[0].byteLength,bin.length);
  return {text,json,bin,start};
}
export function pack(text,bin){
  let j=Buffer.from(text);j=Buffer.concat([j,Buffer.alloc((4-j.length%4)%4,32)]);
  assert.equal(bin.length%4,0);const h=Buffer.alloc(20),bh=Buffer.alloc(8),length=28+j.length+bin.length;
  assert(length<=0xffffffff,'GLB size overflow');h.writeUInt32LE(0x46546c67);h.writeUInt32LE(2,4);h.writeUInt32LE(length,8);
  h.writeUInt32LE(j.length,12);h.writeUInt32LE(0x4e4f534a,16);bh.writeUInt32LE(bin.length);bh.writeUInt32LE(0x004e4942,4);
  return Buffer.concat([h,j,bh,bin]);
}
function layout(raw,id){
  integer(id,'accessor');const a=raw.json.accessors[id];assert(a&&!a.sparse,'missing/sparse accessor');
  const v=raw.json.bufferViews[a.bufferView];assert(v&&v.buffer===0,'missing/non-native bufferView');
  const dims={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16}[a.type],bytes={5121:1,5123:2,5125:4,5126:4}[a.componentType];
  assert(dims&&bytes,'unsupported layout');integer(a.count,'accessor count');assert(a.count>0);
  const offset=v.byteOffset??0,inner=a.byteOffset??0,stride=v.byteStride??dims*bytes;
  integer(stride,'stride');assert(stride>=dims*bytes&&stride%bytes===0,'bad stride');
  bounded(offset,v.byteLength,raw.bin.length,'bufferView');
  bounded(inner,(a.count-1)*stride+dims*bytes,v.byteLength,'accessor');
  assert((offset+inner)%bytes===0,'unaligned accessor');
  const at=(i,k)=>{integer(i,'vertex');integer(k,'component');assert(i<a.count&&k<dims);const p=offset+inner+i*stride+k*bytes;bounded(p,bytes,offset+v.byteLength,'element');return p;};
  return {a,v,dims,bytes,at,get(i,k){const p=at(i,k);const value=a.componentType===5126?raw.bin.readFloatLE(p):bytes===1?raw.bin[p]:bytes===2?raw.bin.readUInt16LE(p):raw.bin.readUInt32LE(p);assert(Number.isFinite(value),'non-finite attribute');return value;},set(i,k,value){assert.equal(a.componentType,5126);assert(Number.isFinite(value));raw.bin.writeFloatLE(value,at(i,k));}};
}
function values(raw,id){const a=layout(raw,id);return Array.from({length:a.a.count},(_,i)=>Array.from({length:a.dims},(_,k)=>a.get(i,k)));}
function allRanges(raw){
  for(let i=0;i<raw.json.bufferViews.length;i++){const v=raw.json.bufferViews[i];assert.equal(v.buffer,0);bounded(v.byteOffset??0,v.byteLength,raw.bin.length,'bufferView '+i);}
  for(let i=0;i<raw.json.accessors.length;i++)layout(raw,i);
  for(const m of raw.json.meshes)for(const p of m.primitives){const count=raw.json.accessors[p.attributes.POSITION].count;
    if(p.indices!==undefined)for(const [i] of values(raw,p.indices))assert(i<count,'index exceeds vertex count');}
}
function expectedView(raw,p){
  equal(raw.json.accessors[p.accessor],p.expectedAccessor,'expected original accessor');equal(raw.json.bufferViews[p.bufferView],p.expectedBufferView,'expected original bufferView');
  const a=layout(raw,p.accessor),v=a.v;assert.equal(sha(raw.bin.subarray(v.byteOffset??0,(v.byteOffset??0)+v.byteLength)),p.sha256,'expected original view bytes');
}
function viewHash(raw,id){const {v}=layout(raw,id);return sha(raw.bin.subarray(v.byteOffset??0,(v.byteOffset??0)+v.byteLength));}

// The original index graph and vertex splits are preserved. Only the lower cap profile changes.
function correctCaps(raw,recipe,T){
  const v=p=>new T.Vector3(...p),edits=[];
  for(const c of recipe.caps){
    equal(raw.json.nodes[c.nodeIndex],c.expectedNode);equal(raw.json.meshes[c.meshIndex],c.expectedMesh);
    for(const p of [c.position,c.normal,c.indices])expectedView(raw,p);
    const x=c.side==='L'?-.4:.4,p=layout(raw,c.position.accessor),n=layout(raw,c.normal.accessor),ix=layout(raw,c.indices.accessor);
    assert.equal(p.dims,3);assert.equal(n.dims,3);assert.equal(ix.dims,1);assert.equal(ix.a.count%3,0);
    const moved=new Set(),affected=new Set();
    function set(a,id,i,next){for(let k=0;k<3;k++){const offset=a.at(i,k),oldBits=raw.bin.readUInt32LE(offset),old=a.get(i,k);a.set(i,k,next[k]);const newBits=raw.bin.readUInt32LE(offset);if(oldBits!==newBits)edits.push({side:c.side,accessor:id,vertex:i,component:k,binOffset:offset,oldBits,newBits,old,new:a.get(i,k)});}}
    for(let i=0;i<p.a.count;i++){
      const old=[0,1,2].map(k=>p.get(i,k)),r=Math.hypot(old[0]-x,old[2]+.38),next=[...old];
      if(Math.abs(old[1]-.125)<1e-7){next[1]=Math.fround(.1250000298023224);if(r>.0142){const scale=.0142/r;next[0]=Math.fround(x+(old[0]-x)*scale);next[2]=Math.fround(-.38+(old[2]+.38)*scale);}}
      else if(Math.abs(old[1]-.12515)<1e-7)next[1]=Math.fround(.1268000298023224);
      if(next.some((q,k)=>q!==old[k])){moved.add(i);set(p,c.position.accessor,i,next);}
    }
    const sums=Array.from({length:p.a.count},()=>v([0,0,0]));
    for(let i=0;i<ix.a.count;i+=3){const ids=[0,1,2].map(k=>ix.get(i+k,0)),pp=ids.map(j=>v([0,1,2].map(k=>p.get(j,k)))),normal=pp[1].clone().sub(pp[0]).cross(pp[2].clone().sub(pp[0]));
      for(const j of ids)sums[j].add(normal);if(ids.some(j=>moved.has(j)))for(const j of ids)affected.add(j);}
    for(let i=0;i<n.a.count;i++)if(affected.has(i)){const old=[0,1,2].map(k=>n.get(i,k)),next=sums[i].normalize().toArray().map(Math.fround);if(next.some((q,k)=>q!==old[k]))set(n,c.normal.accessor,i,next);}
    assert.equal(viewHash(raw,c.position.accessor),c.replacementPositionViewSHA256,'analytic cap POSITION');assert.equal(viewHash(raw,c.normal.accessor),c.replacementNormalViewSHA256,'analytic cap NORMAL');
  }
  return edits;
}
// Extract the six native annular profile stations; keep every original angular station exactly.
function profileFromOriginal(p,segments){
  const stations=[];for(const q of p){const r=Math.hypot(q[1],q[2]);if(!stations.some(s=>Math.abs(s.x-q[0])<1e-9&&Math.abs(s.r-r)<1e-7))stations.push({x:q[0],r,points:[]});}assert.equal(stations.length,6);
  for(const q of p){const st=stations.find(s=>s.x===q[0]&&Math.abs(s.r-Math.hypot(q[1],q[2]))<1e-7);if(!st.points.some(t=>t.join(',')===q.join(',')))st.points.push(q);}
  stations.sort((a,b)=>a.x-b.x||a.r-b.r);const ordered=[stations[0],stations[1],stations[2],stations[3],stations[5],stations[4]];
  for(const st of ordered){assert.equal(st.points.length,segments);st.points.sort((a,b)=>((Math.atan2(a[2],a[1])+2*Math.PI)%(2*Math.PI))-((Math.atan2(b[2],b[1])+2*Math.PI)%(2*Math.PI)));st.r=st.points[0][1];st.maxR=Math.max(...st.points.map(p=>Math.hypot(p[1],p[2])));}
  return ordered;
}
function makeTyre(profile,N,T){
  integer(N,'segments');assert(N<=240&&N%24===0);const v=p=>new T.Vector3(...p);
  const rings=profile.map(st=>Array.from({length:N},(_,j)=>{
    if(j%(N/24)===0)return [...st.points[j/(N/24)]];
    const theta=2*Math.PI*j/N;let y=Math.fround(st.r*Math.cos(theta)),z=Math.fround(st.r*Math.sin(theta));
    for(let k=0;Math.hypot(y,z)>st.maxR&&k<12;k++){const scale=(st.maxR-2e-8)/Math.hypot(y,z);y=Math.fround(y*scale);z=Math.fround(z*scale);}assert(Math.hypot(y,z)<=st.maxR);return [st.x,y,z];
  }));
  const positions=[],normals=[],indices=[];
  for(let k=0;k<6;k++)for(let j=0;j<N;j++){
    const nj=(j+1)%N,nk=(k+1)%6,q=[rings[k][j],rings[k][nj],rings[nk][nj],rings[nk][j]],vv=q.map(v);
    const normal=vv[1].clone().sub(vv[0]).cross(vv[2].clone().sub(vv[0])).add(vv[2].clone().sub(vv[0]).cross(vv[3].clone().sub(vv[0]))).normalize().toArray().map(Math.fround),base=positions.length;
    for(let i=0;i<4;i++){positions.push(q[i]);normals.push(normal);}indices.push(base,base+1,base+2,base,base+2,base+3);
  }
  return {positions,normals,indices};
}
function binaryValues(values,type){const b=Buffer.alloc(values.length*(type==='index'?2:12));
  values.forEach((p,i)=>{if(type==='index'){assert(Number.isSafeInteger(p)&&p>=0&&p<=65535);b.writeUInt16LE(p,i*2);}else p.forEach((x,k)=>{assert(Number.isFinite(x));b.writeFloatLE(x,i*12+k*4);});});return b;
}
export function applyJSONEdits(text,edits){
  let end=0;for(const e of [...edits].sort((a,b)=>a.start-b.start)){
    bounded(e.start,e.end-e.start,text.length,'JSON edit');assert(e.start>=end,'overlapping JSON edits');assert.equal(text.slice(e.start,e.end),e.old,'expected original JSON bytes');end=e.end;
  }
  for(const e of [...edits].sort((a,b)=>b.start-a.start))text=text.slice(0,e.start)+e.new+text.slice(e.end);return text;
}
function buildLoaded(source,recipe,edits,T){
  const original=unpack(source);allRanges(original);pinned(Buffer.from(original.text),recipe.sourceJSON,'source JSON');pinned(original.bin,recipe.sourceBIN,'source BIN');
  const raw={...original,bin:Buffer.from(original.bin)},capEdits=correctCaps(raw,recipe,T);
  const lock=pack(raw.text,raw.bin);pinned(lock,recipe.correctedLock,'corrected lock epoch');pinned(raw.bin,recipe.correctedLockBIN,'corrected lock BIN');
  const restored=Buffer.from(raw.bin);for(const e of capEdits){assert.equal(restored.readUInt32LE(e.binOffset),e.newBits);restored.writeUInt32LE(e.oldBits,e.binOffset);}assert(restored.equals(original.bin),'cap edit reversal');assert(pack(raw.text,restored).equals(source),'complete source reversal');
  const appended=[],wheelProfiles=[];let offset=raw.bin.length;
  for(const w of recipe.wheels){
    equal(raw.json.nodes[w.nodeIndex],w.expectedNode);equal(raw.json.meshes[w.meshIndex],w.expectedMesh);
    for(const p of [w.position,w.normal,w.indices])expectedView(raw,p);
    const old=values(raw,w.position.accessor),profile=profileFromOriginal(old,24),tyre=makeTyre(profile,w.segments,T);
    const retained=new Set(tyre.positions.map(p=>p.join(',')));assert(old.every(p=>retained.has(p.join(','))),'original tyre position missing');
    const chunks=[binaryValues(tyre.positions,'vec3'),binaryValues(tyre.normals,'vec3'),binaryValues(tyre.indices,'index')];
    for(let k=0;k<chunks.length;k++){
      const e=w.appended[k],view=e.expectedBufferView;assert.equal(view.buffer,0);assert.equal(view.byteOffset,offset,'append boundary');assert.equal(view.byteLength,chunks[k].length);assert.equal(chunks[k].length%4,0);assert.equal(sha(chunks[k]),e.sha256,'analytic tyre view bytes');appended.push(chunks[k]);offset+=chunks[k].length;
    }
    wheelProfiles.push({id:w.id,segments:w.segments,stations:profile.map(s=>({x:s.x,radius:s.r,maximumNativeRadius:s.maxR})),allOriginalPositionsRetained:true});
  }
  const extra=Buffer.concat(appended);pinned(extra,recipe.appendedTyreBIN,'analytic appended BIN');
  const text=applyJSONEdits(raw.text,edits),bin=Buffer.concat([raw.bin,extra]),result=pack(text,bin),decoded=unpack(result);allRanges(decoded);
  assert(decoded.bin.subarray(0,raw.bin.length).equals(raw.bin),'corrected original BIN prefix changed');
  // Only four tyre nodes/meshes and append-only container arrays may differ.
  const allowedNodes=new Set(recipe.wheels.map(w=>w.nodeIndex)),allowedMeshes=new Set(recipe.wheels.map(w=>w.meshIndex));
  equal(decoded.json.accessors.slice(0,raw.json.accessors.length),raw.json.accessors);equal(decoded.json.bufferViews.slice(0,raw.json.bufferViews.length),raw.json.bufferViews);
  for(const key of Object.keys(raw.json))if(!['nodes','meshes','accessors','bufferViews','buffers'].includes(key))equal(decoded.json[key],raw.json[key]);
  raw.json.nodes.forEach((n,i)=>{if(!allowedNodes.has(i))equal(decoded.json.nodes[i],n);});raw.json.meshes.forEach((m,i)=>{if(!allowedMeshes.has(i))equal(decoded.json.meshes[i],m);});
  for(const w of recipe.wheels){const old=raw.json.nodes[w.nodeIndex],next=structuredClone(decoded.json.nodes[w.nodeIndex]);assert.equal(next.extras.radial_segments,w.segments);next.extras.radial_segments=24;equal(next,old);assert.equal(decoded.json.meshes[w.meshIndex].primitives[0].material,w.expectedMesh.primitives[0].material);}
  return {bytes:result,capEdits,wheelProfiles};
}
function buildApron(template,recipe,environment){
  const doc=JSON.parse(template),env=unpack(environment);allRanges(env);
  equal(doc.materials[0],env.json.materials.find(m=>m.name==='V3_Shell_floor'),'exact source concrete material');
  const chunks=[];
  for(const piece of recipe.apron.pieces){
    const [x0,y0,z0]=piece.min,[x1,y1,z1]=piece.max;assert.equal(y1,0);
    assert([x0,y0,z0,x1,y1,z1].every(x=>Number.isFinite(x)&&Math.fround(x)===x));assert(x0<x1&&y0<y1&&z0<z1);
    const faces=[
      [[-1,0,0],[[x0,y0,z0],[x0,y0,z1],[x0,y1,z1],[x0,y1,z0]]],
      [[1,0,0],[[x1,y0,z1],[x1,y0,z0],[x1,y1,z0],[x1,y1,z1]]],
      [[0,-1,0],[[x0,y0,z1],[x0,y0,z0],[x1,y0,z0],[x1,y0,z1]]],
      [[0,1,0],[[x0,y1,z0],[x0,y1,z1],[x1,y1,z1],[x1,y1,z0]]],
      [[0,0,-1],[[x1,y0,z0],[x0,y0,z0],[x0,y1,z0],[x1,y1,z0]]],
      [[0,0,1],[[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]]]
    ],positions=[],normals=[],indices=[];
    for(const [normal,points] of faces){const base=positions.length;positions.push(...points);normals.push(normal,normal,normal,normal);indices.push(base,base+1,base+2,base,base+2,base+3);}
    chunks.push(binaryValues(positions,'vec3'),binaryValues(normals,'vec3'),binaryValues(indices,'index'));
  }
  const bin=Buffer.concat(chunks);let offset=0;
  for(const e of recipe.apron.expectedViews){const v=doc.bufferViews[e.index];equal(v,e.expected);assert.equal(v.byteOffset,offset);bounded(offset,v.byteLength,bin.length,'apron view');assert.equal(sha(bin.subarray(offset,offset+v.byteLength)),e.sha256);offset+=v.byteLength;}assert.equal(offset,bin.length);
  const result=pack(template,bin);allRanges(unpack(result));return result;
}
export async function buildAll(recipe,files,source,environment,T,validator,generatorSHA256){
  pinned(source,recipe.sources.source,'source');pinned(environment,recipe.sources.environment,'environment');
  for(const [name,p] of Object.entries(recipe.files))pinned(files[name],p,name);
  const loaded=buildLoaded(source,recipe,JSON.parse(files['tyre-json-edits.json']),T),apron=buildApron(files['apron-document.json'].toString(),recipe,environment);
  const outputs=[loaded.bytes,apron],validation=[];
  for(let i=0;i<outputs.length;i++){
    const expected=recipe.outputs[i];pinned(outputs[i],expected,'generated '+expected.name);
    const report=await validator.validateBytes(new Uint8Array(outputs[i]),{uri:expected.name,maxIssues:1000});
    assert.equal(report.issues.numErrors,0,'Khronos errors');assert.equal(report.issues.numWarnings,0,'Khronos warnings');
    equal(report.issues.messages.filter(m=>m.severity===2).map(m=>m.pointer).sort(),expected.expectedUnusedAccessors.map(x=>'/accessors/'+x).sort(),'expected retained-accessor infos');
    assert(report.issues.messages.every(m=>m.severity===2&&m.code==='UNUSED_OBJECT'),'unexpected validator issue');
    validation.push({name:expected.name,issues:report.issues});
  }
  const report={schema:'qoima.long-calibration-build.v1',status:'unaccepted_generated_asset',generatorSHA256,recipeSHA256:sha(encode(recipe)),sources:recipe.sources,data:recipe.files,outputs:recipe.outputs,validator:{version:validator.version(),validation},invariants:recipe.invariants,preservation:{originalJSONOutsideExplicitEditsPreserved:true,allOldAccessorsAndBufferViewsPreserved:true,allMaterialsAndJointsPreserved:true,correctedOriginalBINPrefixSHA256:recipe.correctedLockBIN.sha256,capChangesReverseToExactSource:true,tyreAppendBytes:recipe.appendedTyreBIN.bytes,allOriginalTyrePositionsRetained:true},wheelProfiles:loaded.wheelProfiles,capFloatEdits:loaded.capEdits,admission:{sourceCalibrationAPI:false,loaderRegistration:false,workflow:false,operational:false,W12:false}};
  return [...outputs.map((bytes,i)=>({name:recipe.outputs[i].name,bytes})),{name:'long-calibration-build.json',bytes:encode(report)}];
}
async function statOrNull(p){try{return await lstat(p);}catch(e){if(e.code==='ENOENT')return null;throw e;}}
async function safeDirectory(dir){let p=path.resolve(dir);for(;;){const s=await statOrNull(p);if(s)assert(s.isDirectory()&&!s.isSymbolicLink(),'output ancestors must be real directories');const next=path.dirname(p);if(next===p)break;p=next;}}
async function preflight(out,products,check){
  await safeDirectory(out);const pending=[];
  for(const p of products){assert.equal(path.basename(p.name),p.name);const file=path.join(out,p.name),s=await statOrNull(file);
    if(s){assert(s.isFile()&&!s.isSymbolicLink(),'target must be a regular file');assert((await readFile(file)).equals(p.bytes),'changed existing target refuses overwrite: '+p.name);}
    else {assert(!check,'check-only missing target: '+p.name);pending.push({...p,file});}}
  return pending;
}
async function publish(out,pending){
  if(!pending.length)return;await mkdir(out,{recursive:true});await safeDirectory(out);
  const staged=[],published=[];
  try{
    for(const p of pending){const temp=path.join(out,'.long-calibration-'+randomUUID()+'.tmp');await writeFile(temp,p.bytes,{flag:'wx'});staged.push({temp,file:p.file});}
    // Hard-link creation is exclusive: a competing writer can never be overwritten.
    for(const p of staged){await link(p.temp,p.file);published.push(p);}
  }catch(e){for(const p of published){const a=await lstat(p.temp),b=await statOrNull(p.file);if(b&&a.ino===b.ino&&a.dev===b.dev)await unlink(p.file);}throw e;}
  finally{for(const p of staged)await unlink(p.temp);}
}
export async function main(argv=process.argv.slice(2)){
  const opts={};for(let i=0;i<argv.length;i++){const a=argv[i];if(a==='--check-only')opts.check=true;else if(a==='--source-root'||a==='--out'){assert(argv[i+1]&&!argv[i+1].startsWith('--'),'missing '+a);assert(opts[a]===undefined,'duplicate '+a);opts[a]=argv[++i];}else if(a==='--help'){console.log('node tools/visual/v3/build_long_calibration_assets.mjs [--source-root REPO] --out NEW_DIRECTORY [--check-only]');return;}else throw Error('unknown option '+a);}
  assert(opts['--out'],'--out is required; choose an explicit new destination');
  const root=path.resolve(opts['--source-root']??DEFAULT_ROOT),out=path.resolve(opts['--out']);
  const recipeBytes=await readFile(path.join(DATA,'recipe.json'));assert.equal(sha(recipeBytes),RECIPE_SHA256,'recipe integrity SHA256');const recipe=JSON.parse(recipeBytes);
  assert.equal(recipe.schema,'qoima.long-calibration-assets.v1');const inputs=[];
  const readPinned=async(p,pin,label)=>{const b=await readFile(p);pinned(b,pin,label);inputs.push({path:p,pin});return b;};
  // Both canonical source pins are checked before geometry or destination creation.
  const source=await readPinned(path.join(root,recipe.sources.source.path),recipe.sources.source,'source');
  const environment=await readPinned(path.join(root,recipe.sources.environment.path),recipe.sources.environment,'environment');
  const files={};for(const [name,p] of Object.entries(recipe.files)){assert.equal(path.basename(name),name);files[name]=await readPinned(path.join(DATA,name),p,name);}
  const T=await import(pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')));
  const validator=await import(pathToFileURL(path.join(root,'frontend/node_modules/gltf-validator/module.mjs')));
  const products=await buildAll(recipe,files,source,environment,T,validator,sha(await readFile(SELF)));
  const pending=await preflight(out,products,!!opts.check);
  const sourcePaths=await Promise.all(inputs.map(x=>realpath(x.path)));
  for(const product of products)assert(!sourcePaths.some(p=>p.toLowerCase()===path.join(out,product.name).toLowerCase()),'output aliases input');
  for(const input of inputs)pinned(await readFile(input.path),input.pin,'input before publication');
  assert.equal(sha(await readFile(path.join(DATA,'recipe.json'))),RECIPE_SHA256,'recipe changed during build');
  if(!opts.check)await publish(out,pending);
  console.log(JSON.stringify({checkOnly:!!opts.check,written:opts.check?0:pending.length,outputs:products.map(p=>({name:p.name,...pin(p.bytes)})),validator:'0 errors, 0 warnings; model 9 expected UNUSED_OBJECT infos, apron 0 infos'}));
}
if(process.argv[1]&&path.resolve(process.argv[1])===SELF)main().catch(e=>{console.error('LONG_ASSET_BUILD_REJECTED: '+e.message);process.exitCode=1;});
