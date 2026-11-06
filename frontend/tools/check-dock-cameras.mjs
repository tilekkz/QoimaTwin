import {chromium} from '@playwright/test';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const page=await browser.newPage({viewport:{width:1366,height:768}});
await page.goto('http://127.0.0.1:4180');await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
for(const [id,start,end] of [['F01',100,108],['F02',450,466]]){
 await page.evaluate(({id,start})=>{const v=window.__QOIMA_VIEWER__;v.replay.seek(start);v.selectActor(id);v.replay.setSpeed(10);v.replay.play();},{id,start});
 await page.waitForFunction(end=>window.__QOIMA_VIEWER__.replay.getState().time>=end,end);
 await page.evaluate(()=>window.__QOIMA_VIEWER__.replay.pause());await page.screenshot({path:`test-results/${id}-safe-camera.png`});
 console.log(JSON.stringify(await page.evaluate(()=>{const s=window.__QOIMA_VIEWER__.getState();return{time:s.replay.time,camera:s.camera,target:s.target};})));
}
await browser.close();
