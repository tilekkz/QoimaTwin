import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/** Rigid authored pivots, batched into one dynamic surface per material.
 * The editable GLB hierarchy remains the pose source. Baking only nearby heroes
 * avoids sixty draw calls for each of the 24 small figures. No business state here.
 */
export function createRiggedModel(template:THREE.Group, tint?:THREE.Color, options:{includeWorkProps?:boolean}={}){
  const skeleton=template.clone(true);
  const group=new THREE.Group();
  const joints=new Map<string,THREE.Object3D>();
  const bind=new Map<THREE.Object3D,{q:THREE.Quaternion;p:THREE.Vector3}>();
  const sources:THREE.Mesh[]=[];
  skeleton.traverse(object=>{
    bind.set(object,{q:object.quaternion.clone(),p:object.position.clone()});
    const name=object.userData.joint_name||object.userData.pivot_name;
    if(name)joints.set(name,object);
    joints.set(object.name,object);
    if(object instanceof THREE.Mesh&&!Array.isArray(object.material)){
      let hidden=false;for(let ancestor:THREE.Object3D|null=object;ancestor;ancestor=ancestor.parent)if(ancestor.userData.runtime_default_visible===false)hidden=true;
      if(!hidden||options.includeWorkProps)sources.push(object);
    }
  });
  skeleton.updateMatrixWorld(true);
  type Range={source:THREE.Mesh;geo:THREE.BufferGeometry;start:number};
  const batches=new Map<THREE.Material,{ranges:Range[];geos:THREE.BufferGeometry[]}>();
  for(const source of sources){
    const geometry=source.geometry.index?source.geometry.toNonIndexed():source.geometry.clone();
    const material=source.material as THREE.MeshStandardMaterial;
    const batch=batches.get(material)||{ranges:[],geos:[]};
    const start=batch.geos.reduce((sum,geo)=>sum+geo.getAttribute('position').count,0);
    batch.ranges.push({source,geo:geometry,start});
    batch.geos.push(geometry.clone().applyMatrix4(source.matrixWorld));
    batches.set(material,batch);
  }
  const surfaces:{geometry:THREE.BufferGeometry;ranges:Range[]}[]=[];
  const ownMaterials:THREE.Material[]=[];
  for(const [base,batch] of batches){
    const geometry=mergeGeometries(batch.geos,false)!;batch.geos.forEach(geo=>geo.dispose());
    let material=base as THREE.MeshStandardMaterial;
    if(tint&&/cloth|shirt|uniform/i.test(material.name)){
      material=material.clone();material.color.copy(tint);ownMaterials.push(material);
    }
    (geometry.getAttribute('position') as THREE.BufferAttribute).setUsage(THREE.DynamicDrawUsage);
    (geometry.getAttribute('normal') as THREE.BufferAttribute)?.setUsage(THREE.DynamicDrawUsage);
    const surface=new THREE.Mesh(geometry,material);surface.frustumCulled=false;group.add(surface);
    surfaces.push({geometry,ranges:batch.ranges});
  }
  const rotation=new THREE.Quaternion();const euler=new THREE.Euler();
  const normalMatrix=new THREE.Matrix3();const point=new THREE.Vector3();const normal=new THREE.Vector3();
  const posedBounds=new THREE.Box3();
  const pose=(rotations:Record<string,readonly number[]>,translations:Record<string,readonly number[]>={})=>{
    posedBounds.makeEmpty();
    for(const [object,rest]of bind){object.quaternion.copy(rest.q);object.position.copy(rest.p);}
    for(const [name,value]of Object.entries(rotations)){
      const joint=joints.get(name);if(!joint)continue;
      rotation.setFromEuler(euler.set(value[0]||0,value[1]||0,value[2]||0));
      joint.quaternion.multiply(rotation);
    }
    for(const [name,value]of Object.entries(translations)){
      const joint=joints.get(name);if(joint)joint.position.add(new THREE.Vector3().fromArray(value));
    }
    skeleton.updateMatrixWorld(true);
    for(const {geometry,ranges}of surfaces){
      const bounds=new THREE.Box3();
      const positions=geometry.getAttribute('position') as THREE.BufferAttribute;
      const normals=geometry.getAttribute('normal') as THREE.BufferAttribute;
      for(const range of ranges){
        const local=range.geo.getAttribute('position');const localNormals=range.geo.getAttribute('normal');
        normalMatrix.getNormalMatrix(range.source.matrixWorld);
        for(let index=0;index<local.count;index++){
          point.fromBufferAttribute(local,index).applyMatrix4(range.source.matrixWorld);
          bounds.expandByPoint(point);
          positions.setXYZ(range.start+index,point.x,point.y,point.z);
          if(normals&&localNormals){
            normal.fromBufferAttribute(localNormals,index).applyNormalMatrix(normalMatrix);
            normals.setXYZ(range.start+index,normal.x,normal.y,normal.z);
          }
        }
      }
      positions.needsUpdate=true;if(normals)normals.needsUpdate=true;
      geometry.boundingBox=bounds;geometry.boundingSphere=bounds.getBoundingSphere(new THREE.Sphere());posedBounds.union(bounds);
    }
  };
  const inspect=()=>{
    group.updateWorldMatrix(true,false);skeleton.updateMatrixWorld(true);
    return{rootWorld:group.getWorldPosition(new THREE.Vector3()).toArray(),nodes:Object.fromEntries([...joints].filter(([name])=>/^(anchor_|pivot_|hand_|foot_)/.test(name)).map(([name,node])=>[name,node.getWorldPosition(new THREE.Vector3()).applyMatrix4(group.matrixWorld).toArray()]))};
  };
  return{group,pose,joints,inspect,worldPoint:(name:string)=>{group.updateWorldMatrix(true,false);const joint=joints.get(name);return joint?.getWorldPosition(new THREE.Vector3()).applyMatrix4(group.matrixWorld);},worldBounds:()=>{group.updateWorldMatrix(true,false);return posedBounds.clone().applyMatrix4(group.matrixWorld);},dispose(){
    surfaces.forEach(surface=>{surface.geometry.dispose();surface.ranges.forEach(range=>range.geo.dispose());});
    ownMaterials.forEach(material=>material.dispose());group.removeFromParent();
  }};
}
