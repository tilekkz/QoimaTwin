import * as THREE from 'three';
import {canonical,nodes,requireThat} from './native';
import {webHash} from './hash';

/** JSON-valued native metadata only; no accessors, cycles or custom prototypes. */
export function same(a:unknown,b:unknown):boolean {
  if(Object.is(a,b))return true;
  if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
  const aa=a as Record<string,unknown>,bb=b as Record<string,unknown>,keys=Object.keys(aa);
  return keys.length===Object.keys(bb).length&&keys.every(k=>Object.hasOwn(bb,k)&&same(aa[k],bb[k]));
}
const all=(roots:readonly THREE.Object3D[])=>[...new Set(roots.flatMap(nodes))];
/** Validation only: valid binary v1 descriptor preimages stay byte-identical. */
export function validateDrawRanges(roots:readonly THREE.Object3D[]):void {
  for(const n of all(roots))if((n as THREE.Mesh).isMesh)validateDrawRange((n as THREE.Mesh).geometry);
}
function validateDrawRange(g:THREE.BufferGeometry):void {
  const {start,count}=g.drawRange;
  requireThat(typeof start==='number'&&Number.isInteger(start)&&start>=0&&typeof count==='number'&&((Number.isInteger(count)&&count>=0)||count===Infinity),'Invalid native numeric drawRange');
}
/** Exact node identities, parent references and ordered topology across await. */
export function createNodeReferenceGuard(roots:readonly THREE.Object3D[]):()=>void {
  validateDrawRanges(roots);
  const refs=all(roots),rows=refs.map(n=>({n,parent:n.parent,children:[...n.children]}));
  return ()=>{validateDrawRanges(roots);const current=all(roots);requireThat(current.length===refs.length&&current.every((n,i)=>n===refs[i]),'Native node identity changed during async verification');for(const r of rows)requireThat(r.n.parent===r.parent&&r.n.children.length===r.children.length&&r.n.children.every((n,i)=>n===r.children[i]),'Native parent/topology changed during async verification');};
}
type Attr=THREE.BufferAttribute;
function attribute(a:THREE.BufferAttribute|THREE.InterleavedBufferAttribute):Attr {
  requireThat(!(a as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute,'Interleaved attributes unsupported');
  requireThat(a.array.buffer instanceof ArrayBuffer,'Shared geometry buffers unsupported');return a as Attr;
}
function byteView(a:Attr):Uint8Array{return new Uint8Array(a.array.buffer,a.array.byteOffset,a.array.byteLength);}
function equalBytes(a:Uint8Array,b:Uint8Array):boolean {
  if(a.byteLength!==b.byteLength)return false;
  // Uint32 comparisons cover every bit; unaligned views use the byte loop.
  let i=0;if(a.byteOffset%4===0&&b.byteOffset%4===0){const n=a.byteLength>>>2,aa=new Uint32Array(a.buffer,a.byteOffset,n),bb=new Uint32Array(b.buffer,b.byteOffset,n);for(let j=0;j<n;j++)if(aa[j]!==bb[j])return false;i=n*4;}
  for(;i<a.byteLength;i++)if(a[i]!==b[i])return false;return true;
}
function entries(g:THREE.BufferGeometry):[string,Attr][] {
  return [...Object.entries(g.attributes).sort(([a],[b])=>a.localeCompare(b)).map(([k,a])=>['attribute:'+k,attribute(a)] as [string,Attr]),
    ...(g.index?[['index',attribute(g.index)] as [string,Attr]]:[]),
    ...Object.entries(g.morphAttributes).sort(([a],[b])=>a.localeCompare(b)).flatMap(([k,values])=>(values??[]).map((a,i)=>['morph:'+k+':'+i,attribute(a)] as [string,Attr]))];
}
function describe(a:Attr){return {type:a.array.constructor.name,size:a.itemSize,normalized:a.normalized,count:a.count,byteLength:a.array.byteLength,gpuType:a.gpuType,usage:a.usage};}
function geometryRows(roots:readonly THREE.Object3D[]) {
  validateDrawRanges(roots);
  return all(roots).filter(n=>(n as THREE.Mesh).isMesh).sort((a,b)=>a.name.localeCompare(b.name)).map(n=>{const g=(n as THREE.Mesh).geometry;return {n,g,metadata:structuredClone({groups:g.groups,parts:n.userData,drawRange:g.drawRange,morphTargetsRelative:g.morphTargetsRelative}),attrs:entries(g).map(([key,a])=>({key,a,array:a.array,descriptor:describe(a),copy:new Uint8Array(byteView(a))}))};});
}
/** Length-prefixed metadata and raw native array bytes. Little-endian machines
 * only: GLB buffers retain their native typed-array bit patterns (including -0). */
export function binaryGeometryBytes(roots:readonly THREE.Object3D[]):Uint8Array {
  requireThat(new Uint8Array(new Uint32Array([1]).buffer)[0]===1,'Little-endian runtime required');
  const chunks:Uint8Array[]=[];const add=(b:Uint8Array)=>{const length=new Uint8Array(4);new DataView(length.buffer).setUint32(0,b.length,true);chunks.push(length,b);};
  const text=(v:unknown)=>add(new TextEncoder().encode(canonical(v)));
  text('qoima.native.geometry.binary.v1');
  const rows=geometryRows(roots);text(rows.length);
  for(const r of rows){text({name:r.n.name,...r.metadata,drawRange:{start:String(r.g.drawRange.start),count:String(r.g.drawRange.count)},attributes:r.attrs.map(a=>({key:a.key,...a.descriptor}))});for(const a of r.attrs)add(a.copy);}
  const out=new Uint8Array(chunks.reduce((s,c)=>s+c.length,0));let offset=0;for(const c of chunks){out.set(c,offset);offset+=c.length;}return out;
}
export const binaryGeometryHash=(roots:readonly THREE.Object3D[])=>webHash(binaryGeometryBytes(roots));
/** Private byte snapshots; no version counter, needsUpdate, JSON or hash hot path. */
export function createGeometryGuard(roots:readonly THREE.Object3D[]) {
  const rows=geometryRows(roots),members=new Set(rows.map(r=>r.n));
  return ()=>{
    validateDrawRanges(roots);
    const current=all(roots).filter(n=>(n as THREE.Mesh).isMesh);
    requireThat(current.length===rows.length&&current.every(n=>members.has(n)),'Native mesh membership changed');
    for(const r of rows){
      const g=(r.n as THREE.Mesh).geometry;
      requireThat(g===r.g&&same(g.groups,r.metadata.groups)&&same(r.n.userData,r.metadata.parts)&&same(g.drawRange,r.metadata.drawRange)&&g.morphTargetsRelative===r.metadata.morphTargetsRelative,'Native geometry metadata changed');
      const list=entries(g);requireThat(list.length===r.attrs.length,'Native attribute set changed');
      for(let i=0;i<list.length;i++){const [key,a]=list[i],saved=r.attrs[i];requireThat(key===saved.key&&a===saved.a&&a.array===saved.array&&same(describe(a),saved.descriptor)&&equalBytes(byteView(a),saved.copy),'Native geometry bytes/attribute changed');}
    }
  };
}
/** Scene object references, child order, local TRS, visibility, matrix mode,
 * and recursively copied userData. Metadata comparison does not serialize. */
export function createLiveGuard(roots:readonly THREE.Object3D[]) {
  validateDrawRanges(roots);
  const refs=all(roots),members=new Set(refs);
  const rows=refs.map(n=>({n,name:n.name,parent:n.parent,children:[...n.children],p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone(),visible:n.visible,auto:n.matrixAutoUpdate,worldAuto:n.matrixWorldAutoUpdate,data:structuredClone(n.userData)}));
  function check(){validateDrawRanges(roots);const current=all(roots);requireThat(current.length===refs.length&&current.every(n=>members.has(n)),'Native node membership changed');for(const r of rows){const n=r.n;requireThat(n.name===r.name&&n.parent===r.parent&&n.children.length===r.children.length&&n.children.every((c,i)=>c===r.children[i])&&n.position.equals(r.p)&&n.quaternion.equals(r.q)&&n.scale.equals(r.s)&&n.visible===r.visible&&n.matrixAutoUpdate===r.auto&&n.matrixWorldAutoUpdate===r.worldAuto&&same(n.userData,r.data),'Concurrent native hierarchy/TRS/visibility/control mutation');}}
  function refreshTransforms(){validateDrawRanges(roots);for(const r of rows){r.p.copy(r.n.position);r.q.copy(r.n.quaternion);r.s.copy(r.n.scale);}}
  return {check,refreshTransforms};
}
