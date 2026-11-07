import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
const dir='../work/visual-polish/browser-first';await mkdir(dir,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.goto('http://127.0.0.1:4180');await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
const frames=async()=>page.evaluate(async()=>{for(let i=0;i<4;i++)await new Promise(r=>requestAnimationFrame(r));});
for(const id of (process.argv.includes('--actions-only')?[]:['standing-worker','picker-worker','driver','picking-cart','forklift','crate','rack-high','order-tote'])){await page.locator(`[data-asset="${id}"]`).click();await page.evaluate(()=>window.__QOIMA_VIEWER__.inspect('quarter'));await frames();await page.screenshot({path:dir+'/'+id+'.png'});}
await page.getByRole('button',{name:/Весь склад/}).click();await frames();await page.screenshot({path:dir+'/overview.png'});
for(const [id,t] of [['P01',6.4],['T001',40],['K01',68],['F02',467]]){await page.evaluate(({id,t})=>{const v=window.__QOIMA_VIEWER__;v.replay.seek(t);v.selectActor(id);},{id,t});await frames();await page.screenshot({path:dir+'/'+id+'-action.png'});}
await writeFile(dir+'/errors.json',JSON.stringify(errors,null,2));await browser.close();if(errors.length)throw new Error(errors.join('\n'));console.log('POLISH_FIRST_PREVIEWS '+dir);


