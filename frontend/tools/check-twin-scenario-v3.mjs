// Checks the frozen A/B demonstration episode: causes, allowed wave edges, no flicker, seek determinism.
// Run from frontend/: node tools/check-twin-scenario-v3.mjs  (Node >= 22.18 strips TS types natively)
import assert from 'node:assert/strict';
const S=await import('../src/adaptive-v3/twin/twinScenario.ts');
const zones=new Set(S.ATMO_ZONES.map(z=>z.id)),edge=(a,b)=>S.INFLUENCE_EDGES.some(([x,y])=>(x===a&&y===b)||(x===b&&y===a));
for(const v of ['A','B']){
 const ev=S.DEMO_EVENTS[v];
 assert.deepEqual([...ev].sort((a,b)=>a.at_s-b.at_s),[...ev],`${v}: events sorted`);
 for(const e of ev){
  assert.ok(zones.has(e.zone_id),`${v}: known zone ${e.zone_id}`);
  assert.ok(e.cause.length>8,`${v}: cause text at ${e.at_s}`);
  assert.ok(e.at_s>=0&&e.at_s<=S.DEMO_DURATION_S);
  if(e.from_zone_id)assert.ok(edge(e.from_zone_id,e.zone_id),`${v}: wave ${e.from_zone_id}->${e.zone_id} uses a declared edge`);
 }
 for(const z of zones){
  const segs=S.stateSegments(v,z);
  for(const s of segs.slice(0,-1))assert.ok(s.to_s-s.from_s>=10,`${v}/${z}: state held >=10 s (no flicker)`);
  assert.equal(segs.at(-1).state,'control',`${v}/${z}: episode ends in control`);
 }
 // Independent zones never react to the packing wave.
 for(const z of ['HEAVY_W','HEAVY_E','LONG_W','LONG_E','SMALL_W','STANDARD_W'])
  for(let t=0;t<=S.DEMO_DURATION_S;t+=1)assert.equal(S.sampleAtmosphere(v,t)[z].state,'control',`${v}/${z} @${t}`);
 // Seek order does not matter: random jumps equal a forward sweep.
 const forward=new Map();for(let t=0;t<=S.DEMO_DURATION_S;t+=0.5)forward.set(t,JSON.stringify(S.sampleAtmosphere(v,t)));
 let seed=7;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
 for(let i=0;i<200;i++){const t=Math.round(rnd()*S.DEMO_DURATION_S*2)/2;assert.equal(JSON.stringify(S.sampleAtmosphere(v,t)),forward.get(t),`${v}: seek ${t}`);}
 for(const p of S.activePulses(v,72))assert.ok(p.progress>=0&&p.progress<=1);
}
// The LONG refusal is independent of the plan: identical in A and B.
const long=v=>S.DEMO_EVENTS[v].filter(e=>e.zone_id==='STAGE_OUT_S_EXPRESS');
assert.deepEqual(long('A'),long('B'));
assert.equal(S.sampleAtmosphere('A',100).PACKING_LIGHT_LINE.state,'sos');
assert.equal(S.sampleAtmosphere('B',100).PACKING_LIGHT_LINE.state,'danger');
assert.equal(S.DEMO_SOURCE.engine_operation,false);
// Presenter text quotes recovery times; keep them tied to the fixture.
assert.equal(S.stateSegments('B','PACKING_LIGHT_LINE').at(-1).from_s,104,'presenter says B recovers at 01:44');
assert.equal(S.stateSegments('A','PACKING_LIGHT_LINE').at(-1).from_s,200,'presenter says A recovers at 03:20');
for(const s of S.PRESENTER_STEPS){assert.ok(s.t>=0&&s.t<=S.DEMO_DURATION_S&&s.focus.span>0&&s.title&&s.text.length>20);}
assert.equal(S.sampleAtmosphere('A',114).STAGE_OUT_S_EXPRESS.state,'danger','refusal step shows the refusal');

// Worker reactions: presentation only, deterministic, budgeted, local to the troubled zone.
const R=S;
const crew=[...['K01','K02','K03','K04','K05','K06'].map(id=>({actor_id:id,zone_id:'PACKING_LIGHT_LINE'})),
 ...['P01','P02'].map(id=>({actor_id:id,zone_id:'STANDARD_E'})),{actor_id:'P03',zone_id:'SMALL_E'},
 {actor_id:'P09',zone_id:'HEAVY_W'},{actor_id:'P10',zone_id:'LONG_E'},{actor_id:'FL01',zone_id:null}];
for(const v of ['A','B']){
 const forward=new Map();for(let t=0;t<=S.DEMO_DURATION_S;t+=1)forward.set(t,JSON.stringify(R.reactionsAt(v,t,crew)));
 let seed=11;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
 for(let i=0;i<200;i++){const t=Math.round(rnd()*S.DEMO_DURATION_S);assert.equal(JSON.stringify(R.reactionsAt(v,t,crew)),forward.get(t),`${v}: reactions seek ${t}`);}
 for(let t=0;t<=S.DEMO_DURATION_S;t+=1){
  const all=R.reactionsAt(v,t,crew),z=S.sampleAtmosphere(v,t);
  assert.equal(new Set(all.map(r=>r.actor_id)).size,all.length,`${v}@${t}: one bubble per worker`);
  for(const r of all){
   assert.notEqual(r.zone_id,'HEAVY_W');assert.notEqual(r.zone_id,'LONG_E');
   if(r.bubble==='relief')assert.equal(z[r.zone_id].state,'control',`${v}@${t}: relief only in control`);
   else assert.notEqual(z[r.zone_id].state,'control',`${v}@${t}: worry only where the zone is not in control`);
  }
  for(const [eff,phone,max] of [['full',false,6],['full',true,3],['calm',false,3],['off',false,0]])
   assert.ok(R.visibleReactions(all,R.bubbleBudget(eff,phone),null).length<=max,`${v}@${t}: budget ${eff}/${phone}`);
 }
 // Calm start: nobody reacts before the first trouble.
 assert.equal(R.reactionsAt(v,10,crew).length,0,`${v}: calm shift has no bubbles`);
}
// SOS in A: someone signals, someone asks for help; the selected worker always keeps a bubble.
const sos=R.reactionsAt('A',100,crew.filter(c=>c.zone_id==='PACKING_LIGHT_LINE'));
assert.deepEqual(sos.slice(0,2).map(r=>r.bubble),['alert','help']);
const last=sos.at(-1).actor_id;assert.equal(R.visibleReactions(sos,1,last)[0].actor_id,last);
// B recovers at 104: relief shows briefly, then fades.
assert.ok(R.reactionsAt('B',106,crew).some(r=>r.bubble==='relief'),'B shows relief right after recovery');
assert.equal(R.reactionsAt('B',104+R.RELIEF_S+1,crew).filter(r=>r.zone_id==='PACKING_LIGHT_LINE').length,0,'relief fades');
// Card text matches the bubble for the same worker.
for(const r of R.reactionsAt('A',100,crew))assert.equal(R.workerStatus('A',100,crew,r.actor_id),r.text);
assert.match(R.workerStatus('A',100,crew,'FL01'),/Вне участков/);
// "Why" chains: history explains the current state; the wave names its source; recovered zones really recovered.
for(const v of ['A','B'])for(let t=0;t<=S.DEMO_DURATION_S;t+=2){
 const now=S.sampleAtmosphere(v,t);
 for(const z of S.ATMO_ZONES.map(z=>z.id)){const h=S.zoneHistory(v,z,t);if(h.length){assert.equal(h.at(-1).state,now[z].state,`${v}/${z}@${t}: last history entry is the current state`);assert.equal(h.at(-1).cause,now[z].cause);}}
 for(const z of S.recoveredZones(v,t)){assert.equal(now[z].state,'control');assert.ok(S.zoneHistory(v,z,t).some(e=>e.state!=='control'),`${v}/${z}@${t}: recovered after trouble`);}
}
assert.equal(S.zoneHistory('A','STANDARD_E',100).find(e=>e.from)?.from,'Упаковка и линия','wave names its source zone');
assert.deepEqual(S.recoveredZones('A',100),[]);assert.ok(S.recoveredZones('B',120).includes('PACKING_LIGHT_LINE'));
// Search: forgiving about case, separators and v3 prefixes; exact IDs first; empty or unknown queries find nothing.
const Q=await import('../src/adaptive-v3/twin/twinSearch.ts');
const idx=Q.buildIndex([
 ...['P01','P02','K03','K04'].map(id=>({kind:'actor',id,title:id,sub:id[0]==='K'?'Упаковщик':'Комплектовщик',keys:[id,id[0]==='K'?'Упаковщик':'Комплектовщик']})),
 ...Array.from({length:9},(_,i)=>({kind:'HU',id:`v3:HU:initial:DEMO_00${i+1}:01`,title:`DEMO_00${i+1}`,sub:'SMALL_CARTON',keys:[`v3:HU:initial:DEMO_00${i+1}:01`,`DEMO_00${i+1}`,'SMALL_CARTON']})),
 {kind:'port',id:'OUT_S_EXPRESS',title:'OUT_S_EXPRESS',sub:'выход',keys:['OUT_S_EXPRESS','выход','ворота']},
 {kind:'zone',id:'PACKING_LIGHT_LINE',title:'Упаковка и линия',sub:'участок',keys:['PACKING_LIGHT_LINE','Упаковка и линия']},
 {kind:'slot',id:'v3:slot:SMALL_E:019:L1:B5',title:'SMALL_E:019:L1:B5',sub:'занята',keys:['v3:slot:SMALL_E:019:L1:B5']},
]);
assert.equal(Q.search(idx,'p01')[0].id,'P01','exact worker id first');
assert.deepEqual(Q.search(idx,'упаков').filter(h=>h.kind==='actor').map(h=>h.id),['K03','K04'],'role words find workers');
assert.equal(Q.search(idx,'demo 003')[0].id,'v3:HU:initial:DEMO_003:01','separators do not matter');
assert.equal(Q.search(idx,'small_e 019').find(h=>h.kind==='slot')?.id,'v3:slot:SMALL_E:019:L1:B5');
assert.equal(Q.search(idx,'out s')[0].id,'OUT_S_EXPRESS');
assert.ok(Q.search(idx,'demo').filter(h=>h.kind==='HU').length<=5,'at most five per kind');
assert.deepEqual(Q.search(idx,'   '),[]);assert.deepEqual(Q.search(idx,'zzzz'),[]);
assert.equal(Q.shortId('v3:HU:initial:DEMO_001:01'),'DEMO_001:01');

// Scenario cards N0–N4: every count, time and hash shown in the UI must come from the fixture it names.
{
 const {readFileSync}=await import('node:fs');const C=await import('../src/adaptive-v3/twin/twinScenarios.ts');
 const read=p=>JSON.parse(readFileSync(new URL('../../'+p,import.meta.url),'utf8')),card=id=>C.SCENARIOS.find(c=>c.id===id);
 assert.deepEqual(C.SCENARIOS.map(c=>c.id),['N0','N1','N2','N3','N4']);
 const base=JSON.parse(readFileSync(new URL('../public/data/v3/warehouse-fixture-v3.json',import.meta.url),'utf8'));
 const zoneIds=new Set(JSON.parse(readFileSync(new URL('../public/data/adaptive-v3/layout-manifest.json',import.meta.url),'utf8')).data.zones.map(z=>z.zone_id));
 for(const c of C.SCENARIOS){
  for(const z of c.focus)assert.ok(zoneIds.has(z),`${c.id}: focus zone ${z} exists`);
  for(const w of [...c.changes,c.idea,c.same])assert.ok(!/выигрыш \d|быстрее на|экономи[яи] \d|\d+\s*%/.test(w),`${c.id}: no outcome claims`);
  if(!c.source)continue;const f=read(c.source.path);
  assert.equal(f.frozen_payload_sha256??f.inputs_sha256,c.source.sha256,`${c.id}: payload hash`);
  assert.equal(f.engine_operation,false,`${c.id}: not an engine run`);assert.equal(f.comparison_policy.decision_state,'not_evaluated',`${c.id}: no decision`);
  assert.ok(f.scenario_id.includes(`:${c.id}_`),`${c.id}: scenario id ${f.scenario_id}`);
  if(c.ports){
   for(const dir of ['inbound','outbound'])for(const p of c.ports[dir]){
    assert.equal(f.control.normal_port_counts[dir][p.port_id]??0,p.before,`${c.id} ${p.port_id} before`);
    assert.equal(f.control.scenario_port_counts[dir][p.port_id]??0,p.after,`${c.id} ${p.port_id} after`);
   }
   const n=c.ports.inbound.length+c.ports.outbound.length;assert.equal(n,base.inputs.ports.length,`${c.id}: all gates listed`);
  }
 }
 const n1=read(card('N1').source.path).control.declared_port_changes;
 assert.equal(n1.length,4);assert.equal(n1.filter(d=>d.direction==='outbound'&&d.from_port_id==='OUT_W_RETAIL').length,3);
 assert.equal(n1.filter(d=>d.direction==='inbound'&&d.from_port_id==='IN_N_STANDARD'&&d.to_port_id==='IN_E_PARCEL').length,1);
 const n2=read(card('N2').source.path).preregistration;
 assert.deepEqual([n2.added_HUs,n2.port_id,n2.first_release_s,n2.last_release_s,n2.interval_s,n2.deadline_offset_s],[12,'IN_W_BULK',90,750,60,600]);
 assert.deepEqual(n2.repeating_archetypes,['PALLET_LOAD','IBC','HEAVY_BOX']);
 const w12=read(card('N3').source.path),n3=w12.preregistration,gate=base.inputs.ports.find(p=>p.port_id==='IN_W_BULK');
 assert.deepEqual([n3.additional_receipts,n3.archetype_id,n3.deadline_offset_seconds],[4,'LONG_BUNDLE',900]);assert.deepEqual(n3.release_seconds,[180,360,540,720]);
 assert.deepEqual([gate.clear_width_m,gate.clear_height_m,w12.long_requirements[0].attachment_mass_kg],[7,4.5,40]);
 const reg=JSON.parse(readFileSync(new URL('../public/data/v3/worker-registry-v3.json',import.meta.url),'utf8'));
 for(const id of ['K05','K06','P11','P12'])assert.ok(JSON.stringify(reg).includes(`"actor_id": "${id}"`)||JSON.stringify(reg).includes(`"actor_id":"${id}"`),`N4 names real worker ${id}`);
}
console.log('twin scenario v3: OK');
