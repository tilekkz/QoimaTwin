import * as THREE from 'three';
import {digest,nodes,requireThat} from './native';

/** Native local geometry of the complete canonical rig. Root placement and
 * joint rotations are caller pose; all bone/anchor translations and scales
 * remain native. Nonjoint orientation, topology and child order are immutable. */
export function rigSignature(root:THREE.Object3D):string {
 const all=nodes(root);
 return digest(all.map(n=>({name:n.name,type:n.type,parent:all.indexOf(n.parent!),children:n.children.map(c=>all.indexOf(c)),p:n===root?null:n.position.toArray(),s:n.scale.toArray(),q:n===root||n.name.startsWith('joint__')?null:n.quaternion.toArray()})));
}

/** Only reads ancestors. Their state belongs to the host, never to cancel().
 * Absolute warehouse coordinates require an identity, automatically updated
 * chain. Parent identities and raw matrices are checked before every apply. */
export function createWorldFrameGuard(root:THREE.Object3D){
 const rows:{n:THREE.Object3D;parent:THREE.Object3D|null;p:THREE.Vector3;q:THREE.Quaternion;s:THREE.Vector3;matrix:THREE.Matrix4;world:THREE.Matrix4}[]=[];
 const identity=new THREE.Matrix4(),quaternion=new THREE.Quaternion();
 for(let n=root.parent;n;n=n.parent){
  requireThat(n.position.lengthSq()===0&&n.quaternion.equals(quaternion)&&n.scale.toArray().every(x=>x===1)&&n.matrixAutoUpdate&&n.matrixWorldAutoUpdate&&n.matrix.equals(identity)&&n.matrixWorld.equals(identity),'Unsupported absolute world-frame ancestor');
  rows.push({n,parent:n.parent,p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone(),matrix:n.matrix.clone(),world:n.matrixWorld.clone()});
 }
 const parent=root.parent;
 return ()=>{
  requireThat(root.parent===parent,'Absolute world-frame root reparented');
  for(const r of rows){const n=r.n;requireThat(n.parent===r.parent&&n.position.equals(r.p)&&n.quaternion.equals(r.q)&&n.scale.equals(r.s)&&n.matrixAutoUpdate&&n.matrixWorldAutoUpdate&&n.matrix.equals(r.matrix)&&n.matrixWorld.equals(r.world),'Concurrent absolute world-frame ancestor mutation');}
 };
}
