import * as THREE from 'three';
import type { VisualFrame, VisualRun } from '../replay/types';
import { createRiggedModel } from './riggedModel';
import {layout} from '../contracts';
import {upperBound} from '../replay/core';

type Entry={id:string;position:THREE.Vector3;rotation?:number;scale?:THREE.Vector3;color?:THREE.Color};
type Batch={meshes:THREE.InstancedMesh[];set:(entries:Entry[])=>void};
type Rig=ReturnType<typeof createRiggedModel>;
type Options={group:THREE.Group;templates:Map<string,THREE.Group>;camera:THREE.Camera;selected:()=>string;roleColors:Record<string,string>;batch:(name:string,id:string,capacity:number,entries:Entry[],kind:string,role?:string)=>Batch};

/** Only presentation: all positions, stages and attachments come from the replay. */
export function createWarehouseMotion(options:Options){
  const {group,templates,camera,batch}=options;
  const positions=new Map<string,Entry>();const rigs=new Map<string,Rig>();
  const modelIds=new Map<string,string>();const modelBounds=new Map<string,THREE.Box3>();
  const owned:THREE.BufferGeometry[]=[];const materials:THREE.Material[]=[];
  const batches=new Map<string,Batch>();
  const peopleRoles=['picker','packer','receiver','shipper'];
  for(const role of peopleRoles){
    batches.set(role+':far',batch('staff:'+role+':far','worker-low',24,[],'actor',role));
    batches.set(role+':near',batch('staff:'+role+':near',role==='picker'?'picker-worker':'standing-worker',24,[],'actor',role));
  }
  batches.set('drivers',batch('seated drivers','driver',2,[],'actor'));
  batches.set('fleet',batch('forklifts','forklift',2,[],'vehicle'));
  batches.set('carts',batch('picking carts','picking-cart',12,[],'cart'));
  batches.set('carts:far',batch('distant picking carts','__cart-low',12,[],'cart'));
  batches.set('totes',batch('empty tote pool','tote-low',96,[],'tote'));
  for(const [kind,id]of [['tote','order-tote'],['parcel','sealed-parcel'],['pallet','pallet'],['lot','crate']]){
    batches.set(kind,batch('cargo:'+kind,id,128,[],'cargo'));
  }
  batches.set('contents',batch('picked item symbols','crate',96,[],'content'));
  batches.set('packing',batch('packing stations','packing-station',6,[],'pack'));
  batches.set('work-carton',batch('empty packing shells','__packing-wip',6,[],'work-prop'));
  batches.set('hand-scanner',batch('handheld scanners','__hand-scanner',4,[],'tool'));
  const markerGeometry=new THREE.RingGeometry(.34,.38,24).rotateX(-Math.PI/2);owned.push(markerGeometry);
  const markerMaterial=new THREE.MeshBasicMaterial({color:'#d5a343',transparent:true,opacity:.75,depthWrite:false});materials.push(markerMaterial);
  const marker=new THREE.Mesh(markerGeometry,markerMaterial);marker.visible=false;group.add(marker);
  const statusGeometry=new THREE.SphereGeometry(.055,8,5);owned.push(statusGeometry);
  const statusMaterial=new THREE.MeshBasicMaterial({color:'#71aa8c'});materials.push(statusMaterial);
  const statusLed=new THREE.Mesh(statusGeometry,statusMaterial);statusLed.position.set(20,.99,6);group.add(statusLed);
  const holdGeometry=new THREE.BoxGeometry(.58,.008,1);owned.push(holdGeometry);
  const holdMaterial=new THREE.MeshBasicMaterial({color:'#d7a438',transparent:true,opacity:.23,depthWrite:false});materials.push(holdMaterial);
  const holdOverlay=new THREE.Mesh(holdGeometry,holdMaterial);holdOverlay.visible=false;group.add(holdOverlay);
  let route:THREE.Line|undefined;let lastRoute='';let latest:VisualFrame|undefined;
  let indexedRun:VisualRun|undefined;
  const pickedByOrder=new Map<string,VisualRun['events']>();const actionById=new Map<string,VisualRun['actions'][number]>();const firstActionByActor=new Map<string,number>();
  const vector=(position:readonly number[])=>new THREE.Vector3().fromArray(position);
  const offset=(position:readonly number[],yaw:number,local:readonly number[])=>vector(position).add(new THREE.Vector3(local[0],local[1],local[2]).applyAxisAngle(new THREE.Vector3(0,1,0),yaw));
  const rigFor=(key:string,id:string,role?:string,includeWorkProps=false)=>{
    let rig=rigs.get(key);
    if(!rig){rig=createRiggedModel(templates.get(id)!,role?new THREE.Color(options.roleColors[role]):undefined,{includeWorkProps});rig.group.traverse(object=>{if(object instanceof THREE.Mesh){object.castShadow=true;object.receiveShadow=true;}});rig.group.userData.entityId=key;rig.group.userData.kind='actor';group.add(rig.group);rigs.set(key,rig);}
    return rig;
  };
  const update=(frame:VisualFrame,run:VisualRun,reducedMotion:boolean)=>{
    if(indexedRun!==run){
      pickedByOrder.clear();actionById.clear();firstActionByActor.clear();
      for(const action of run.actions){actionById.set(action.action_id,action);firstActionByActor.set(action.actor_id,Math.min(firstActionByActor.get(action.actor_id)??Infinity,action.start_s));}
      for(const event of run.events)if(event.kind==='sku_picked'&&typeof event.payload.order_id==='string'){const list=pickedByOrder.get(event.payload.order_id)||[];list.push(event);pickedByOrder.set(event.payload.order_id,list);}
      indexedRun=run;
    }
    latest=frame;positions.clear();modelIds.clear();rigs.forEach(rig=>rig.group.visible=false);
    const selected=options.selected();const entries=new Map<string,Entry[]>();
    const put=(key:string,entry:Entry)=>{const values=entries.get(key)||[];values.push(entry);entries.set(key,values);};
    const heroes=Object.values(frame.actors).filter(actor=>actor.id===selected||camera.position.distanceTo(vector(actor.pos))<13)
      .sort((a,b)=>(b.id===selected?1000:0)+(b.state!=='IDLE'?100:0)-((a.id===selected?1000:0)+(a.state!=='IDLE'?100:0))+camera.position.distanceToSquared(vector(a.pos))-camera.position.distanceToSquared(vector(b.pos)))
      .slice(0,4);
    const heroIds=new Set(heroes.map(actor=>actor.id));
    for(const station of layout.pack_stations){
      const actor=Object.values(frame.actors).find(actor=>actor.role==='packer'&&actor.id==='K'+station.pack_id.slice(2));
      const position=new THREE.Vector3(station.worker_pos[0],0,station.worker_pos[2]);
      positions.set(station.pack_id,{id:station.pack_id,position});modelIds.set(station.pack_id,'packing-station');
      if(actor?.operation==='pack'&&heroIds.has(actor.id)){
        const rig=rigFor(station.pack_id,'packing-station',undefined,true);rig.group.userData.kind='pack';rig.group.visible=true;rig.group.position.copy(position);
        const close=Math.min(1,Math.max(0,(actor.phase-.65)/.3));
        rig.pose({pivot_carton_flap_left:[0,0,-close*2.5307274],pivot_carton_flap_right:[0,0,close*2.5307274],pivot_carton_flap_front:[-close*2.5307274,0,0],pivot_carton_flap_rear:[close*2.5307274,0,0]});
      }else{
        put('packing',{id:station.pack_id,position});
        if(actor?.operation==='pack')put('work-carton',{id:station.pack_id+':empty-shell',position});
      }
    }
    for(const actor of Object.values(frame.actors)){
      const pos=vector(actor.pos);let yaw=actor.yaw;
      // Offsets resolve coincident home poses and the workstation's logical root.
      // They never alter actor.pos or route lengths in the replay.
      const parked=actor.role==='picker'&&actor.state==='IDLE'&&(firstActionByActor.get(actor.id)??Infinity)>frame.time;
      if(parked){
        const parsed=Number(actor.id.slice(1))-1;const index=Number.isFinite(parsed)?parsed:Object.values(frame.actors).filter(value=>value.role==='picker').findIndex(value=>value.id===actor.id);
        pos.x+=(index%2-.5)*1.56;pos.z+=Math.floor(index%4/2)*.75;yaw=Math.PI;
      }
      if(actor.role==='packer')pos.z+=.85;
      // R02's canonical initial point is also FI_PICK. A standing offset keeps
      // the idle figure beside the arriving vehicle; the logical point stays intact.
      if(actor.id==='R02'&&actor.state==='IDLE')pos.x+=1.1;
      if(actor.id==='S02'&&actor.state==='IDLE')pos.x+=1;
      const logical:Entry={id:actor.id,position:pos,rotation:yaw};positions.set(actor.id,logical);
      modelIds.set(actor.id,actor.role==='forklift_driver'?'forklift':actor.role==='picker'?'picker-worker':'standing-worker');
      if(actor.role==='forklift_driver'){
        const vehicle=actor.vehicleId!;const vehicleEntry={id:vehicle,position:pos,rotation:yaw};
        positions.set(vehicle,vehicleEntry);modelIds.set(vehicle,'forklift');
        if(heroIds.has(actor.id)){
          const rig=rigFor(vehicle,'forklift');rig.group.userData.kind='vehicle';rig.group.visible=true;rig.group.position.copy(pos);rig.group.rotation.y=yaw;
          const rotations:Record<string,number[]>={};
          for(const end of ['front','rear'])for(const side of ['left','right']){const name=`pivot_wheel_${end}_${side}_spin`;const radius=Number(rig.joints.get(name)?.userData.radius_m)||.3;rotations[name]=[actor.pose.wheelAngle*.3/radius,0,0];}
          const steer=actor.operation==='turn'?Math.sin(actor.phase*Math.PI)*.55:0;
          rotations.pivot_wheel_rear_left_steer=[0,steer,0];rotations.pivot_wheel_rear_right_steer=[0,steer,0];rotations.pivot_steering_wheel=[0,steer*2,0];
          rig.pose(rotations,{pivot_carriage:[0,actor.pose.lift||0,0]});
        }else put('fleet',vehicleEntry);
        const driverPos=offset(pos.toArray(),yaw,[0,.99,-.65]);
        if(heroIds.has(actor.id)){
          const rig=rigFor(actor.id,'driver');rig.group.visible=true;rig.group.position.copy(driverPos);rig.group.rotation.y=yaw;rig.pose(actor.pose.jointRotations);
        }else put('drivers',{id:actor.id,position:driverPos,rotation:yaw});
        continue;
      }
      if(heroIds.has(actor.id)){
        const model=actor.role==='picker'?'picker-worker':'standing-worker';const rig=rigFor(actor.id,model,actor.role);
        rig.group.visible=true;rig.group.position.copy(pos).add(vector(actor.pose.rootOffset));rig.group.rotation.y=yaw;rig.pose(actor.pose.jointRotations);
      }else put(actor.role+(camera.position.distanceTo(pos)<16?':near':':far'),logical);
      if(actor.role==='receiver'||actor.role==='shipper'&&actor.operation==='scan'){
        const wrist=rigs.get(actor.id)?.group.visible?rigs.get(actor.id)!.worldPoint('hand_R'):undefined;
        put('hand-scanner',{id:actor.id+':scanner',position:wrist||offset(pos.toArray(),yaw,[.247,.88,.055]),rotation:yaw,scale:new THREE.Vector3(.7,.7,.7)});
      }
      if(actor.role==='picker'){
        // Cart stays parked while the worker turns to reach a shelf.
        const cartYaw=parked?Math.PI:actor.cartYaw;
        const cartEntry={id:'CART_'+actor.id,position:offset(pos.toArray(),cartYaw,[0,0,.62]),rotation:cartYaw};
        positions.set(cartEntry.id,cartEntry);
        modelIds.set(cartEntry.id,'picking-cart');
        if(heroIds.has(actor.id)&&actor.state==='TRAVEL'){
          const rig=rigFor('CART_'+actor.id,'picking-cart');rig.group.userData.kind='cart';rig.group.visible=true;rig.group.position.copy(cartEntry.position);rig.group.rotation.y=cartYaw;
          const rotations:Record<string,number[]>={};for(const side of ['L','R'])for(const end of ['front','rear'])rotations[`wheel_${end}_${side}`]=[actor.pose.wheelAngle,0,0];rig.pose(rotations);
        }else put(camera.position.distanceTo(cartEntry.position)>16?'carts:far':'carts',cartEntry);
      }
    }
    for(let i=0;i<96;i++){
      const id='T'+String(i+1).padStart(3,'0');const cargo=frame.cargo[id];
      if(cargo?.visible)continue;
      put('totes',{id,position:new THREE.Vector3(8+(i%12)*.64,.3*Math.floor(i/24),3.4+Math.floor(i%24/12)*.48)});
    }
    for(const cargo of Object.values(frame.cargo)){
      if(!cargo.visible)continue;
      put(cargo.kind,{id:cargo.id,position:vector(cargo.pos),rotation:cargo.yaw});
      positions.set(cargo.id,{id:cargo.id,position:vector(cargo.pos),rotation:cargo.yaw});
      modelIds.set(cargo.id,({tote:'order-tote',parcel:'sealed-parcel',pallet:'pallet',lot:'crate'})[cargo.kind]);
      if(cargo.kind==='pallet'&&!cargo.orderIds.length){
        // Two stacked carton pairs are a load symbol, never a unit count.
        for(let index=0;index<4;index++)put('lot',{id:cargo.id+':load-symbol:'+index,position:offset(cargo.pos,cargo.yaw,[(index%2-.5)*.6,.14+.225+.45*Math.floor(index/2),0]),rotation:cargo.yaw});
      }
      if(cargo.kind==='tote'&&cargo.orderIds.length){
        const picked=cargo.orderIds.flatMap(orderId=>{const list=pickedByOrder.get(orderId)||[];return list.slice(0,Math.min(4,upperBound(list,frame.time,event=>event.at_s)));}).slice(0,4);
        // Unit packs fit the tote interior; a stock case is never crammed into it.
        picked.slice(0,4).forEach((event,index)=>put('contents',{id:cargo.id+':'+event.seq,position:offset(cargo.pos,cargo.yaw,[(index%2-.5)*.24,.10,Math.floor(index/2)*.18-.09]),rotation:cargo.yaw,scale:new THREE.Vector3(.32,.267,.185)}));
      }
    }
    for(const [key,value]of batches)value.set(entries.get(key)||[]);
    statusMaterial.color.set(frame.line.blocked?'#d69b35':'#71aa8c');
    const held=Object.values(frame.cargo).find(cargo=>cargo.visible&&cargo.kind==='tote'&&cargo.stage==='conveyor');
    holdOverlay.visible=frame.line.blocked&&!!held;
    if(held){holdOverlay.position.copy(vector(held.pos)).add(new THREE.Vector3(0,.006,0));holdOverlay.rotation.y=held.yaw;}
    marker.visible=false;
    const pulse=frame.pulses.at(-1);const pulsePosition=pulse&&positions.get(pulse.entityId);
    if(pulse&&pulsePosition&&!reducedMotion){marker.visible=true;marker.position.copy(pulsePosition.position);marker.position.y=.016;markerMaterial.opacity=pulse.opacity;}
    const actor=frame.actors[selected];const action=actor?.actionId&&actionById.get(actor.actionId);
    const key=action&&typeof action!=='string'&&action.waypoints?action.action_id:'';
    if(key!==lastRoute){
      if(route){route.geometry.dispose();(route.material as THREE.Material).dispose();route.removeFromParent();route=undefined;}
      if(action&&typeof action!=='string'&&action.waypoints){
        route=new THREE.Line(new THREE.BufferGeometry().setFromPoints(action.waypoints.map(point=>vector(point.pos).setY(.025))),new THREE.LineBasicMaterial({color:'#278f84',transparent:true,opacity:.7}));group.add(route);
      }lastRoute=key;
    }
  };
  const boundsFor=(id:string,visited=new Set<string>()):THREE.Box3|undefined=>{
    if(visited.has(id))return undefined;visited.add(id);
    const vehicleId=latest?.actors[id]?.vehicleId;
    const rig=rigs.get(vehicleId||id);let result:THREE.Box3|undefined;
    if(rig?.group.visible)result=rig.worldBounds();
    else{
      const entry=positions.get(id);const model=modelIds.get(id);if(!entry||!model)return undefined;
      let bounds=modelBounds.get(model);if(!bounds){bounds=new THREE.Box3().setFromObject(templates.get(model)!,true);modelBounds.set(model,bounds);}
      result=bounds.clone().applyMatrix4(new THREE.Matrix4().compose(entry.position,new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),entry.rotation||0),new THREE.Vector3(1,1,1)));
    }
    for(const cargo of Object.values(latest?.cargo||{})){
      if(!cargo.visible)continue;
      if(cargo.attachment.id===id||(vehicleId&&cargo.attachment.id===vehicleId)){const child=boundsFor(cargo.id,visited);if(child)result.union(child);}
    }
    const cart=positions.has('CART_'+id)?boundsFor('CART_'+id,visited):undefined;if(cart)result.union(cart);
    const cargo=latest?.cargo[id];
    if(cargo?.kind==='pallet'&&!cargo.orderIds.length){
      const crateBounds=new THREE.Box3().setFromObject(templates.get('crate')!,true);
      for(let index=0;index<4;index++)result.union(crateBounds.clone().applyMatrix4(new THREE.Matrix4().compose(offset(cargo.pos,cargo.yaw,[(index%2-.5)*.6,.14+.225+.45*Math.floor(index/2),0]),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),cargo.yaw),new THREE.Vector3(1,1,1))));
    }
    return result;
  };
  return{update,positions,rigs,boundsFor,visibleEntityIds:(kind:string)=>[...rigs].filter(([,rig])=>rig.group.visible&&rig.group.userData.kind===kind).map(([id])=>id),inspectRig:(id:string)=>{const rig=rigs.get(id);return rig?.group.visible?rig.inspect():undefined;},getState:()=>({actors:Object.keys(latest?.actors||{}),cargo:Object.values(latest?.cargo||{}).filter(cargo=>cargo.visible).map(cargo=>cargo.id),heroIds:[...rigs].filter(([,rig])=>rig.group.visible).map(([id])=>id)}),dispose(){rigs.forEach(rig=>rig.dispose());owned.forEach(geometry=>geometry.dispose());materials.forEach(material=>material.dispose());if(route){route.geometry.dispose();(route.material as THREE.Material).dispose();} }};
}

