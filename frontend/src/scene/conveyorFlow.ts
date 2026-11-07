import * as THREE from 'three';
import type {VisualRun} from '../replay/types';

type Cell={id:string;position:THREE.Vector3;rotation?:number;scale?:THREE.Vector3};

/** A moving belt surface, measured in metres, driven by the absolute replay clock. */
export function createConveyorFlow(cells:Cell[]){
  const canvas=document.createElement('canvas');canvas.width=32;canvas.height=64;
  const context=canvas.getContext('2d')!;
  context.fillStyle='#385357';context.fillRect(0,0,32,64);
  context.fillStyle='#294246';context.fillRect(0,0,32,3);
  context.fillStyle='#577274';context.fillRect(0,3,32,1);
  for(let x=3;x<32;x+=6){context.fillStyle='rgba(200,220,215,.065)';context.fillRect(x,6,1,52);}
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(1,1/.16);texture.anisotropy=4;
  const material=new THREE.MeshStandardMaterial({map:texture,roughness:.84,metalness:.04,polygonOffset:true,polygonOffsetFactor:-1});
  const geometry=new THREE.PlaneGeometry(.61,1).rotateX(-Math.PI/2);
  const lengths=new Float32Array(cells.map(cell=>cell.scale?.z??1));
  const phases=new THREE.InstancedBufferAttribute(new Float32Array(cells.length),1).setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('flowLength',new THREE.InstancedBufferAttribute(lengths,1));geometry.setAttribute('flowPhase',phases);
  material.onBeforeCompile=shader=>{
    shader.vertexShader='attribute float flowLength;\nattribute float flowPhase;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>','#include <uv_vertex>\n#ifdef USE_MAP\nvMapUv=(mapTransform*vec3(uv.x,uv.y*flowLength+flowPhase,1.0)).xy;\n#endif');
  };
  material.customProgramCacheKey=()=> 'qoima-belt-metres-v1';
  const mesh=new THREE.InstancedMesh(geometry,material,cells.length);mesh.name='Continuous moving belt surfaces';mesh.receiveShadow=true;
  const dummy=new THREE.Object3D();
  cells.forEach((cell,index)=>{dummy.position.copy(cell.position);dummy.position.y=.9025;dummy.rotation.set(0,cell.rotation||0,0);dummy.scale.set(1,1,lengths[index]);dummy.updateMatrix();mesh.setMatrixAt(index,dummy.matrix);});
  mesh.computeBoundingSphere();
  const segments=cells.map(cell=>cell.id.split(':')[0]);const uniqueSegments=[...new Set(segments)];
  return{mesh,update(time:number,run:VisualRun,reducedMotion:boolean){
    const elapsed=new Map<string,number>();
    for(const segment of uniqueSegments){
      const held=run.blocked.filter(block=>block.segment_ids.includes(segment)).reduce((sum,block)=>sum+Math.max(0,Math.min(time,block.end_s)-block.start_s),0);
      elapsed.set(segment,reducedMotion?0:(time-held)% .16);
    }
    segments.forEach((segment,index)=>phases.setX(index,elapsed.get(segment)!));phases.needsUpdate=true;
  },getState:()=>({cellCount:cells.length,phases:Object.fromEntries(uniqueSegments.map(segment=>[segment,phases.getX(segments.indexOf(segment))]))}),dispose(){mesh.dispose();geometry.dispose();material.dispose();texture.dispose();mesh.removeFromParent();}};
}
