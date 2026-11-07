import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import validator from 'gltf-validator';
import path from 'node:path';
const requested=process.argv.slice(2);const directory='public/models/v3';
const files=requested.length?requested:(await readdir(directory)).filter(n=>n.endsWith('.glb')).map(n=>path.join(directory,n));
const reports=[];
for(const file of files){
 const bytes=await readFile(file);const report=await validator.validateBytes(new Uint8Array(bytes),{uri:path.basename(file)});
 reports.push({file,bytes:bytes.length,issues:report.issues});
 console.log(JSON.stringify({file,errors:report.issues.numErrors,warnings:report.issues.numWarnings}));
 if(report.issues.numErrors||report.issues.numWarnings)process.exitCode=1;
}
await mkdir('../docs/adaptive-v3/evidence',{recursive:true});
await writeFile('../docs/adaptive-v3/evidence/GLB_VALIDATION_V3.json',JSON.stringify({at:new Date().toISOString(),validator:'Khronos gltf-validator',passed:reports.every(r=>!r.issues.numErrors&&!r.issues.numWarnings),files:reports},null,2));
