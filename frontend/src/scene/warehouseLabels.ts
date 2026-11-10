import * as THREE from 'three';
import {layout} from '../contracts';

/** Eighteen floor IDs in a single local atlas/draw call. No floating label wall. */
export function createWarehouseLabels(){
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=256;
  const context=canvas.getContext('2d')!;context.fillStyle='#536d61';context.font='600 38px Segoe UI, sans-serif';context.textAlign='center';context.textBaseline='middle';
  const labels=Array.from({length:12},(_,index)=>({text:'A'+String(index+1).padStart(2,'0'),x:10+4.5*index,z:13.55,width:1.4}));
  labels.push(...layout.pack_stations.map(pack=>({text:pack.pack_id,x:pack.worker_pos[0],z:3.6,width:1.4})));
  const positions:number[]=[];const uvs:number[]=[];const indices:number[]=[];
  labels.forEach((label,index)=>{
    const column=index%8;const row=Math.floor(index/8);context.fillText(label.text,column*128+64,row*64+32);
    const half=label.width/2;const depth=.4;const vertex=index*4;
    positions.push(label.x-half,.013,label.z-depth/2,label.x+half,.013,label.z-depth/2,label.x+half,.013,label.z+depth/2,label.x-half,.013,label.z+depth/2);
    const x=column/8;const y=1-(row+1)/4;uvs.push(x,y+.25,x+.125,y+.25,x+.125,y,x,y);
    indices.push(vertex,vertex+2,vertex+1,vertex,vertex+3,vertex+2);
  });
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));geometry.setIndex(indices);geometry.computeBoundingSphere();
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  const material=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,side:THREE.DoubleSide});
  const mesh=new THREE.Mesh(geometry,material);mesh.name='18 canonical floor IDs';
  return{mesh,dispose(){geometry.dispose();texture.dispose();material.dispose();}};
}
