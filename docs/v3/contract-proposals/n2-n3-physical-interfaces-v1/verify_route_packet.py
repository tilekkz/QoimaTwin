"""Offline read-only source verification; reports only beside this script."""
from pathlib import Path
import argparse,copy,json,hashlib,math,time
from route_math import evaluate,pose_error,prove_segment,floor_contained,wrap,sweep_bounds,padded
OWN=Path(__file__).resolve().parent
arg=argparse.ArgumentParser();arg.add_argument('--repo',type=Path,default=OWN.parents[3]);REPO=arg.parse_args().repo.resolve();started=time.monotonic()
P=json.loads((OWN/'route-terminal-interfaces.json').read_text('utf8'));G=json.loads((OWN/'reference-vehicle-graph.json').read_text('utf8'));checks=[];negative=[]
def ck(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def ptr(d,p):
 for k in p.lstrip('/').split('/') if p else []:d=d[int(k)] if isinstance(d,list) else d[k.replace('~1','/').replace('~0','~')]
 return d
def pp(p):return p['position_m'],p['yaw_rad']
def pv(p):return p['scale']==[1,1,1] and all(math.isfinite(x) for x in p['position_m']+[p['yaw_rad']]) and max(abs(a-b) for a,b in zip(p['quaternion_xyzw'],[0,math.sin(p['yaw_rad']/2),0,math.cos(p['yaw_rad']/2)]))<1e-12
source={}
for path,expected in P['source_hashes'].items():
 b=(REPO/path).read_bytes();ck('hash:'+path,hashlib.sha256(b).hexdigest()==expected)
 if path.endswith('.json'):source[path]=json.loads(b)
def refs(x):
 if isinstance(x,dict):
  if all(k in x for k in ['repo_path','sha256','json_pointer']):ck('pointer:'+x['repo_path']+x['json_pointer'],P['source_hashes'].get(x['repo_path'])==x['sha256'] and ptr(source[x['repo_path']],x['json_pointer']) is not None)
  for v in x.values():refs(v)
 elif isinstance(x,list):
  for v in x:refs(v)
refs(P)
ck('ready_interface_only',P['ready'] and not P['scope']['operational_admission'] and not P['scope']['full_W11_W12_runtime_complete'])
actual=source['docs/v3/contract-proposals/layout-links-v3.json']['vehicle_graph'];ck('exact_reference_graph',G['nodes']==actual['nodes'] and G['arcs']==actual['arcs'])
nodes={n['node_id']:n for n in G['nodes']};arcs={a['arc_id']:a for a in G['arcs']};ports={r['port_id']:r for r in P['ports']}
def eligible(a,profile,cargo,pair):return profile in a['allowed_geometry_profile_ids'] and cargo in a['allowed_cargo_archetype_ids'] and pair in a['equipment_pair_refs'] and a.get('cargo_transport_supported',True)
def staging_refusal(cell_id,cargo,pair,occupied=False):
 cell=next((r for r in P['staging_cells'] if r['cell_id']==cell_id),None)
 if cell is None or occupied:return 'STAGING_CELL_UNAVAILABLE'
 port=ports[cell['port_id']]
 if cargo not in port['vehicle_service_action']['allowed_cargo_archetype_ids'] or pair not in port['vehicle_service_action']['equipment_pair_refs']:return 'PORT_CARGO_OR_POWERED_SERVICE_FORBIDDEN'
 if not any(r['cell_id']==cell_id and r['archetype_id']==cargo for r in P['connectors']):return 'TERMINAL_CONNECTOR_NOT_PROVED'
 return None
def chain(c):
 seg=c['segments'];ok=pv(c['start']['pose']) and pv(c['end']['pose']);ok &= pose_error(pp(c['start']['pose']),evaluate(seg[0]['geometry'],0))<1e-8 and pose_error(pp(c['end']['pose']),evaluate(seg[-1]['geometry'],1))<1e-8
 for i,s in enumerate(seg):
  g=s['geometry'];ok &= pv(s['start_pose']) and pv(s['end_pose']);ok &= pose_error(pp(s['start_pose']),evaluate(g,0))<1e-8 and pose_error(pp(s['end_pose']),evaluate(g,1))<1e-8
  if i:ok &= pose_error(evaluate(seg[i-1]['geometry'],1),evaluate(g,0))<1e-8 and seg[i-1]['end_node_id']==s['start_node_id']
  if g['kind']=='rear_steer_arc':ok &= abs(g['icr_vehicle_local_x_m'])>=1.4/math.tan(math.pi/3)-1e-12 and s['inner_rear_wheel_steer_abs_deg']<=75
  else:
   a,t=evaluate(g,0);b,_=evaluate(g,1);ok &= abs((b[0]-a[0])*math.cos(t)-(b[2]-a[2])*math.sin(t))<1e-8 and ((b[0]-a[0])*math.sin(t)+(b[2]-a[2])*math.cos(t))*s['motion_direction']>=-1e-8
 return bool(ok)
details=[]
for c in P['connectors']:
 ck('chain:'+c['connector_id'],chain(c));ck('floor:'+c['connector_id'],all(floor_contained(s['geometry'],c['geometry_profile_components_local_m']) for s in c['segments']))
 obs=[o for o in P['geometry_obstacles'] if o['id']!=c['excluded_intended_terminal_id']];proofs=[prove_segment(s['geometry'],c['geometry_profile_components_local_m'],obs) for s in c['segments']]
 ck('continuous_profile:'+c['connector_id'],all(p['passed'] for p in proofs),[p for p in proofs if not p['passed']]);details.append({'id':c['connector_id'],'passed':all(p['passed'] for p in proofs),'interval_tests':sum(p['interval_tests'] for p in proofs)})
 ck('no_bare_override:'+c['connector_id'],not c['source_arc_reuse'] and c['not_a_bare_only_arc_override'] and not c['operational_admission'])
samples=0;maximum=0
for edge in source['docs/v3/contract-proposals/vehicle-graph-v3.json']['edges']:
 for row in edge['pose_samples']:
  p,t=evaluate(edge['geometry'],row[0]);maximum=max(maximum,math.dist(p,row[1:4]),abs(wrap(t-row[4])));samples+=1
ck('independent_L07_samples',maximum<1e-10,{'count':samples,'max_error':maximum})
for r in P['route_examples']:
 ok=len(r['node_ids'])==len(r['arc_ids'])+1
 for i,aid in enumerate(r['arc_ids']):
  a=arcs[aid];profile='loaded_max';ok &= a['from_node_id']==r['node_ids'][i] and a['to_node_id']==r['node_ids'][i+1] and eligible(a,profile,r['archetype_id'],r['equipment_pair_ref'])
  ok &= pose_error(evaluate(a['geometry'],0),(nodes[a['from_node_id']]['world_pos'],nodes[a['from_node_id']]['yaw_rad']))<1e-8 and pose_error(evaluate(a['geometry'],1),(nodes[a['to_node_id']]['world_pos'],nodes[a['to_node_id']]['yaw_rad']))<1e-8
 ck('source_route:'+r['route_id'],ok)
for g in P['gate_joins']:
 p=ports[g['port_id']];allow=p['vehicle_service_action']['vehicle_service_enabled'] and g['archetype_id'] in p['vehicle_service_action']['allowed_cargo_archetype_ids'];geom=g['required_padded_width_m']<=g['clear_width_m'] and g['required_padded_height_m']<=g['clear_height_m'];ck('gate_policy:'+g['gate_join_id'],allow==g['policy_eligible'] and geom==g['aperture_geometry_clear'] and (not allow or geom));ck('gate_straight:'+g['gate_join_id'],abs(wrap(g['start']['pose']['yaw_rad']-g['end']['pose']['yaw_rad']))<1e-12)
ck('one_station_identity',sum(o['id']==P['attachment_stow_station']['station_id'] for o in P['geometry_obstacles'])==1 and P['attachment_stow_station']['capacity_attachment_assemblies']==1)
ck('capacity_IN_W_2',sum(c['maximum_handling_units'] for c in P['staging_cells'] if c['port_id']=='IN_W_BULK')==2)
for e in P['embedded_evidence']:ck('embedded:'+e['path'],hashlib.sha256((OWN/e['path']).read_bytes()).hexdigest()==e['sha256'])
ck('storage_fail_closed',all(not r['operational_admission'] and not r['stub_clearance_admitted'] and r['refusal'] for r in P['storage_terminal_joins']))
ck('storage_pi_disclosed',all(abs(abs(r['required_relative_HU_yaw_rad'])-math.pi)<1e-10 for r in P['storage_terminal_joins']))
def neg(name,detected):negative.append({'name':name,'passed':bool(detected)})
bad=copy.deepcopy(P['connectors'][0]);bad['segments'][2]['start_pose']['position_m'][0]+=.01;neg('teleport_rejected',not chain(bad))
bad=copy.deepcopy(P['connectors'][0]);bad['start']['pose']['scale'][0]=.5;neg('scale_rejected',not chain(bad))
bad=copy.deepcopy(P['connectors'][0]);bad['segments'][1]['geometry']['end_yaw_rad']+=.01;neg('line_yaw_hack_rejected',not chain(bad))
bare=next(a for a in G['arcs'] if a['allowed_geometry_profile_ids']==['unloaded_bare']);neg('bare_ONLY_LONG_rejected',not eligible(bare,'loaded_max','LONG_BUNDLE','INBOUND_FORKLIFT_PAIR'))
a=next(a for a in G['arcs'] if 'loaded_max' in a['allowed_geometry_profile_ids']);neg('wrong_pair_rejected',not eligible(a,'loaded_max','LONG_BUNDLE','THIRD_PAIR'))
neg('manual_port_power_rejected',not ports['IN_E_PARCEL']['vehicle_service_action']['vehicle_service_enabled']);neg('retail_LONG_rejected','LONG_BUNDLE' not in ports['OUT_W_RETAIL']['vehicle_service_action']['allowed_cargo_archetype_ids'])
neg('old_relative_zero_rejected',all(r['old_relative_identity_refusal']=='SAME_HU_FRAME_INCOMPATIBLE' for r in P['storage_terminal_joins']))
neg('stale_W12_epoch_refused',next(r for r in P['scenario_epochs'] if 'W12-' in r['source'])['execution_refusal']=='SCENARIO_SOURCE_EPOCH_MISMATCH')
neg('upper_LONG_blocked',any(r['archetype_id']=='LONG_BUNDLE' and r['retrieval_blocked'] and r['refusal']=='STORAGE_RETRIEVAL_BLOCKED' for r in P['storage_terminal_joins']))
cell=P['connectors'][0]['cell_id'];neg('unknown_cell_refused',staging_refusal('nonexistent','PALLET_LOAD','INBOUND_FORKLIFT_PAIR')=='STAGING_CELL_UNAVAILABLE');neg('occupied_cell_refused',staging_refusal(cell,'PALLET_LOAD','INBOUND_FORKLIFT_PAIR',True)=='STAGING_CELL_UNAVAILABLE');neg('cell_wrong_pair_refused',staging_refusal(cell,'PALLET_LOAD','THIRD_PAIR')=='PORT_CARGO_OR_POWERED_SERVICE_FORBIDDEN')
c=P['connectors'][0];g=c['segments'][0]['geometry'];obs={'id':'negative:foreign','bounds':sweep_bounds(g,padded(c['geometry_profile_components_local_m'][0]))};neg('actual_obstacle_intersection_rejected',not prove_segment(g,c['geometry_profile_components_local_m'],[obs])['passed'])
for path,sha in P['source_hashes'].items():ck('after_hash:'+path,hashlib.sha256((REPO/path).read_bytes()).hexdigest()==sha)
passed=all(c['passed'] for c in checks+negative)
report={'schema_id':'qoima.n2-n3-route-terminal-checks.v1','ready':True,'passed':passed,'status':'PASS_BOUNDED_INTERFACE_PACKET' if passed else 'FAIL','elapsed_s':time.monotonic()-started,'source_hashes':P['source_hashes'],'source_nodes':len(nodes),'source_arcs':len(arcs),'connector_count':len(P['connectors']),'analytic_clear_connectors':sum(d['passed'] for d in details),'obstacle_count':len(P['geometry_obstacles']),'gate_policy_rows':len(P['gate_joins']),'source_routes':len(P['route_examples']),'storage_endpoint_joins':len(P['storage_terminal_joins']),'checks':checks,'negative_controls':negative,'connector_proofs':details,'packet_sha256':hashlib.sha256((OWN/'route-terminal-interfaces.json').read_bytes()).hexdigest(),'scope':'Continuous analytic padded profiles for named proposed connectors; no native full-mesh, continuous transfer, scheduling or engine admission.'}
print(json.dumps({k:report[k] for k in ['passed','status','elapsed_s','connector_count','analytic_clear_connectors','obstacle_count','gate_policy_rows','source_routes','storage_endpoint_joins']}));print(json.dumps({'failed':[c for c in checks+negative if not c['passed']][:15]}));raise SystemExit(0 if passed else 1)
