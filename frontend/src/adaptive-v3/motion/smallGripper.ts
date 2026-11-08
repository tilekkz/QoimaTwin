import * as THREE from 'three';

const leased=new WeakSet<THREE.Object3D>();
const carrierY=.1238,linkLength=.05;
const capY=(u:number)=>carrierY+Math.sqrt(linkLength**2-(.036+.007*u)**2);
const leverAngle=(u:number)=>{const target=.016+capY(0)-capY(u);let lo=0,hi=.18;for(let i=0;i<44;i++){const a=(lo+hi)/2,length=Math.hypot(.10*(1-Math.cos(a)),.016+.10*Math.sin(a));if(length<target)lo=a;else hi=a;}return u===0?0:(lo+hi)/2;};

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
  const drive=root.userData.manual_drive_version==='v3_radial_button_Bowden';
  if(root.userData.manual_drive_version&&!drive)throw Error('Неподдерживаемая версия ручного привода.');
  const morph=(name:string)=>{let found:THREE.Mesh|undefined;root.traverse(n=>{if(n instanceof THREE.Mesh&&n.morphTargetDictionary?.[name]!==undefined){if(found)throw Error('Неоднозначный привод '+name);found=n;}});if(!found?.morphTargetInfluences)throw Error('Нет геометрии привода '+name);return {mesh:found,index:found.morphTargetDictionary![name],saved:found.morphTargetInfluences![found.morphTargetDictionary![name]]};};
  const wires=drive?[morph('pull_y'),morph('pull_z'),morph('plunger_down')]:[];
  const saved=[...nodes.values()].map(n=>({node:n,position:n.position.clone(),quaternion:n.quaternion.clone()}));
  const savedMorph=spring.morphTargetInfluences![morphIndex];let released=false,opening=0;
  function assertLive(){if(released)throw Error('Управление захватом освобождено.');}
  let thumbPress=0;
  function snapshot(){assertLive();return {opening,jaw_gap_m:.04+.014*opening,plunger_y_m:capY(opening),spring_compression:spring.morphTargetInfluences![morphIndex],manual_drive:drive,lever_angle_rad:drive?-leverAngle(opening):.18*opening,manual_thumb_retraction_m:-.005,manual_thumb_press_rad:thumbPress,source_kind:'synthetic_design' as const,engine_operation:false as const,stock_instances:0,certified_handling_admission:false};}
  function apply(value:number){
    assertLive();if(!Number.isFinite(value)||value<0||value>1)throw Error('Раскрытие захвата должно быть от 0 до 1.');
    opening=value;
    for(const[end,sign]of[['front',1],['rear',-1]]as const){
      nodes.get('joint__jaw_'+end)!.position.set(0,0,sign*.007*value);
      const link=nodes.get('joint__link_'+end)!;link.position.set(0,capY(value),0);link.rotation.set(-Math.atan2(sign*(.036+.007*value),capY(value)-carrierY),0,0,'XYZ');
    }
    nodes.get('joint__plunger')!.position.set(0,capY(value),0);nodes.get('joint__squeeze_lever')!.rotation.set(drive?-leverAngle(value):.18*value,0,0,'XYZ');
    spring.morphTargetInfluences![morphIndex]=(capY(0)-capY(value))/(capY(0)-capY(1));
    if(drive){const a=leverAngle(value),maximum=leverAngle(1);for(const[w,i]of wires.map((w,i)=>[w,i]as const))w.mesh.morphTargetInfluences![w.index]=i===0?(1-Math.cos(a))/(1-Math.cos(maximum)):i===1?Math.sin(a)/Math.sin(maximum):(capY(0)-capY(value))/(capY(0)-capY(1));}
    root.updateWorldMatrix(true,true);
    if(drive){
      const tab=root.getObjectByName('thumb_tab_frame');if(!tab)throw Error('Нет кнопки под большой палец.');
      const inverse=root.matrixWorld.clone().invert(),q=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),-Math.PI*5/8),points:THREE.Vector3[]=[];
      tab.traverse(n=>{if(n instanceof THREE.Mesh)for(let i=0;i<n.geometry.getAttribute('position').count;i++)points.push(n.getVertexPosition(i,new THREE.Vector3()).applyMatrix4(n.matrixWorld).applyMatrix4(inverse).sub(new THREE.Vector3(0,.148,.23)).applyQuaternion(q).add(new THREE.Vector3(.007,-.05,.05)));});
      const gap=(a:number)=>Math.max(...points.map(p=>(p.y+.006)*Math.cos(a)+(p.z+.020)*Math.sin(a)+.020));
      if(gap(0)>2e-6||gap(.06)<-2e-6)throw Error('Кнопка вне хода большого пальца.');
      let lo=0,hi=.06;if(gap(0)>=0)hi=0;else for(let i=0;i<44;i++){const a=(lo+hi)/2;if(gap(a)<0)lo=a;else hi=a;}thumbPress=(lo+hi)/2;
    }
    return snapshot();
  }
  leased.add(root);apply(0);
  return {apply,snapshot,dispose(){if(released)return;for(const s of saved){s.node.position.copy(s.position);s.node.quaternion.copy(s.quaternion);}spring.morphTargetInfluences![morphIndex]=savedMorph;for(const w of wires)w.mesh.morphTargetInfluences![w.index]=w.saved;leased.delete(root);released=true;}};
}
