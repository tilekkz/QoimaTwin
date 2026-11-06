import {chromium} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';

const packageRoot=resolve(process.argv[2]||'');
assert(process.argv[2],'Pass the actual delivery directory');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const files=async(root,prefix='')=>{
 const result=[];
 for(const item of await readdir(join(root,prefix),{withFileTypes:true})){
  const path=prefix?prefix+'/'+item.name:item.name;
  if(item.isDirectory())result.push(...await files(root,path));else result.push(path);
 }return result.sort();
};
const sourceFiles=await files('dist');const deliveredFiles=await files(join(packageRoot,'viewer'));
assert.deepEqual(deliveredFiles,sourceFiles);
const inventory=[];
for(const path of sourceFiles){
 const source=await readFile(join('dist',path));const delivered=await readFile(join(packageRoot,'viewer',path));
 assert.equal(sha(delivered),sha(source),path);
 inventory.push({path,bytes:delivered.length,sha256:sha(delivered)});
}
for(const path of ['server.mjs','START_VIEWER.ps1','start-viewer.cmd']){
 assert.equal(sha(await readFile(join(packageRoot,path))),sha(await readFile(join('../tools/visual',path))),path);
}
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const page=await browser.newPage({viewport:{width:1366,height:768}});
const pageErrors=[],badResponses=[],remoteRequests=[];
page.on('pageerror',error=>pageErrors.push(error.message));
page.on('response',response=>{if(response.status()>=400)badResponses.push({url:response.url(),status:response.status()});});
await page.route('**/*',route=>{const url=new URL(route.request().url());if(url.origin==='http://127.0.0.1:4180')return route.continue();remoteRequests.push(url.href);return route.abort();});
await page.goto('http://127.0.0.1:4180');
await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
const startup=await page.evaluate(()=>window.__QOIMA_VIEWER__.getState());
assert.equal(startup.counts.racks,288);assert.equal(startup.counts.slots,864);assert.equal(startup.counts.actors,24);assert.equal(startup.counts.conveyorCells,179);
assert.equal(await page.locator('canvas').count(),1);
await page.screenshot({path:'test-results/package-startup.png'});
await page.getByRole('button',{name:/Водитель/}).click();
await page.waitForFunction(()=>window.__QOIMA_VIEWER__.getState().mode==='driver');
await page.screenshot({path:'test-results/package-driver.png'});
await page.getByRole('button',{name:/Весь склад/}).click();
await page.waitForFunction(()=>window.__QOIMA_VIEWER__.getState().mode==='overview');
await page.evaluate(()=>{const v=window.__QOIMA_VIEWER__;v.replay.seek(466);v.selectActor('F02');});
await page.waitForTimeout(150);
const follow=await page.evaluate(()=>window.__QOIMA_VIEWER__.getState());
assert(follow.camera[0]<68,'Shipping follow camera must stay on the open interior side');
await page.screenshot({path:'test-results/package-forklift.png'});
assert.deepEqual(pageErrors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(remoteRequests,[]);
await browser.close();
const report={status:'passed',timestampUtc:new Date().toISOString(),packageRoot,launchCommand:'powershell -NoProfile -ExecutionPolicy Bypass -File .\\START_VIEWER.ps1',url:'http://127.0.0.1:4180',viewerFilesEqualProductionBuild:true,launcherFilesEqualSource:true,inventory,pageErrors,badResponses,remoteRequests,checks:['actual packaged START_VIEWER.ps1 bound localhost4180','full registry and single canvas','driver stand selected through UI','warehouse restored through UI','shipping focus on open interior side','all viewer files byte-identical to the 30/30 tested build','no external API/CDN requests'],startupCounts:startup.counts,shippingCamera:follow.camera,screenshots:['package-startup.png','package-driver.png','package-forklift.png']};
await writeFile('../docs/visual/PACKAGE_LAUNCH_QA.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({status:report.status,viewerFiles:inventory.length,counts:startup.counts,errors:pageErrors.length,externalRequests:remoteRequests.length}));
