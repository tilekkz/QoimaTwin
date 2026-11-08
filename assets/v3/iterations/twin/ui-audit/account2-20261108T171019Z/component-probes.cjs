// CPU-only WHITE_BOX / COMPONENT_ONLY. No DOM/browser, WebGL renderer or asset loading.
// Run from any directory: node <this-file>. Only probe-results.json is written beside this file.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript/lib/typescript.js'));
const source = name => fs.readFileSync(path.join(root, 'frontend/src/adaptive-v3/twin', name + '.ts'), 'utf8');
const files = Object.fromEntries(['twinRender','twinPage','twinScenario'].map(n => [n, ts.createSourceFile(n+'.ts', source(n), ts.ScriptTarget.Latest, true)]));
function find(file, predicate) { let result; function walk(node) { if (!result && predicate(node)) result=node; if (!result) ts.forEachChild(node, walk); } walk(files[file]); assert.ok(result, 'source node exists'); return result; }
const fn = (file, name) => find(file, n => ts.isFunctionDeclaration(n) && n.name?.text===name).getText(files[file]);
function handler(file, target, event) { const n=find(file,n=>ts.isCallExpression(n)&&n.expression.getText(files[file])===target+'.addEventListener'&&n.arguments[0]?.text===event); return n.arguments[1].getText(files[file]); }
const compile = text => ts.transpileModule(text,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const make = globals => vm.createContext({...globals});
const install = (ctx, file, names) => vm.runInContext(compile(names.map(n=>fn(file,n)).join('\n')),ctx);
const scenarioContext=make({exports:{}}); vm.runInContext(compile(source('twinScenario')),scenarioContext); const scenario=scenarioContext.exports;
function el() { return {dataset:{},style:{},children:[],attributes:{},hidden:false,offsetWidth:60,classList:{toggle(){},remove(){},add(){}},setAttribute(k,v){this.attributes[k]=v;},toggleAttribute(){},animate(){},querySelector(){return el();}}; }
const results=[];
function record(id, observation, scope='WHITE_BOX COMPONENT_ONLY') { results.push({id,scope,...observation}); }

// Exact domFor private helper + exact installed bubble click callback; scenario functions are real.
{
 const b=el(),clicks=[],p={variant:'B',vp:{x:0,y:0,w:1000,h:600},sc:{x:0,y:0,w:1000,h:600},gray:false};
 const ctx=make({...scenario,b,onBubble:id=>clicks.push(id),t:34,mode:'overlay',effects:'full',budget:6,selectedActor:null,selected:null,moves:[],spots:[{actor_id:'W1',zone_id:'PACKING_LIGHT_LINE'}],heads:new Map([['W1',{}]]),layers:{B:el()},labels:{B:el()},labelW:{},corners:{B:[el(),el(),el(),el()]},badges:{B:new Map()},pins:{B:[]},bubbles:{B:[b]},rings:{B:el()},BUBBLE_MIN_PX_PER_M:3.5,BUBBLE_ICON:{wait:'wait'},BUBBLE_RU:{wait:'Wait'},ctx:{camera:{zoom:1,left:-50,right:50}},project:()=>({x:100,y:100}),inside:(q,r)=>q.x>=r.x&&q.x<=r.x+r.w&&q.y>=r.y&&q.y<=r.y+r.h,reducedMotion:()=>true});
 install(ctx,'twinRender',['domFor']); const click=vm.runInContext('('+handler('twinRender','b','click')+')',ctx);
 ctx.domFor(p,1000,600); click(); const initial={hidden:b.hidden,actor:b.dataset.actor,key:b.dataset.key,label:b.attributes['aria-label'],clicks:clicks.length};
 ctx.budget=0;ctx.effects='off';ctx.domFor(p,1000,600);const hidden={hidden:b.hidden,actor:b.dataset.actor??null,key:b.dataset.key};
 ctx.budget=6;ctx.effects='full';ctx.domFor(p,1000,600);click();const restored={hidden:b.hidden,actor:b.dataset.actor??null,key:b.dataset.key,clicks:clicks.length};
 assert.equal(initial.actor,'W1');assert.equal(hidden.actor,null);assert.equal(restored.hidden,false);assert.equal(restored.actor,null);assert.equal(restored.clicks,initial.clicks);
 record('bubble-reappearance',{product_failure_reproduced:true,initial,hidden,restored,stub_dependencies:['one fake worker W1 in PACKING_LIGHT_LINE','plain-object DOM controls','projection/on-screen and camera scale stubs; no renderer']});
 ctx.t=48;ctx.domFor(p,1000,600); const expected=scenario.reactionsAt('B',48,ctx.spots)[0].text;assert.notEqual(b.attributes['aria-label'],'W1: '+expected);
 record('bubble-cause-cache',{product_failure_reproduced:true,actual_label:b.attributes['aria-label'],expected_label:'W1: '+expected,dependency:'same private-helper context; real B events at 30 and 46 seconds'});
}
{
 const ctx=make({mode:'side',split:.5,SIDE_ZOOM:.72});install(ctx,'twinRender',['passes']);const layouts=[];
 for(const [W,H] of [[1200,700],[600,900]])for(const mode of ['side','swipe','overlay','diff']){ctx.mode=mode;const p=ctx.passes(W,H);assert.equal(p.length,mode==='side'||mode==='swipe'?2:1);if(p.length===2){assert.equal(p[0].variant,'A');assert.equal(p[1].variant,'B');assert.equal(p[0].vp.w,p[1].vp.w);assert.equal(p[0].vp.h,p[1].vp.h);assert.equal(p[0].zoom,p[1].zoom);}else{assert.equal(p[0].variant,'B');assert.equal(p[0].gray,mode==='diff');}layouts.push({W,H,mode,passes:p});}
 record('four-mode-routing',{assertions_passed:true,layouts,limitation:'Pure pass-layout function only; no pixels, draw loop, camera hardware or public bootstrap executed.'});
}
{
 const state={},present=el(),app=el(),ctx=make({PRESENTER_STEPS:scenario.PRESENTER_STEPS,phase:'ready',stepIndex:-1,app,present,pStep:el(),pDots:{children:scenario.PRESENTER_STEPS.map(el)},pTitle:el(),pText:el(),pPrev:el(),pNext:el(),phone:{matches:false},show:(e,open)=>e.dataset.open=String(open),setPop(){},select:id=>state.selection=id,setPlaying:v=>state.playing=v,seek:v=>state.t=v,setMode:v=>state.mode=v,setSheet:v=>state.sheet=v,fly:(target,span)=>state.focus={target,span},MODES:['side','swipe','overlay','diff'],sheet:null,nav:null});
 install(ctx,'twinPage',['goStep','endPresent']);const keyboard=vm.runInContext(compile('('+handler('twinPage','document','keydown')+')'),ctx),next=vm.runInContext(compile('('+handler('twinPage','pNext','click')+')'),ctx);
 let restored=0;for(const i of [0,1,2,3,4,5,6,7,6,5,4,3,2,1,0,0]){ctx.goStep(i);assert.equal(state.t,scenario.PRESENTER_STEPS[i].t);assert.equal(state.mode,scenario.PRESENTER_STEPS[i].mode);assert.equal(state.focus.span,scenario.PRESENTER_STEPS[i].focus.span);assert.equal(state.selection,null);restored++;}
 ctx.goStep(7);keyboard({key:'PageDown',target:{closest:()=>false},preventDefault(){}});const afterKeyboard={stepIndex:ctx.stepIndex,open:present.dataset.open,nextLabel:ctx.pNext.textContent};next();const afterButton={stepIndex:ctx.stepIndex,open:present.dataset.open};assert.equal(afterKeyboard.stepIndex,7);assert.equal(afterKeyboard.open,'true');assert.equal(afterButton.stepIndex,-1);assert.equal(afterButton.open,'false');
 record('presenter-boundaries',{restored_steps_checked:restored,product_failure_reproduced:true,afterKeyboard,afterButton,stub_dependencies:['UI elements','setPlaying/seek/setMode/setSheet/select/fly state-recording stubs; no camera animation'],limitation:'Real goStep/endPresent and installed keyboard/next callbacks executed; downstream helpers stubbed.'});
 let invalid;try{ctx.goStep(NaN);}catch(e){invalid=e.name;}assert.equal(invalid,'TypeError');record('presenter-private-invalid-index',{input:'NaN',observed:invalid,finding:false,limitation:'Private debug API boundary only; no normal UI input producing NaN was identified.'});
}

// Exact page load/disposeAll/setPhase functions, with deferred scene and source-reader stubs.
function lifecycle(deferred=false){
 const tws=[],scenes=[],waiters=[],panel={open:true,content:'Previously selected HU1'},data={fixture:{inputs:{initial_stock:[],requests:[]}},registry:{workers:[]}},host=el();
 const scene=()=>({disposed:0,dispose(){this.disposed++;},applyCargoBindings(){return{ok:false};},getCargoBindings(){return[];},resetCargoBindings(){},setView(){}});
 const oldScene=scene(),oldTwin={selected:'HU1',dispose(){this.disposed=true;}},ctx=make({serial:0,controller:undefined,phase:'ready',nav:{dispose(){}},raf:0,flyRaf:0,flyTarget:null,switchTimer:0,host,twin:oldTwin,scene:oldScene,bundle:data,moves:[],nowKey:'',selectedId:'HU1',selectedKind:'HU',panel,app:el(),status:el(),retry:el(),AbortController,WAREHOUSE_BASE_FILES:{fixture:'fake-fixture'},readLocal:async()=>'',adaptWarehouseV3:async()=>data,WarehouseAdapterError:class extends Error{},layer:el(),reduced:{matches:false},createTwinRenderer(){const tw={selected:null,disposed:false,dispose(){this.disposed=true;},onBubble(){},capture(){},setMoves(){},setReady(){}};tws.push(tw);return tw;},createWarehouseScene(){const sc=scene();scenes.push(sc);return deferred?new Promise((resolve,reject)=>waiters.push({resolve:()=>resolve(sc),reject})):Promise.resolve(sc);},outboundCandidates:()=>[],createNavigation:()=>({dispose(){}}),tapAt(){},homeShown(){},cancelAnimationFrame(){},clearTimeout,setTimeout,setMode(){},mode:'side',setSplit(){},split:.5,renderMoves(){},applyEffects(){},seek(){},t:34,setPlaying(){},playing:false,URL,location:{href:'https://component.invalid/twin-v3.html'},goStep(){},select(){}});
 install(ctx,'twinPage',['disposeAll','setPhase','load']);return{ctx,tws,scenes,waiters,panel,oldScene,oldTwin};
}
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
(async()=>{
 const a=lifecycle();await a.ctx.load();assert.equal(a.ctx.phase,'ready');assert.equal(a.ctx.selectedId,'HU1');assert.equal(a.ctx.twin.selected,null);assert.equal(a.panel.open,true);record('reload-selection-retention',{product_failure_reproduced:true,page_selected_id:a.ctx.selectedId,new_twin_selected_id:a.ctx.twin.selected,prior_card:a.panel,old_scene_disposals:a.oldScene.disposed,stub_dependencies:['source fetch/adapter returning empty synthetic data','synthetic scene and twin objects; no renderer or admission','UI update helpers stubbed'],limitation:'Lifecycle helper does not reset or rebuild the pre-existing card; actual browser rendering not executed.'});
 const b=lifecycle(true),first=b.ctx.load();await flush();assert.equal(b.waiters.length,1);const second=b.ctx.load();await flush();assert.equal(b.waiters.length,2);b.waiters[1].resolve();await second;b.waiters[0].resolve();await first;assert.equal(b.ctx.scene,b.scenes[1]);assert.equal(b.scenes[0].disposed,1);assert.equal(b.tws[0].disposed,true);assert.equal(b.tws[1].disposed,false);record('latest-request-late-resolution',{assertions_passed:true,latest_scene_retained:true,stale_scene_disposals:b.scenes[0].disposed,stale_twin_disposed:b.tws[0].disposed,scope:'COMPONENT_ONLY actual load/dispose helpers with deferred scene/source-reader stubs'});
 const c=lifecycle(true),pending=c.ctx.load();await flush();c.ctx.serial++;c.ctx.controller.abort();c.ctx.disposeAll();c.ctx.setPhase('disposed','Stopped');c.waiters[0].resolve();await pending;assert.equal(c.ctx.phase,'disposed');assert.equal(c.ctx.scene,undefined);assert.equal(c.scenes[0].disposed,1);record('pagehide-late-resolution',{assertions_passed:true,phase:c.ctx.phase,stale_scene_disposals:c.scenes[0].disposed,limitation:'Same serial/abort/dispose/setPhase sequence as the pagehide callback; browser event delivery not executed.'});
 const d=lifecycle(true),failed=d.ctx.load();await flush();d.waiters[0].reject(Error('synthetic scene failure'));await failed;assert.equal(d.ctx.phase,'error');assert.equal(d.ctx.twin,undefined);assert.equal(d.tws[0].disposed,true);record('current-load-error-ownership',{assertions_passed:true,phase:d.ctx.phase,twin_disposed:d.tws[0].disposed,limitation:'Synthetic scene rejection; no actual resource load failure.'});
 const output={status:'completed',executed_at:new Date().toISOString(),scope:'CPU-only WHITE_BOX / COMPONENT_ONLY exact TypeScript AST extraction; no source changes, actual renderer, native scene, assets, browser or audio hardware',results};
 fs.writeFileSync(path.join(__dirname,'probe-results.json'),JSON.stringify(output,null,2)+'\n');console.log(JSON.stringify({status:output.status,checks:results.length,reproduced_product_failures:results.filter(r=>r.product_failure_reproduced).map(r=>r.id)}));
})().catch(e=>{console.error(e);process.exitCode=1;});
