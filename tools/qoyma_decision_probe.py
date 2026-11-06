"""Bounded Qoyma feasibility probe; NOT the app or a queue simulation.
Canonical 31-node/33-edge aisle graph, fixed ABC28, two disjoint pair swaps.
"""
from pathlib import Path
import csv
import hashlib
import heapq
import json
import math
import time
import sys
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'data'
SPEED=1.2
HANDLE=8.0

def rows(name):
    with (OUT/name).open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))

def main(mode='daily'):
    started=time.perf_counter()
    nodes={}; edges=[]; slots={}
    xs=[3,7,11,15]; zs=[2,4,6,8,10,12,15]
    for ai,x in enumerate(xs,1):
        chain=[]
        for zi,z in enumerate(zs):
            key=f'N_A{ai}_Z{z}';nodes[key]=(x,z);chain.append(key)
            if 1<=zi<=5:slots[f'S_A{ai}_B{zi}']=key
        edges.extend(zip(chain,chain[1:]))
    nodes['N_FRONT_9']=(9,2);nodes['N_BUFFER']=(18,2);nodes['N_PACK']=(9,1.4)
    front=['N_A1_Z2','N_A2_Z2','N_FRONT_9','N_A3_Z2','N_A4_Z2']
    rear=[f'N_A{a}_Z15' for a in range(1,5)]
    edges.extend(zip(front,front[1:]));edges.extend(zip(rear,rear[1:]))
    edges += [('N_A4_Z2','N_BUFFER'),('N_FRONT_9','N_PACK')]
    graph={n:[] for n in nodes}
    for a,b in edges:
        d=math.dist(nodes[a],nodes[b]);graph[a].append((b,d));graph[b].append((a,d))
    assert len(nodes)==31 and len(edges)==33
    distances={}
    for source in nodes:
        ds={source:0.0};queue=[(0.0,source)]
        while queue:
            cost,node=heapq.heappop(queue)
            if cost>ds[node]+1e-10:continue
            for dest,weight in sorted(graph[node]):
                candidate=cost+weight
                if candidate<ds.get(dest,float('inf'))-1e-10:
                    ds[dest]=candidate;heapq.heappush(queue,(candidate,dest))
        assert len(ds)==31
        distances[source]=ds
    assert abs(distances['N_PACK'][slots['S_A1_B1']]-8.6)<1e-8
    cutoff=date(2011,10,3);window=cutoff-timedelta(days=28)
    master=rows('sku_master_20.csv');skus=sorted(r['sku_id'] for r in master)
    prior={sku:0 for sku in skus}
    for r in rows('daily_pick_visits_20sku.csv'):
        day=date.fromisoformat(r['date'])
        if window<=day<cutoff:prior[r['sku_id']]+=int(r['pick_visits'])
    ranked=sorted(skus,key=lambda sku:(-prior[sku],sku))
    ranked_slots=sorted(slots,key=lambda s:(distances['N_PACK'][slots[s]],s))
    baseline=dict(zip(ranked,ranked_slots))
    forecasts=defaultdict(dict)
    forecast_name='weekly_probe_predictions.csv' if mode=='weekly' else 'forecast_probe_predictions.csv'
    for r in rows(forecast_name):
        forecasts[r['date']][r['sku_id']]={'mean28':float(r['naive_mean28']),'hgb':float(r['model_hgb'])}
    baskets=defaultdict(lambda:defaultdict(set))
    for r in rows('test_basket_lines_20days.csv'):
        key=r['date']
        if mode=='weekly':
            d=date.fromisoformat(key);key=(d-timedelta(days=d.weekday())).isoformat()
        baskets[key][r['order_id']].add(r['sku_id'])
    assert len(forecasts)==(4 if mode=='weekly' else 20) and sum(len(x) for x in baskets.values())==749

    def surrogate(layout,pred):
        return sum(pred[s]*2*distances['N_PACK'][slots[layout[s]]]/SPEED for s in skus)

    def swap_cost(layout,a,b):
        aa=slots[layout[a]];bb=slots[layout[b]]
        def total(a_node,b_node):
            path=['N_PACK',a_node,'N_BUFFER',b_node,a_node,'N_BUFFER',b_node,'N_PACK']
            return sum(distances[x][y] for x,y in zip(path,path[1:]))
        walked=min(total(aa,bb),total(bb,aa))
        return walked/SPEED+6*HANDLE,walked

    def plan(pred):
        current=baseline.copy();used=set();pairs=[];reloc=0.;reloc_m=0.
        for _ in range(2):
            best=None;before=surrogate(current,pred)
            for a,b in combinations(skus,2):
                if a in used or b in used:continue
                cost,walked=swap_cost(current,a,b)
                candidate=current.copy();candidate[a],candidate[b]=candidate[b],candidate[a]
                gain=before-surrogate(candidate,pred)-cost
                if gain>1e-9 and (best is None or gain>best[0]+1e-9 or (abs(gain-best[0])<=1e-9 and (a,b)<best[1])):
                    best=(gain,(a,b),candidate,cost,walked)
            if best is None:break
            gain,pair,current,cost,walked=best
            used.update(pair);pairs.append(pair);reloc+=cost;reloc_m+=walked
        expected=surrogate(baseline,pred)-surrogate(current,pred)-reloc
        return current,pairs,reloc,reloc_m,expected

    def actual_routes(layout,orders):
        total=0.
        for order in orders.values():
            remaining=set(order);current='N_PACK'
            while remaining:
                sku=min(remaining,key=lambda s:(distances[current][slots[layout[s]]],s))
                target=slots[layout[sku]];total+=distances[current][target];current=target;remaining.remove(sku)
            total+=distances[current]['N_PACK']
        return total

    if mode=='promotion':
        day='2011-10-03'; promoted='22382'; multiplier=5.0
        methods={}
        for method in ['mean28','hgb']:
            pred={s:forecasts[day][s][method] for s in skus}
            original=pred[promoted];pred[promoted]*=multiplier
            layout,pairs,reloc,reloc_m,expected=plan(pred)
            methods[method]={'promoted_forecast_before':original,'promoted_forecast_after':pred[promoted],
                'pairs':pairs,'swaps':len(pairs),'candidate_assignment':layout,
                'relocation_labor_s':reloc,'relocation_walk_m':reloc_m,
                'baseline_single_stop_surrogate_s':surrogate(baseline,pred),
                'candidate_single_stop_surrogate_s_excluding_relocation':surrogate(layout,pred),
                'expected_net_surrogate_saved_s':expected}
        payload={'scenario_kind':'controlled synthetic planned-promotion input, NOT historical evaluation',
            'fixed_before_execution':{'date':day,'sku_id':promoted,'multiplier':multiplier,'other_sku_forecasts_unchanged':True},
            'baseline':'same frozen ABC28 2011-09-05 through2011-10-02','canonical_graph_nodes':31,'canonical_graph_edges':33,
            'methods':methods,'actual_historical_effect':None,'synthetic_orders_materialized':False,
            'limitations':'5x is a declared campaign assumption applied equally to both forecasts, not learned uplift and not actual historical demand. No throughput or actual savings claim; no parameter sweep.'}
        (OUT/'scenario_synthetic_promotion_probe.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
        print(json.dumps(payload,indent=2));return

    result=[];details={}
    for day in sorted(forecasts):
        base_m=actual_routes(baseline,baskets[day]);base_s=base_m/SPEED
        row={'date':day,'subset_orders':len(baskets[day]),'baseline_walk_m':base_m,'baseline_walk_s':base_s}
        details[day]={}
        for method in ['mean28','hgb']:
            pred={s:forecasts[day][s][method] for s in skus}
            layout,pairs,reloc,reloc_m,expected=plan(pred)
            actual_m=actual_routes(layout,baskets[day]);gross=base_s-actual_m/SPEED;net=gross-reloc
            # Diagnostic only: repeated-day assumption, not a fitted multi-day forecast or selected plan.
            repeats=[]
            for a,b in combinations(skus,2):
                candidate=baseline.copy();candidate[a],candidate[b]=candidate[b],candidate[a]
                gross_expected=surrogate(baseline,pred)-surrogate(candidate,pred)
                relocation,_=swap_cost(baseline,a,b)
                if gross_expected>1e-9:repeats.append((relocation/gross_expected,a,b,gross_expected,relocation))
            breakeven=min(repeats) if repeats else None
            row.update({f'{method}_swaps':len(pairs),f'{method}_actual_walk_m':actual_m,
                f'{method}_gross_walk_saved_s':gross,f'{method}_relocation_s':reloc,
                f'{method}_net_labor_proxy_saved_s':net,f'{method}_predicted_net_surrogate_saved_s':expected})
            details[day][method]={'pairs':pairs,'candidate_assignment':layout,'relocation_walk_m':reloc_m,
                'diagnostic_min_repeated_demand_days_to_cover_one_swap':breakeven[0] if breakeven else None,
                'diagnostic_pair_at_min_repeated_days':list(breakeven[1:3]) if breakeven else None,
                'diagnostic_warning':'Assumes exactly repeated forecast daily demand, not a validated multi-day forecast or operation plan.'}
        result.append(row)
    output_prefix='weekly_probe_decision' if mode=='weekly' else 'decision_probe'
    with (OUT/f'{output_prefix}_by_date.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    summary={}
    for method in ['mean28','hgb']:
        net=[r[f'{method}_net_labor_proxy_saved_s'] for r in result]
        summary[method]={
            'no_op_days':sum(r[f'{method}_swaps']==0 for r in result),
            'one_swap_days':sum(r[f'{method}_swaps']==1 for r in result),
            'two_swap_days':sum(r[f'{method}_swaps']==2 for r in result),
            'net_positive_days':sum(v>1e-8 for v in net),'net_negative_days':sum(v < -1e-8 for v in net),
            'total_gross_walking_saved_s':sum(r[f'{method}_gross_walk_saved_s'] for r in result),
            'total_relocation_s':sum(r[f'{method}_relocation_s'] for r in result),
            'total_net_labor_proxy_saved_s':sum(net),'best_day_net_s':max(net),'worst_day_net_s':min(net),
        }
    metrics={'probe_kind':'bounded travel/labor feasibility, NOT full app or 2-picker/packing-queue simulation',
        'created_date':'2026-11-06','canonical_graph':{'nodes':len(nodes),'edges':len(edges),'coordinates_xz_m':nodes,
            'undirected_edges':list(edges),'slots_to_pick_nodes':slots},
        'walk_speed_mps':SPEED,'relocation_handle_s':HANDLE,'relocation_take_place_count_per_swap':6,
        'baseline':'ABC ranked by 28 calendar-day visits 2011-09-05 inclusive to 2011-10-03 exclusive; fixed for all20days',
        'baseline_assignment':baseline,'baseline_past28_visits':prior,
        'planning':'at most2 disjoint swaps; greedy largest positive marginal reduction in predicted single-stop 2d objective including exact specified relocation walk+48s; no future basket use',
        'actual_evaluation':'NN by graph distance and sku_id on each retained historical subset basket, start/end pack; same algorithm all methods; quantity handling is identical so cancels in differences',
        'scenario_protocol':('4 independent Monday decisions, seven-calendar-day horizon with only Mon-Fri5operating-day demand; reset to ABC eachweek; not full Sunday-inclusive demand' if mode=='weekly' else '20 independent daily whatifs reset to frozen ABC; total is benchmark sum, not continuously operated month'),
        'day_count':len(result),'subset_order_count':sum(len(x) for x in baskets.values()),
        'baseline_total_walk_m':sum(r['baseline_walk_m'] for r in result),
        'baseline_total_walk_s':sum(r['baseline_walk_s'] for r in result),
        'methods':summary,'hgb_better_net_than_mean28_days':sum(r['hgb_net_labor_proxy_saved_s']>r['mean28_net_labor_proxy_saved_s']+1e-8 for r in result),
        'hgb_worse_net_than_mean28_days':sum(r['hgb_net_labor_proxy_saved_s']<r['mean28_net_labor_proxy_saved_s']-1e-8 for r in result),
        'plans_by_date':details,'limitations':['Only20SKU subset, not full original orders','No queues, collisions, throughput or service-level claims',
            'Planner single-stop surrogate may fail on multi-stop heldout baskets','Initial ABC could already be strong enough to make relocation unprofitable',
            'Relocation cost and speed are scenario assumptions, not field measurements'],
        'input_sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in [forecast_name,'daily_pick_visits_20sku.csv','test_basket_lines_20days.csv']},
        'elapsed_seconds':time.perf_counter()-started}
    (OUT/f'{output_prefix}_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:metrics[k] for k in ['day_count','subset_order_count','baseline_total_walk_m','methods','hgb_better_net_than_mean28_days','hgb_worse_net_than_mean28_days','elapsed_seconds']},indent=2))
    print('Nonzero plans:',[(r['date'],r['mean28_swaps'],r['hgb_swaps'],round(r['mean28_net_labor_proxy_saved_s'],2),round(r['hgb_net_labor_proxy_saved_s'],2)) for r in result if r['mean28_swaps'] or r['hgb_swaps']])

def weekly_forecast():
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder
    start=time.perf_counter()
    df=pd.read_csv(OUT/'daily_pick_visits_20sku.csv',parse_dates=['date']).sort_values(['sku_id','date']).reset_index(drop=True)
    dow=df['date'].dt.dayofweek;numeric=[]
    for lag in [1,2,7,14,28]:
        name=f'lag_{lag}';df[name]=df.groupby('sku_id').pick_visits.shift(lag);numeric.append(name)
    for w in [7,28]:
        name=f'mean_{w}';df[name]=df.groupby('sku_id').pick_visits.transform(lambda s:s.shift(1).rolling(w,min_periods=w).mean());numeric.append(name)
    df['dow']=dow;df['month']=df.date.dt.month;numeric+=['dow','month']
    df['weekday_observed']=df.pick_visits.where(dow<5,0)
    df['last7weekdaytotal']=df.groupby('sku_id').weekday_observed.transform(lambda s:s.shift(1).rolling(7,min_periods=7).sum())
    target=pd.Series(0.,index=df.index)
    for h in range(7):
        future=df.groupby('sku_id').pick_visits.shift(-h)
        target=target+future.where((dow+h)%7<5,0.)
    df['target']=target
    first=pd.read_csv(OUT/'sku_master_20.csv',parse_dates=['first_observed_sale']).set_index('sku_id').first_observed_sale
    adequate=df.date >= df.sku_id.map(first)+pd.Timedelta(days=28)
    train=df[(df.date+pd.Timedelta(days=6)<pd.Timestamp('2011-10-03')) & (dow<5) & adequate].dropna(subset=numeric+['target'])
    test_dates=pd.to_datetime(['2011-10-03','2011-10-10','2011-10-17','2011-10-24'])
    test=df[df.date.isin(test_dates)].copy()
    assert len(test)==80 and test.target.notna().all()
    features=numeric+['sku_id']
    transform=ColumnTransformer([('sku',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['sku_id']),('numbers','passthrough',numeric)])
    pipeline=make_pipeline(transform,HistGradientBoostingRegressor(loss='poisson',max_iter=150,max_leaf_nodes=15,learning_rate=.06,l2_regularization=1.,random_state=42))
    pipeline.fit(train[features],train.target)
    test['model_hgb']=np.maximum(0.,pipeline.predict(test[features]))
    test['naive_mean28']=test.mean_28*5.
    test['naive_last7weekday_total']=test.last7weekdaytotal
    test['pick_visits']=test.target
    test[['date','sku_id','pick_visits','naive_mean28','naive_last7weekday_total','model_hgb']].to_csv(OUT/'weekly_probe_predictions.csv',index=False)
    metrics={}
    for method in ['naive_mean28','naive_last7weekday_total','model_hgb']:
        e=test[method]-test.target;den=float(test.target.sum())
        metrics[method]={'mae':float(e.abs().mean()),'wape':float(e.abs().sum()/den),'bias':float(e.sum()/den)}
    payload={'kind':'exploratory5weekday-window forecast; not a full7day demand forecast','train_rows':len(train),'test_rows':len(test),
        'test_origins':[d.strftime('%Y-%m-%d') for d in test_dates],
        'target':'sum visits t..t+6 for Mon-Fri dates only; Sunday historical records retained in lag inputs',
        'leakage_rule':'all train target window ends strictly before2011-10-03; all test features earlier than ownMonday; model fitted once, no test tuning',
        'training_origins':'all eligible Monday-Friday origins, each future7calendar-day window has5weekday target dates',
        'metrics':metrics,'total_test_visits':float(test.target.sum()),'elapsed_seconds':time.perf_counter()-start}
    assert int(test.target.sum())==1745
    (OUT/'weekly_probe_forecast_metrics.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload,indent=2))

if __name__=='__main__':
    if '--weekly-forecast' in sys.argv:weekly_forecast()
    elif '--weekly' in sys.argv:main('weekly')
    elif '--promotion' in sys.argv:main('promotion')
    else:main()
