import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
const out='../assets/v3/qa-browser/environment-shell-close';await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],failedResources=[],frames=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
page.on('response',r=>{if(r.status()>=400)failedResources.push({url:r.url(),status:r.status()});});
try{
 await page.goto('http://127.0.0.1:4173/stand-v3.html?asset=environment-shell');await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
 const before=await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());
 for(const port of ['IN_W_BULK','OUT_S_EXPRESS']){
  await page.evaluate(port=>window.__QOIMA_STAND_V3__.focus('GATE__'+port,'quarter'),port);
  await page.evaluate(async()=>{for(let n=0;n<5;n++)await new Promise(requestAnimationFrame);});
  const state=await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());
  for(const field of ['dimensions_m','bounds_m','anchors','triangles'])if(state[field]===undefined||JSON.stringify(state[field])!==JSON.stringify(before[field]))throw Error('Focus changed geometry '+field);
  const screenshot=`${out}/${port}.png`;await page.screenshot({path:screenshot});frames.push({port,screenshot,state});
 }
 if(errors.length||failedResources.length)throw Error(JSON.stringify({errors,failedResources}));
 await writeFile(`${out}/browser-capture.json`,JSON.stringify({errors,failedResources,browser:await browser.version(),frames,geometry_unchanged:true},null,2));
 console.log(JSON.stringify({captures:frames.length,errors:0,failedResources:0,geometry_unchanged:true}));
}finally{await browser.close();}
