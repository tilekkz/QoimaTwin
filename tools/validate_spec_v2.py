from pathlib import Path
import json,math,heapq,sys,hashlib
R=Path(__file__).resolve().parents[1];C=R/'contracts'
# Prepared document/schema checks only, not tests of an implemented warehouse.
import jsonschema
checks=[]
def ck(name,condition):
 if not condition:raise AssertionError(name)
 checks.append(name)
def rd(n):return json.loads((C/n).read_text(encoding='utf-8'))
l=rd('layout.example.json');cfg=rd('simulation_defaults.json');a=rd('actors.example.json');stock=rd('assignment.example.json');f=rd('analytical_fixture.json')
for data,schema in [('layout.example.json','layout.schema.json'),('actors.example.json','actors.schema.json')]:
 sc=rd(schema);jsonschema.Draft202012Validator.check_schema(sc);jsonschema.Draft202012Validator(sc).validate(rd(data));ck('JSON Schema: '+data,True)
for s in ['run.schema.json','scenario.schema.json']:
 jsonschema.Draft202012Validator.check_schema(rd(s));ck('Schema structure valid: '+s,True)
nodes={n['node_id']:n['pos'] for n in l['picker_graph']['nodes']};edges=l['picker_graph']['edges'];adj={n:[] for n in nodes}
ck('Picker node count 184',len(nodes)==184);ck('Picker edge count 205',len(edges)==205)
for e in edges:
 ck('Euclidean edge: '+e['a']+' / '+e['b'],abs(math.dist(nodes[e['a']],nodes[e['b']])-e['length_m'])<1e-9 and e['length_m']>0)
 adj[e['a']].append((e['b'],e['length_m']));adj[e['b']].append((e['a'],e['length_m']))
def distances(start):
 d={start:0};q=[(0,start)]
 while q:
  v,n=heapq.heappop(q)
  if v!=d[n]:continue
  for w,z in adj[n]:
   if v+z<d.get(w,math.inf):d[w]=v+z;heapq.heappush(q,(v+z,w))
 return d
for h in ['I01','I02','I03']:
 ck('All picker nodes reachable from '+h,len(distances(h))==184)
d=distances('I01');d2=distances('N_A01_Z16')
ck('Route I01 to first bay =4',d['N_A01_Z16']==4)
ck('Cross-aisle detour =8.5',d2['N_A02_Z16']==8.5)
ck('One order route =21',d['N_A01_Z16']+d2['N_A02_Z16']+d['N_A02_Z16']==21)
slots={x['slot_id']:x for x in l['slots']};racks={x['rack_id']:x for x in l['racks']}
ck('864 unique slots /288 racks',len(slots)==864 and len(racks)==288)
ck('288 pick faces /576 reserve',sum(x['kind']=='pickface' for x in slots.values())==288)
for x in slots.values():
 ck('Slot rack/anchor valid: '+x['slot_id'],x['rack_id'] in racks and (x['service_node_id'] in nodes if x['level']==1 else x['service_node_id'] is None))
 ck('Anchor inside bounds: '+x['slot_id'],all(0<=v<=hi for v,hi in zip(x['bin_anchor'],l['bounds']['max'])))
# Reject graph segments through any rack footprint, using strict interior intersection.
def crosses(p,q,r):
 xmin=r['root'][0]-r['size'][0]/2;xmax=r['root'][0]+r['size'][0]/2
 zmin=r['root'][2]-r['size'][2]/2;zmax=r['root'][2]+r['size'][2]/2
 if p[0]==q[0]:return xmin<p[0]<xmax and max(min(p[2],q[2]),zmin)<min(max(p[2],q[2]),zmax)
 if p[2]==q[2]:return zmin<p[2]<zmax and max(min(p[0],q[0]),xmin)<min(max(p[0],q[0]),xmax)
 raise AssertionError('non-axis aligned edge')
ck('All picker edges avoid rack interiors',not any(crosses(nodes[e['a']],nodes[e['b']],r) for e in edges for r in racks.values()))
segs={s['segment_id']:s for s in l['conveyor']['segments']}
ck('179 conveyor cells',sum(s['cell_count'] for s in segs.values())==179)
ck('Tote pool below112 ring cells',cfg['totes_total']==96 and cfg['totes_total']<112)
for s in segs.values():
 ck('Segment length/cells '+s['segment_id'],math.dist(s['from'],s['to'])==s['length_m']==s['cell_count'])
# Build canonical directed cell graph with every internal connection port.
ca={}
for name,s in segs.items():
 for i in range(s['cell_count']):
  ca[(name,i)]=set()
  if i+1<s['cell_count']:ca[(name,i)].add((name,i+1))
for k in l['conveyor']['connections']:
 s=segs[k['from_segment_id']];t=segs[k['to_segment_id']];p=k['at']
 os=math.dist(s['from'],p);ot=math.dist(t['from'],p)
 ck('Port lies on both segments '+k['from_segment_id']+'/'+k['to_segment_id'],abs(os+math.dist(p,s['to'])-s['length_m'])<1e-9 and abs(ot+math.dist(p,t['to'])-t['length_m'])<1e-9)
 ck('Port on integer cell boundaries',os==int(os) and ot==int(ot))
 src=(s['segment_id'],int(os)-1);dst=(t['segment_id'],int(ot))
 ck('Port cell references valid',src in ca and dst in ca)
 ca[src].add(dst)
def shortest(start,end):
 q=[(start,0)];seen={start}
 for n,d in q:
  if n==end:return d
  for w in sorted(ca[n]):
   if w not in seen:seen.add(w);q.append((w,d+1))
 raise AssertionError('Unreachable')
for i in range(1,4):
 for j in range(1,7):ck(f'Conveyor I{i} reaches PK{j}',shortest((f'FEED{i:02d}',0),(f'BRANCH{j:02d}',1))>=1)
ck('I01 to PK01 =19 cell travel seconds',shortest(('FEED01',0),('BRANCH01',1))+1==19)
ck('PK01 to shipping =47 cell travel seconds',shortest(('OUTFEED01',0),('OUT_MAIN',45))+1==47)
actors=a['actors'];ck('24 unique actors',len({x['actor_id'] for x in actors})==24)
for role,count in cfg['staffing'].items():ck('Staff '+role,sum(x['role']==role for x in actors)==count)
active=stock['active_assignment'];lots=stock['initial_lots']
ck('Injective200 SKU assignment',len(active)==len(set(active.values()))==200)
ck('Only ground assignments',all(slots[k]['kind']=='pickface' for k in active))
ck('600 lots in600 unique bins',len(lots)==len({x['slot_id'] for x in lots})==600)
ck('Initial600000 units',sum(x['quantity'] for x in lots)==600000)
ck('88 empty active and176 empty reserve',len(stock['empty_pickfaces'])==88 and len(stock['empty_reserve_slots'])==176)
ck('Empty and occupied partition all864',set(x['slot_id'] for x in lots).isdisjoint(stock['empty_pickfaces']+stock['empty_reserve_slots']) and len(lots)+88+176==864)
for sku in active.values():
 ls=[x for x in lots if x['sku_id']==sku];ck('Stock SKU '+sku,len(ls)==3 and sorted(x['quantity'] for x in ls)==[500,500,2000])
e=f['expected'];ck('Fixture picker ready32.8',abs(21/1.2+2*6.15+3-e['handoff_ready_s'])<1e-9)
ck('Fixture feed33 and pack52',math.ceil(e['handoff_ready_s'])==33 and 33+19==e['pack_buffer_arrival_s'])
ck('Fixture pack76.1/outfeed77',abs(52+20+2*2+.05*2-e['pack_completed_s'])<1e-9 and math.ceil(e['pack_completed_s'])==77)
ck('Fixture shipping124/scan132/seal432',77+47==124 and 124+8==132 and 132+300==432)
ck('Fixture dispatch469/home474',432+6/2+15+8/2+15==469 and 469+10/2==474)
ck('Offered load is not promised capacity',cfg['profiles']['large-normal']['orders_per_hour']==240 and cfg['profiles']['large-peak']['orders_per_hour']==600)
ck('Legacy v1 explicitly preserved',(C/'legacy-v1/technical_specification.v1.md').exists() and rd('legacy-v1/layout.example.json')['layout_version']=='qoyma-20x18-v1')
report={'date':'2026-11-07','scope':'v2 prepared documentation, schemas, geometry, examples and analytical arithmetic; not application implementation tests','spec_version':'2.0','layout_version':l['layout_version'],'total_checks':len(checks),'all_passed':True,'checks':checks,'not_verified':['runtime DES/conveyor behavior','runtime replay/seek','full generated200SKUscenarios or forecasts','warehouse capacity/output','optimization gain','new GLB assets','target laptop performance'],'legacy_report':'contracts/legacy-v1/verification_report.v1.json'}
(R/'verification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':len(checks),'scope':report['scope']},ensure_ascii=False))
