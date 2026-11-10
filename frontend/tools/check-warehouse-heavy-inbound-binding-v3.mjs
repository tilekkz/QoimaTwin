import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import ts from 'typescript';

const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),output=path.join(repo,'work/v3/heavy-inbound-binding-20261109');
await mkdir(output,{recursive:true});
const pins={},sha=b=>createHash('sha256').update(b).digest('hex');
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter','warehouseHeavyInboundBinding']){
 const relative='frontend/src/adaptive-v3/'+name+'.ts',bytes=await readFile(path.join(repo,relative));pins[relative]=sha(bytes);
 const code=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '\.\/(\w+)'/g,"from './$1.mjs'");
 await writeFile(path.join(output,name+'.mjs'),code);
}
const {WAREHOUSE_BASE_FILES}=await import(pathToFileURL(path.join(output,'warehouseAdapter.mjs'))),{verifyWarehouseHeavyInboundSources}=await import(pathToFileURL(path.join(output,'warehouseHeavyInboundBinding.mjs')));
const texts={};
for(const [key,url] of Object.entries(WAREHOUSE_BASE_FILES)){const relative='frontend/public'+url,bytes=await readFile(path.join(repo,relative));texts[key]=bytes.toString();pins[relative]=sha(bytes);}
const relative='frontend/public/data/v3/heavy-inbound-fixture.json',bytes=await readFile(path.join(repo,relative)),fixtureText=bytes.toString();pins[relative]=sha(bytes);
assert.equal((await verifyWarehouseHeavyInboundSources(texts,fixtureText)).fixture_id,JSON.parse(fixtureText).fixture_id);
await assert.rejects(()=>verifyWarehouseHeavyInboundSources(texts,fixtureText+' '),/INBOUND_FIXTURE_HASH_MISMATCH/);
for(const key of Object.keys(texts))await assert.rejects(()=>verifyWarehouseHeavyInboundSources({...texts,[key]:texts[key]+' '},fixtureText),/INBOUND_SOURCE_HASH_MISMATCH/);
const report={passed:true,positive_controls:1,negative_controls:5,scope:'exact UTF-8 episode and four adapted source texts',source_hashes:pins};
await writeFile(path.join(output,'checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:true,positive_controls:1,negative_controls:5}));
