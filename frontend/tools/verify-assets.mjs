import { readFile, readdir, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import validator from 'gltf-validator';

const directory = new URL('../public/models/', import.meta.url);
const files = (await readdir(directory)).filter((name) => name.endsWith('.glb'));
for (const name of (await readdir(new URL('v2/',directory))).filter(name=>name.endsWith('.glb'))) files.push(`v2/${name}`);
if (!files.length) throw new Error('No GLB assets. Run tools/export-calibration.ps1 first.');
const reports=[];
for (const file of files) {
  const path = new URL(file, directory);
  const bytes = await readFile(path);
  const result = await validator.validateBytes(new Uint8Array(bytes), { uri: file });
  reports.push({path:`frontend/public/models/${file}`,bytes:bytes.length,issues:result.issues});
  console.log(JSON.stringify({ file: fileURLToPath(path), bytes: bytes.length, issues: result.issues }));
  if (result.issues.numErrors) process.exitCode = 1;
}
const reportDirectory=new URL('../../docs/visual/',import.meta.url);
await mkdir(reportDirectory,{recursive:true});
await writeFile(new URL('GLB_VALIDATION.json',reportDirectory),JSON.stringify({timestampUtc:new Date().toISOString(),validator:'Khronos gltf-validator 2.0.0-dev.3.10',passed:reports.every(report=>report.issues.numErrors===0),files:reports},null,2));
