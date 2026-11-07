import {readFile,writeFile} from 'node:fs/promises';
import {GLTFLoader} from '../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
import {Vector3,Raycaster} from '../../../frontend/node_modules/three/build/three.module.js';
globalThis.ProgressEvent??=class ProgressEvent{constructor(type,init={}){this.type=type;Object.assign(this,init);}};
const data=await readFile('frontend/public/models/v3/conveyor-kit.glb');
const gltf=await new Promise((resolve,reject)=>new GLTFLoader().parse(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength),'',resolve,reject));
const scene=gltf.scene;scene.updateMatrixWorld(true);
const units=new Map(),roots=[];scene.traverse(n=>{if(n.userData.fixture_instance_id)units.set(n.userData.fixture_instance_id,n);if(n.name.includes('belt_surface')||n.name.includes('joint__transfer'))roots.push(n);});
if(units.size!==9)throw Error('Wrong physical module count');
const initial=JSON.parse(await readFile('docs/adaptive-v3/evidence/M13-assembly-numeric.json','utf8'));
function port(unit,id){let found;units.get(unit).traverse(n=>{if(n.userData.anchor_id===id)found=n;});if(!found)throw Error('Missing port '+unit+id);return found.getWorldPosition(new Vector3());}
const pairs=initial.connections.map(c=>{const gap=port(...c.from).distanceTo(port(...c.to));if(gap>1e-5)throw Error('ActualGLB gap '+gap);return {...c,actual_glb_gap_m:gap};});
const poses=[];const line=(name,a,b,yaw,steps)=>{for(let i=0;i<=steps;i++)poses.push({name,x:a[0]+(b[0]-a[0])*i/steps,z:a[1]+(b[1]-a[1])*i/steps,yaw});};
line('intake',[4.25,3.05],[4.25,2.25],Math.PI,16);
for(let i=0;i<=32;i++){const t=-Math.PI/2*i/32;poses.push({name:'curve',x:3+1.25*Math.cos(t),z:2.25+1.25*Math.sin(t),yaw:Math.PI-t});}
line('main_to_T',[3,1],[.5,1],Math.PI*1.5,50);
for(let i=0;i<=18;i++)poses.push({name:'stopped_pivot',x:.5,z:1,yaw:Math.PI*1.5+Math.PI/2*i/18});
line('spur_to_work',[.5,1],[.5,3.3],Math.PI*2,46);
line('main_to_output',[.5,1],[-1.7,1],Math.PI*1.5,44);
const ray=new Raycaster(),down=new Vector3(0,-1,0);ray.near=0;ray.far=.4;
let points=0,minSupport=1,minHeight=1,maxHeight=0,seamToleranceRetries=0;
for(const pose of poses){let high=0;
 for(let wi=0;wi<7;wi++)for(let di=0;di<5;di++){
  const w=-.3+wi*.1,d=-.2+di*.1;
  const x=pose.x+w*Math.cos(pose.yaw)+d*Math.sin(pose.yaw),z=pose.z-w*Math.sin(pose.yaw)+d*Math.cos(pose.yaw);
  ray.set(new Vector3(x,1.1,z),down);let hits=ray.intersectObject(scene,true);
  if(!hits.length||hits[0].point.y<.8999){
   for(const [dx,dz]of [[1e-6,0],[-1e-6,0],[0,1e-6],[0,-1e-6]]){
    ray.set(new Vector3(x+dx,1.1,z+dz),down);const retry=ray.intersectObject(scene,true);
    if(retry.length&&retry[0].point.y>=.8999){hits=retry;seamToleranceRetries++;break;}
   }
  }
  if(!hits.length)throw Error('No deck under carrier at '+JSON.stringify({pose,x,z}));
  const y=hits[0].point.y;minHeight=Math.min(minHeight,y);maxHeight=Math.max(maxHeight,y);
  if(y>.9201||y<.8999)throw Error('Raised cap or unsupported carrier: '+y);
  if(y>.9199)high++;
  points++;
 }
 const ratio=high/35;minSupport=Math.min(minSupport,ratio);if(ratio<.80)throw Error('Insufficient coplanar base support: '+ratio);
}
const report={status:'PASS',scope:'Module integration geometry; no source job timing or operational throughput',method:'Actual GLB/Three world transforms + downward raycasts on all real assembly meshes, including guards',modules:9,paired_ports:pairs,carrier_base_xz_m:[.6,.4],poses:poses.length,actual_surface_rays:points,edge_ray_tolerance_m:1e-6,edge_ray_tolerance_retries:seamToleranceRetries,min_coplanar_contact_fraction:minSupport,min_surface_y_m:minHeight,max_surface_y_m:maxHeight,allowable_engineered_disk_clearance_groove_depth_m:.02,raised_crossing_caps:0,source_clock_tested:false};
await writeFile('docs/adaptive-v3/evidence/M13-assembly-runtime-geometry.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,poses:poses.length,rays:points,min_coplanar_support:minSupport,min_y:minHeight,max_y:maxHeight}));
