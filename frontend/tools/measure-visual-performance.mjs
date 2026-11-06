import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
const url=process.env.QOIMA_TEST_URL||'http://127.0.0.1:4173';
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1366,height:768},deviceScaleFactor:1});
await page.goto(url);await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
await page.evaluate(()=>{window.__QOIMA_VIEWER__.setQuality('low');window.__QOIMA_VIEWER__.audio.setMuted(true);});
const device=await page.evaluate(()=>{
 const canvas=document.querySelector('canvas');const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');const ext=gl?.getExtension('WEBGL_debug_renderer_info');
 return{userAgent:navigator.userAgent,cores:navigator.hardwareConcurrency,deviceMemoryGB:navigator.deviceMemory||null,renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'unavailable',vendor:ext?gl.getParameter(ext.UNMASKED_VENDOR_WEBGL):'unavailable',viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,loadedBuildAssets:performance.getEntriesByType('resource').map(item=>new URL(item.name).pathname).filter(path=>path.endsWith('.js')).sort()};
});
const reports=[];
for(const mode of ['overview','hero']){
 await page.evaluate(mode=>{const v=window.__QOIMA_VIEWER__;v.overview();v.replay.reset();v.replay.setSpeed(10);if(mode==='hero')v.selectActor('P01');v.replay.play();},mode);
 await page.waitForTimeout(1500);
 console.log('MEASURE_START '+mode);
 const result=await page.evaluate(async()=>{
  const frames=[];const stats=[];let resets=0;const start=performance.now();let previous=start;
  return await new Promise(resolve=>{
   function sample(now){const viewer=window.__QOIMA_VIEWER__;const clock=viewer.replay.getState();if(!clock.playing&&clock.time>=clock.duration){viewer.replay.reset();viewer.replay.play();resets++;}frames.push(now-previous);previous=now;const v=window.__QOIMA_VIEWER__;if(frames.length%30===0)stats.push(v.getPerfState());
    if(now-start>=60000){
      frames.sort((a,b)=>a-b);const quantile=p=>frames[Math.floor((frames.length-1)*p)];
      const memory=performance.memory?{usedJSHeapSize:performance.memory.usedJSHeapSize,totalJSHeapSize:performance.memory.totalJSHeapSize,jsHeapSizeLimit:performance.memory.jsHeapSizeLimit}:null;
      resolve({elapsedMs:now-start,resets,frameCount:frames.length,medianFps:1000/quantile(.5),p95FrameMs:quantile(.95),meanFps:frames.length*1000/(now-start),maxCalls:Math.max(...stats.map(s=>s.calls)),maxTriangles:Math.max(...stats.map(s=>s.triangles)),samples:stats,memory});
    }else requestAnimationFrame(sample);
   }requestAnimationFrame(sample);
  });
 });
 reports.push({mode,...result});console.log(JSON.stringify({mode,medianFps:result.medianFps,p95FrameMs:result.p95FrameMs,maxCalls:result.maxCalls,maxTriangles:result.maxTriangles}));
 await page.screenshot({path:`test-results/performance-${mode}.png`});
}
await mkdir('../docs/visual',{recursive:true});
await writeFile('../docs/visual/PERFORMANCE.json',JSON.stringify({timestampUtc:new Date().toISOString(),source:'500s synthetic visual fixture repeated in one full-scale warehouse; no DES/throughput result',conditions:{device,quality:'low',headless:true,measurement:'two 60s rAF sampling windows; overview and follow P01; speed10x; mute; no simultaneous Blender renderer',framesIncludeWarmup:false},reports},null,2));
await browser.close();
