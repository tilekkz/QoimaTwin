import * as THREE from 'three';

const leased=new WeakSet<THREE.Object3D>();
const carrierY=.1238,linkLength=.05;
const capY=(u:number)=>carrierY+Math.sqrt(linkLength**2-(.036+.007*u)**2);

/** One existing synthetic tool; absolute jaw opening, no stock or actor creation. */
export function bindSmallGripper(root:THREE.Object3D){
  if(leased.has(root)||root.userData.asset_id!=='small-package-gripper'||root.userData.namespace!=='v3'||root.userData.units!=='m'||root.userData.engine_operation!==false)throw Error('Нужен свободный ручной захват v3.');
  root.updateWorldMatrix(true,true);
  if(root.getWorldScale(new THREE.Vector3()).toArray().some(x=>Math.abs(x-1)>1e-7))throw Error('Масштаб захвата должен быть 1:1.');
  const required=['joint__jaw_front','joint__jaw_rear','joint__link_front','joint__link_rear','joint__plunger','joint__squeeze_lever'];
  const nodes=new Map(required.map(name=>{const n=root.getObjectByName(name);if(!n)throw Error('Нет узла захвата '+name);return[name,n];}));
  const springs:THREE.Mesh[]=[];
  root.traverse(n=>{if(n instanceof THREE.Mesh&&n.morphTargetDictionary?.jaw_open!==undefined)springs.push(n);});
  if(springs.length!==1||!springs[0].morphTargetInfluences)throw Error('Не сохранена геометрия сжатия пружины.');
  const spring=springs[0],morphIndex=spring.morphTargetDictionary!.jaw_open;
  const saved=[...nodes.values()].map(n=>({node:n,position:n.position.clone(),quaternion:n.quaternion.clone()}));
  const savedMorph=spring.morphTargetInfluences![morphIndex];let released=false,opening=0;
  function assertLive(){if(released)throw Error('Управление захватом освобождено.');}
  function snapshot(){assertLive();return {opening,jaw_gap_m:.04+.014*opening,plunger_y_m:capY(opening),spring_compression:spring.morphTargetInfluences![morphIndex],source_kind:'synthetic_design' as const,engine_operation:false as const,stock_instances:0,certified_handling_admission:false};}
  function apply(value:number){
    assertLive();if(!Number.isFinite(value)||value<0||value>1)throw Error('Раскрытие захвата должно быть от 0 до 1.');
    opening=value;
    for(const[end,sign]of[['front',1],['rear',-1]]as const){
      nodes.get('joint__jaw_'+end)!.position.set(0,0,sign*.007*value);
      const link=nodes.get('joint__link_'+end)!;link.position.set(0,capY(value),0);link.rotation.set(-Math.atan2(sign*(.036+.007*value),capY(value)-carrierY),0,0,'XYZ');
    }
    nodes.get('joint__plunger')!.position.set(0,capY(value),0);nodes.get('joint__squeeze_lever')!.rotation.set(.18*value,0,0,'XYZ');
    spring.morphTargetInfluences![morphIndex]=(capY(0)-capY(value))/(capY(0)-capY(1));
    root.updateWorldMatrix(true,true);return snapshot();
  }
  leased.add(root);apply(0);
  return {apply,snapshot,dispose(){if(released)return;for(const s of saved){s.node.position.copy(s.position);s.node.quaternion.copy(s.quaternion);}spring.morphTargetInfluences![morphIndex]=savedMorph;leased.delete(root);released=true;}};
}
