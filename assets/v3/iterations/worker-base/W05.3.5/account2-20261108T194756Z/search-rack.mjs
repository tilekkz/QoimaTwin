// Extend the owned endpoint search to the actual native source rack. No production writes.
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const out=path.dirname(fileURLToPath(import.meta.url));
let code=await readFile(path.join(out,'probe.mjs'),'utf8');
code=code.replace("const supplemental=[","const supplemental=['frontend/public/data/adaptive-v3/layout-manifest.json','frontend/public/models/v3/rack-small.glb','assets/v3/blender/rack-small.stats.json',");
code=code.replaceAll("'source-hashes-before.json'","'search-hashes-before.json'").replaceAll("'source-hashes-after.json'","'search-hashes-after.json'").replaceAll("'native-results.json'","'native-results-with-rack.json'");
code=code.replace("let endpoint=null;const cm=meshes(cargo),deadline=Date.now()+300000;",`const rack=await load('rack-small'),manifest=await json('frontend/public/data/adaptive-v3/layout-manifest.json'),mt=manifest.data.storage.modules,module=mt.rows.map(row=>Object.fromEntries(mt.columns.map((k,i)=>[k,row[i]]))).find(m=>m.module_id==='v3:module:SMALL_W:005');assert(module);world.add(rack);rack.position.fromArray(module.world_pos).sub(new T.Vector3(17.14,0,42.62)).applyAxisAngle(new T.Vector3(0,1,0),-5*Math.PI/2);rack.rotation.y=module.yaw_rad-5*Math.PI/2;world.updateMatrixWorld(true);const rackMeshes=meshes(rack);let endpoint=null;const cm=meshes(cargo),deadline=Date.now()+80000;`);
code=code.replace("[1.08,1.12,1.04,1.16,1.20,1.02]","[1.12,1.16,1.20,1.08,1.04,1.02]");
code=code.replace("if(row.body_HU_witnesses.length)continue;row.self_check=selfCheck(body);",`if(row.body_HU_witnesses.length)continue;row.source_rack_witnesses=[];for(const a of body)for(const b of rackMeshes){const h=H.witness(a,b,true);if(h.found)row.source_rack_witnesses.push({meshes:[a.name,b.name],bones:[a.bone,b.bone],...h});}if(row.source_rack_witnesses.length)continue;row.self_check=selfCheck(body);`);
code=code.replace("native_endpoint_established:!!endpoint,endpoint,attempts,","native_endpoint_established:!!endpoint,source_rack_included:true,source_rack_module:module,endpoint,attempts,");
await writeFile(path.join(out,'probe-with-rack.mjs'),code);
await import(pathToFileURL(path.join(out,'probe-with-rack.mjs')));
