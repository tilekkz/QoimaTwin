import {readFile,writeFile} from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const output=path.dirname(fileURLToPath(import.meta.url));let script=await readFile(path.join(output,'targeted.mjs'),'utf8');
script=script.replace('export {geometry,witness};','export {geometry,witness,winding,nearest};').replace('const {geometry,witness}=','const {geometry,witness,winding,nearest}=');
script=script.replace('for(const coefficient of [-.6,-.3,.3,.6])','for(const coefficient of ["final"])');
const begin=script.indexOf(' const edited=helper.replace('),end=script.indexOf('\n const js=',begin);script=script.slice(0,begin)+' const edited=helper;'+script.slice(end);
script=script.replace('rows.push({at_s:t,hits});',`const saved=base.native_foreign_and_full_body_gate.material_witnesses.find(w=>w.at_s===t),savedPoint=new T.Vector3(...saved.point_m),savedThigh=body.find(m=>m.bone===saved.bones.find(b=>b.startsWith('joint__thigh_')));rows.push({at_s:t,hits,saved_point_candidate_thigh_solid_angle_rad:winding(savedPoint,savedThigh),saved_point_candidate_thigh_surface_distance_m:nearest(savedPoint,savedThigh).distance_m,saved_point_original_pelvis_solid_angle_rad:winding(savedPoint,pelvis),saved_point_original_pelvis_surface_distance_m:nearest(savedPoint,pelvis).distance_m});`);
script=script.replace("'targeted-results.json'","'final-targeted-results.json'");
await writeFile(path.join(output,'final-targeted.mjs'),script);
