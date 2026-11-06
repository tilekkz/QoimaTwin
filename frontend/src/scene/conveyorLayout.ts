import * as THREE from 'three';
import { layout } from '../contracts';

/** Finite logical cells retain their IDs. Visual half modules leave room for
 * open junction decks at the exact canonical ports, without a rail across cargo.
 */
export function conveyorVisualPlan(){
  const segments=layout.conveyor.segments;
  const vector=(p:number[])=>new THREE.Vector3(p[0],0,p[2]);
  const points=layout.conveyor.connections.map(connection=>vector(connection.at));
  const directions=(point:THREE.Vector3)=>{
    const arms:THREE.Vector3[]=[];
    for(const segment of segments){
      const start=vector(segment.from);const end=vector(segment.to);const delta=end.clone().sub(start);const length=delta.length();const direction=delta.normalize();
      const offset=point.clone().sub(start);const along=offset.dot(direction);
      if(along<-.00001||along>length+.00001||offset.clone().addScaledVector(direction,-along).length()>.00001)continue;
      if(along>.00001)arms.push(direction.clone().negate());if(along<length-.00001)arms.push(direction.clone());
    }
    return arms.filter((arm,index)=>arms.findIndex(other=>other.distanceTo(arm)<.00001)===index);
  };
  const junctions=points.map((position,index)=>{
    const arms=directions(position);const model=arms.length===2?'conveyor-corner':'conveyor-diverter';
    const base=[new THREE.Vector3(0,0,-1),new THREE.Vector3(1,0,0),...(arms.length===3?[new THREE.Vector3(0,0,1)]:[])];
    let rotation=0;let error=Infinity;
    for(let turn=0;turn<4;turn++){
      const yaw=turn*Math.PI/2;const candidate=base.map(point=>point.clone().applyAxisAngle(new THREE.Vector3(0,1,0),yaw));
      const score=arms.reduce((sum,arm)=>sum+Math.min(...candidate.map(value=>value.distanceToSquared(arm))),0);
      if(score<error){error=score;rotation=yaw;}
    }
    if(error>.0001)throw new Error('Unsupported conveyor junction at '+position.toArray().join(','));
    return{id:'JUNCTION_'+String(index+1).padStart(2,'0'),model,position,rotation,arms:arms.map(arm=>arm.toArray())};
  });
  const cells=[];
  for(const segment of segments){
    const start=vector(segment.from);const direction=vector(segment.to).sub(start).normalize();
    for(let index=0;index<segment.cell_count;index++){
      const from=start.clone().addScaledVector(direction,index);const to=from.clone().add(direction);
      const trimStart=points.some(point=>point.distanceToSquared(from)<1e-9) ? 0.5 : 0;
      const trimEnd=points.some(point=>point.distanceToSquared(to)<1e-9) ? 0.5 : 0;
      const length=1-trimStart-trimEnd;
      if(length<=0)throw new Error('Conveyor junctions require a dedicated cell assembly');
      cells.push({id:`${segment.segment_id}:${index}`,position:from.addScaledVector(direction,trimStart+length/2),rotation:Math.atan2(direction.x,direction.z),scale:new THREE.Vector3(1,1,length)});
    }
  }
  return{cells,junctions};
}
