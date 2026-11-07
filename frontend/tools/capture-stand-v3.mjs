import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
const asset=process.argv[2]||'calibration';if(!/^[a-z0-9][a-z0-9-]{0,63}$/.test(asset))throw Error('Invalid asset ID');
const base=process.env.QOIMA_STAND_BASE_URL||'http://127.0.0.1:4173';
const out=process.env.QOIMA_STAND_OUTPUT||`../assets/v3/qa-browser/${asset}`;await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const errors=[];const frames=[];const failedResources=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('response',r=>{if(r.status()>=400)failedResources.push({url:r.url(),status:r.status()});});
try{
 await page.goto(`${base}/stand-v3.html?asset=${asset}`);await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
 for(const view of ['front','side','rear','quarter']){
  await page.evaluate(view=>window.__QOIMA_STAND_V3__.view(view),view);
  await page.evaluate(async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r));});
  await page.screenshot({path:`${out}/${view}.png`});
  frames.push({view,screenshot:`${out}/${view}.png`,state:await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot())});
 }
 await writeFile(`${out}/browser-capture.json`,JSON.stringify({at:new Date().toISOString(),browser:await browser.version(),url:page.url(),viewport:{width:1440,height:1000},errors,failedResources,frames},null,2));
 if(errors.length)throw Error(errors.join('\n'));console.log(JSON.stringify({asset,captures:4,errors:0,out}));
}catch(error){await writeFile(`${out}/failure.json`,JSON.stringify({error:String(error),errors,failedResources,status:await page.locator('#status-copy').textContent().catch(()=>null)},null,2));throw error;}finally{await browser.close();}
