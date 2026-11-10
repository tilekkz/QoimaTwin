import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import validator from 'gltf-validator';
import path from 'node:path';
import {createHash} from 'node:crypto';
const requested=process.argv.slice(2);const directory='public/models/v3';
const files=requested.length?requested:(await readdir(directory)).filter(n=>n.endsWith('.glb')).map(n=>path.join(directory,n));
const reports=[];
for(const file of files){
 const bytes=await readFile(file);const report=await validator.validateBytes(new Uint8Array(bytes),{uri:path.basename(file)});
 reports.push({file,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),checked_at:new Date().toISOString(),issues:report.issues});
 console.log(JSON.stringify({file,errors:report.issues.numErrors,warnings:report.issues.numWarnings}));
 if(report.issues.numErrors||report.issues.numWarnings)process.exitCode=1;
}
await mkdir('../docs/adaptive-v3/evidence',{recursive:true});
const evidence='../docs/adaptive-v3/evidence/GLB_VALIDATION_V3.json';
let previous=[];
if(requested.length){
 try{const saved=JSON.parse(await readFile(evidence,'utf8'));previous=saved.files.map(r=>({...r,checked_at:r.checked_at||saved.at}));}
 catch(error){if(error.code!=='ENOENT')throw error;}
}
const checked=new Set(reports.map(r=>r.file));
const all=[...previous.filter(r=>!checked.has(r.file)),...reports];
await writeFile(evidence,JSON.stringify({at:new Date().toISOString(),validator:'Khronos gltf-validator',passed:all.every(r=>!r.issues.numErrors&&!r.issues.numWarnings),files:all},null,2));
