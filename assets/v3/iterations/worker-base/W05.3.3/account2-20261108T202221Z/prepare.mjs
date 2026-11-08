import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const output=path.dirname(fileURLToPath(import.meta.url));
const repo='C:/Users/izbas/Documents/Codex/2026-11-06/new-chat/work/QoimaTwin',front=path.join(repo,'frontend');
const sha=b=>createHash('sha256').update(b).digest('hex');
const loadedPath='frontend/src/adaptive-v3/warehouseLoadedWalkCalibration.ts',checkerPath='frontend/tools/check-warehouse-loaded-walk-calibration-v3.mjs';
const source=await readFile(path.join(repo,loadedPath),'utf8'),helper=await readFile(path.join(output,'loaded-leg-solver.ts'),'utf8');
if(!source.includes('const next=gait.sample(seconds)'))throw Error('Loaded source changed: expected sample site absent');
const candidate=source.replace('/** Prescribed pre-held calibration only;',helper+'\n/** Prescribed pre-held calibration only;').replace('const next=gait.sample(seconds)','const next=solveLoadedLegs(rig!,gait.sample(seconds))');
await writeFile(path.join(output,'warehouseLoadedWalkCalibration.candidate.ts'),candidate);
const productionPaths=[loadedPath,'frontend/src/adaptive-v3/warehouseWorkerGait.ts',checkerPath,'docs/adaptive-v3/evidence/W05.3.3-checks.json','docs/adaptive-v3/evidence/W05.3.1-checks.json','docs/adaptive-v3/evidence/W05.3.4-checks.json','frontend/public/data/v3/worker-base-carry-pose.json','frontend/public/models/v3/worker-base.glb','frontend/public/models/v3/small-carton.glb'];
const production_hashes={};for(const p of productionPaths)production_hashes[p]=sha(await readFile(path.join(repo,p)));
const provenance={production_hashes,candidate_path:path.join(output,'warehouseLoadedWalkCalibration.candidate.ts'),candidate_sha256:sha(candidate),helper_sha256:sha(helper),injection:'Only warehouseLoadedWalkCalibration source text replaced before transpile. Pure gait and native gate unchanged.'};
await writeFile(path.join(output,'source-hashes.json'),JSON.stringify(provenance,null,2)+'\n');
let checker=await readFile(path.join(repo,checkerPath),'utf8');
checker=checker.replace("const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),cache=path.join(repo,'work/v3/loaded-walk-calibration-check'),reportPath=path.join(repo,'docs/adaptive-v3/evidence/W05.3.3-checks.json');",`const front=${JSON.stringify(front)},repo=${JSON.stringify(repo)},cache=${JSON.stringify(path.join(output,'cache'))},reportPath=${JSON.stringify(path.join(output,'candidate-checks.json'))};\nconst candidateProvenance=JSON.parse(await readFile(${JSON.stringify(path.join(output,'source-hashes.json'))},'utf8'));`);
checker=checker.replace("import ts from 'typescript';",`import ts from ${JSON.stringify(pathToFileURL(path.join(front,'node_modules/typescript/lib/typescript.js')).href)};`)
 .replace("import * as T from 'three';",`import * as T from ${JSON.stringify(pathToFileURL(path.join(front,'node_modules/three/build/three.module.js')).href)};`)
 .replace("import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';",`import {GLTFLoader} from ${JSON.stringify(pathToFileURL(path.join(front,'node_modules/three/examples/jsm/loaders/GLTFLoader.js')).href)};`);
checker=checker.replace("let code=ts.transpileModule((await source('frontend/src/adaptive-v3/'+name+'.ts')).toString(),",`const originalModule=(await source('frontend/src/adaptive-v3/'+name+'.ts')).toString();const candidateModule=name==='warehouseLoadedWalkCalibration'?await readFile(candidateProvenance.candidate_path,'utf8'):originalModule;if(name==='warehouseLoadedWalkCalibration')assert.equal(sha(candidateModule),candidateProvenance.candidate_sha256);let code=ts.transpileModule(candidateModule,`);
checker=checker.replace("const report={schema_id:","const report={candidate_provenance:candidateProvenance,schema_id:");
await writeFile(path.join(output,'probe.mjs'),checker);
console.log(JSON.stringify(provenance,null,2));
