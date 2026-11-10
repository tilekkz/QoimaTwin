/* COMPONENT_ONLY CPU regression for exact Twin bubble DOM logic.
 * Run from any directory: node frontend/tools/check-twin-bubbles-v3.cjs [--check-only]
 * AST-extracts the real private domFor helper and bubble-pool creation/listeners;
 * uses the real scenario functions with synthetic worker spots and DOM/projection stubs.
 * No renderer, assets, browser, public bootstrap, native admission or 530-HU claim.
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),args=process.argv.slice(2),checkOnly=args.includes('--check-only');
if(args.some(arg=>arg!=='--check-only'))throw Error('UNKNOWN_ARGUMENT');
const ts=require(path.join(root,'frontend/node_modules/typescript/lib/typescript.js'));
const checkerPath='frontend/tools/check-twin-bubbles-v3.cjs',renderPath='frontend/src/adaptive-v3/twin/twinRender.ts',scenarioPath='frontend/src/adaptive-v3/twin/twinScenario.ts',evidencePath='docs/adaptive-v3/evidence/twin-bubbles-checks.json';
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const renderBytes=fs.readFileSync(path.join(root,renderPath)),scenarioBytes=fs.readFileSync(path.join(root,scenarioPath));
const render=renderBytes.toString('utf8'),scenarioSource=scenarioBytes.toString('utf8'),ast=ts.createSourceFile(renderPath,render,ts.ScriptTarget.Latest,true);
function find(predicate){let result;function walk(node){if(!result&&predicate(node))result=node;if(!result)ts.forEachChild(node,walk);}walk(ast);assert.ok(result,'Exact production source node exists');return result;}
const domNode=find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='domFor');
const poolNode=find(node=>ts.isBinaryExpression(node)&&node.operatorToken.kind===ts.SyntaxKind.EqualsToken&&node.left.getText(ast)==='bubbles[v]');
const declaration=name=>find(node=>ts.isVariableDeclaration(node)&&node.name.getText(ast)===name).getText(ast);
const transpile=text=>ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scenarioContext=vm.createContext({exports:{}});vm.runInContext(transpile(scenarioSource),scenarioContext,{filename:scenarioPath});const scenario=scenarioContext.exports;
class Element{
 constructor(){this.dataset={};this.style={};this.children=[];this.attributes={};this.hidden=false;this.offsetWidth=60;this.offsetHeight=24;this.title='';this.htmlWrites=0;this.animations=0;this.listeners=new Map();this.classList={toggle(){},remove(){},add(){}};}
 append(node){this.children.push(node);}setAttribute(key,value){this.attributes[key]=value;}getAttribute(key){return this.attributes[key]??null;}
 set innerHTML(value){this.html=value;this.htmlWrites++;}get innerHTML(){return this.html;}
 addEventListener(type,fn){this.listeners.set(type,[...(this.listeners.get(type)??[]),fn]);}fire(type){for(const fn of this.listeners.get(type)??[])fn();}
 animate(){this.animations++;}querySelector(){return new Element();}toggleAttribute(){}
}
const pass=variant=>({variant,vp:{x:0,y:0,w:1000,h:600},sc:{x:0,y:0,w:1000,h:600},gray:false});
function setup({variant='B',ids=['K01'],phone=false,reduced=false}={}){
 const clicks=[],layer=new Element(),layers={A:new Element(),B:new Element()},bubbles={A:[],B:[]};
 const state=vm.createContext({...scenario,document:{createElement:()=>new Element()},onBubble:id=>clicks.push(id),v:variant,el:layer,bubbles,layers,labels:{A:new Element(),B:new Element()},labelW:{},corners:{A:[],B:[]},badges:{A:new Map(),B:new Map()},pins:{A:[],B:[]},rings:{A:new Element(),B:new Element()},moves:[],selected:null,selectedActor:null,t:34,mode:'overlay',effects:'full',budget:scenario.bubbleBudget('full',phone),spots:[],heads:new Map(),ctx:{camera:{zoom:1,left:-50,right:50}},projection:{inside:true},project:()=>state.projection.inside?{x:100,y:100}:{x:1200,y:100},inside:(q,r)=>q.x>=r.x&&q.x<=r.x+r.w&&q.y>=r.y&&q.y<=r.y+r.h,reducedMotion:()=>reduced,THREE:{Vector3:class{}}});
 vm.runInContext(transpile(['const '+declaration('BUDGET_MAX')+';','const '+declaration('BUBBLE_MIN_PX_PER_M')+';','const '+declaration('BUBBLE_ICON')+';',poolNode.getText(ast)+';',domNode.getText(ast)].join('\n')),state,{filename:renderPath});
 Object.assign(state,{
  labelH:{},operationFocus:false,region:()=>({x:0,y:0,w:1000,h:600}),
  gateEls:{A:[],B:[]},gateTags:[],motion:undefined,
  carrierIndicators:{A:{update(){}},B:{update(){}}},
  stationIndicators:{A:{update(){}},B:{update(){}}},
  variantWorkers:()=>state.spots,variantHead:id=>state.heads.get(id)??null,focusPose:()=>null});
 const current=pass(variant);
 function workers(next){state.spots=next.map(actor_id=>({actor_id,zone_id:'PACKING_LIGHT_LINE'}));state.heads=new Map(next.map(id=>[id,{}]));}
 workers(ids);
 return{state,clicks,buttons:bubbles[variant],pass:current,workers,draw(){state.domFor(current,1000,600);},effects(next){state.effects=next;state.budget=scenario.bubbleBudget(next,phone);},expected(){if(current.vp.w*state.ctx.camera.zoom/100<3.5||!state.projection.inside||!state.inside(state.project(),current.sc))return[];return scenario.visibleReactions(scenario.reactionsAt(variant,state.t,state.spots),state.budget,state.selectedActor);}};
}
function assertSemantic(h){
 const expected=h.expected();assert.equal(h.buttons.filter(b=>!b.hidden).length,expected.length);
 h.buttons.forEach((button,index)=>{const reaction=expected[index];if(!reaction){assert.equal(button.hidden,true);assert.equal(button.dataset.actor,undefined);const before=h.clicks.length;button.fire('click');assert.equal(h.clicks.length,before,'Hidden pooled button has no semantic click target');return;}
  assert.equal(button.hidden,false);assert.equal(button.dataset.actor,reaction.actor_id);assert.equal(button.getAttribute('aria-label'),`${reaction.actor_id}: ${reaction.text}`);assert.ok(button.title.startsWith(`${reaction.actor_id} · `));const before=h.clicks.length;button.fire('click');assert.equal(h.clicks.length,before+1);assert.equal(h.clicks.at(-1),reaction.actor_id,'Actual installed click callback uses current semantic identity');
 });
 return expected;
}
const cases=[];
function check(id,fn){try{const detail=fn()??{};cases.push({id,outcome:'PASS',...detail});}catch(error){cases.push({id,outcome:'FAIL',error:String(error.message)});}}
check('C01_A_current_actor_semantics_and_installed_click',()=>{const h=setup({variant:'A'});h.draw();assertSemantic(h);});
check('C02_B_current_actor_semantics_and_installed_click',()=>{const h=setup();h.draw();assertSemantic(h);});
check('C03_full_off_full_same_key_reappearance',()=>{for(const variant of ['A','B']){const h=setup({variant});h.draw();assertSemantic(h);const key=h.buttons[0].dataset.key;h.effects('off');h.draw();assertSemantic(h);h.effects('full');h.draw();assertSemantic(h);assert.equal(h.buttons[0].dataset.key,key);}});
check('C04_full_calm_full_restores_hidden_pool_slots',()=>{const h=setup({ids:['K01','K02','K03','K04','K05','K06']});h.draw();assertSemantic(h);h.effects('calm');h.draw();assert.equal(h.expected().length,3);assertSemantic(h);h.effects('full');h.draw();assert.equal(h.expected().length,6);assertSemantic(h);});
check('C05_full_calm_off_calm_full_repeated_cycles',()=>{const h=setup({ids:['K01','K02','K03','K04','K05','K06']});for(const effect of ['full','calm','off','calm','full','off','full']){h.effects(effect);h.draw();assertSemantic(h);}});
check('C06_phone_calm_full_budget_reappearance',()=>{const h=setup({phone:true,ids:['K01','K02','K03','K04','K05','K06']});for(const [effect,count]of [['full',3],['calm',2],['full',3],['off',0],['calm',2]]){h.effects(effect);h.draw();assert.equal(h.expected().length,count);assertSemantic(h);}});
check('C07_scale_threshold_exact_and_reappearance',()=>{const h=setup();h.draw();assertSemantic(h);h.state.ctx.camera.zoom=.349;h.draw();assertSemantic(h);h.state.ctx.camera.zoom=.35;h.draw();assert.equal(h.expected().length,1);assertSemantic(h);h.state.ctx.camera.zoom=1;h.draw();assertSemantic(h);});
check('C08_offscreen_pass_hide_and_reappearance',()=>{const h=setup();h.draw();assertSemantic(h);const sc=h.pass.sc;h.pass.sc={...sc,x:1100};h.draw();assertSemantic(h);h.pass.sc=sc;h.draw();assertSemantic(h);});
check('C09_scissor_clipped_worker_reappearance',()=>{const h=setup();h.draw();assertSemantic(h);h.state.projection.inside=false;h.draw();assertSemantic(h);h.state.projection.inside=true;h.draw();assertSemantic(h);});
check('C10_same_kind_new_cause_updates_aria_and_title',()=>{const h=setup();h.draw();const first=assertSemantic(h)[0],html=h.buttons[0].htmlWrites;h.state.t=48;h.draw();const next=h.expected()[0];assert.equal(first.bubble,next.bubble);assert.notEqual(first.text,next.text);assertSemantic(h);assert.equal(h.buttons[0].title,`${next.actor_id} · ${next.text}`);assert.equal(h.buttons[0].htmlWrites,html,'Same kind/cached key only refreshes semantic text');return{before_text:first.text,after_text:next.text};});
check('C11_random_absolute_seek_restores_current_semantics',()=>{const h=setup();for(const time of [34,48,34,110,30,46,104,0,72,48]){h.state.t=time;h.draw();assertSemantic(h);}});
check('C12_visible_pool_reuse_replaces_previous_actor',()=>{const h=setup();h.draw();assertSemantic(h);h.workers(['K02']);h.draw();assertSemantic(h);assert.equal(h.buttons[0].dataset.actor,'K02');assert.ok(!h.buttons[0].getAttribute('aria-label').includes('K01'));});
check('C13_hidden_pool_reuse_replaces_previous_actor',()=>{const h=setup();h.draw();assertSemantic(h);h.effects('off');h.draw();assertSemantic(h);h.workers(['K02']);h.effects('full');h.draw();assertSemantic(h);assert.equal(h.buttons[0].dataset.actor,'K02');});
check('C14_selected_worker_reorders_pool_without_stale_identity',()=>{const h=setup({ids:['K01','K02','K03','K04','K05','K06']});h.draw();assertSemantic(h);h.state.selectedActor='K06';h.state.budget=1;h.draw();assertSemantic(h);assert.equal(h.buttons[0].dataset.actor,'K06');h.state.selectedActor=null;h.effects('full');h.draw();assertSemantic(h);});
check('C15_icon_and_reentry_animation_cache_remains_visual_only',()=>{const h=setup({reduced:false});h.draw();assertSemantic(h);const b=h.buttons[0],writes=b.htmlWrites,animations=b.animations;h.state.t=48;h.draw();assertSemantic(h);assert.equal(b.htmlWrites,writes);assert.equal(b.animations,animations);h.effects('off');h.draw();h.effects('full');h.draw();assertSemantic(h);assert.equal(b.htmlWrites,writes);assert.equal(b.animations,animations);h.state.t=110;h.draw();assertSemantic(h);assert.equal(b.htmlWrites,writes+1);assert.equal(b.animations,animations+1);});
check('C16_reduced_motion_skips_animation_preserves_semantics',()=>{const h=setup({reduced:true});for(const time of [34,48,110,34]){h.state.t=time;h.draw();assertSemantic(h);}assert.equal(h.buttons[0].animations,0);});
check('C17_off_buttons_have_no_dispatchable_actor',()=>{const h=setup();h.draw();h.effects('off');h.draw();assertSemantic(h);assert.equal(h.buttons.every(b=>b.dataset.actor===undefined),true);});
check('C18_unused_pool_slots_have_no_previous_actor',()=>{const h=setup({ids:['K01','K02','K03','K04','K05','K06']});h.draw();assertSemantic(h);h.workers(['K02']);h.draw();assertSemantic(h);assert.equal(h.buttons.slice(1).every(b=>b.hidden&&b.dataset.actor===undefined),true);});
const output={passed:cases.every(row=>row.outcome==='PASS'),task:'Twin M001 bubble semantics',label:'COMPONENT_ONLY',public_bootstrap:false,native_admission:false,native_530_HU_scene:false,rendered_appearance:false,scope:'Exact private domFor helper and actual production bubble-pool creation/click listeners extracted from current TypeScript AST; real scenario samplers, synthetic worker spots, DOM/projection/camera stubs. Whole renderer factory and WebGL are not executed.',input_hashes:{[checkerPath]:sha(fs.readFileSync(path.join(root,checkerPath))),[renderPath]:sha(renderBytes),[scenarioPath]:sha(scenarioBytes)},compiler:{dependency:'frontend/node_modules/typescript',version:ts.version},extracted_source:{domFor_line:ast.getLineAndCharacterOfPosition(domNode.getStart(ast)).line+1,pool_and_click_listener_line:ast.getLineAndCharacterOfPosition(poolNode.getStart(ast)).line+1},historical_reference:{audit_findings_path:'work/v3/account2-twin-ui-audit/20261108T171019Z/findings.json',audit_findings_sha256:'9234b4c149e794062ad7753134a82d48305bf89c91261540d40a6d91eebe3223',finding_id:'TWIN-A2-001',before_fix_renderer_sha256:'11b7001b50daf734ab84cb0f5599d53444a0379fdfbd62f5dc2f7ba5274cda56',before_fix_copy:'work/v3/twin-bubbles-check/red/twinRender.ts',before_fix_result_path:'work/v3/twin-bubbles-check/red/before-fix-results.json',before_fix_result_sha256:'cf7104c4937f11051375be72f09125c23dcccce6519f54f565d447b7c4b2b87c',before_fix_counts:{cases:18,passed:6,failed:12},note:'Historical source/audit reference only. No new CLI completion or native/browser acceptance claim.'},counts:{cases:cases.length,passed:cases.filter(row=>row.outcome==='PASS').length,failed:cases.filter(row=>row.outcome!=='PASS').length},cases};
if(!output.passed){console.error(JSON.stringify(output,null,2));process.exitCode=1;}else{
 const bytes=Buffer.from(JSON.stringify(output,null,2)+'\n','utf8');
 if(checkOnly){if(!bytes.equals(fs.readFileSync(path.join(root,evidencePath))))throw Error('TWIN_BUBBLE_EVIDENCE_MISMATCH: recomputed report differs from accepted bytes');}else fs.writeFileSync(path.join(root,evidencePath),bytes);
 console.log(JSON.stringify({passed:true,check_only:checkOnly,label:output.label,counts:output.counts,input_hashes:output.input_hashes,evidence_sha256:sha(bytes)}));
}
