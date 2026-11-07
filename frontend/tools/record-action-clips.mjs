import {chromium} from '@playwright/test';
import {mkdir,writeFile,copyFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const directory=resolve('../work/night-video/action-clips');
await mkdir(directory,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const clips=[
 {name:'pick-contact',actor:'P01',operation:'pick',speed:1,pad:.2},
 {name:'tote-handoff',actor:'P01',operation:'handoff',speed:1,pad:.3},
 {name:'packing-flaps',actor:'K01',operation:'pack',speed:1,pad:.2},
 {name:'forklift-load',actor:'F02',operation:'loading',speed:1,pad:.4},
 {name:'parcel-scan',actor:'S01',operation:'scan',speed:1,pad:.2},
];
const evidence=[];
for(const clip of clips){
 const context=await browser.newContext({viewport:{width:1366,height:768},deviceScaleFactor:1,recordVideo:{dir:directory,size:{width:1366,height:768}}});
 const began=Date.now();const page=await context.newPage();const video=page.video();
 await page.goto(process.env.QOIMA_TEST_URL||'http://127.0.0.1:4180');
 await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
 const span=await page.evaluate(clip=>{
  const v=window.__QOIMA_VIEWER__;v.audio.setMuted(true);v.setQuality('high');
  const action=v.replay.getRun().actions.find(a=>a.actor_id===clip.actor&&a.operation===clip.operation);
  if(!action)throw new Error('Action not found: '+clip.name);
  const start=Math.max(0,action.start_s-clip.pad),end=action.end_s+clip.pad;
  v.replay.seek(start);v.selectActor(clip.actor);v.replay.setSpeed(clip.speed);
  return{start,end,actionId:action.action_id};
 },clip);
 await page.waitForTimeout(400);
 const readyOffset=(Date.now()-began)/1000;
 const duration=(span.end-span.start)/clip.speed;
 console.log('ACTION_CLIP '+clip.name+' '+duration.toFixed(2)+'s');
 await page.evaluate(()=>window.__QOIMA_VIEWER__.replay.play());
 await page.waitForTimeout(duration*1000);
 await page.evaluate(()=>window.__QOIMA_VIEWER__.replay.pause());
 await page.screenshot({path:resolve(directory,clip.name+'.png')});
 await context.close();
 await copyFile(await video.path(),resolve(directory,clip.name+'.webm'));
 evidence.push({...clip,...span,duration,readyOffset,source:'actual viewer recording; synthetic VISUAL DEMO; muted'});
}
await browser.close();
await writeFile(resolve(directory,'clips.json'),JSON.stringify(evidence,null,2));
