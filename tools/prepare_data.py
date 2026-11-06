"""Read official UCI workbook, export anonymous aggregate Qoyma scenario data.
No source workbook changes. Optional --model-only uses existing aggregate CSVs.
"""
from pathlib import Path
import hashlib
import json
import sys
import time
import numpy as np
import pandas as pd

import argparse
parser = argparse.ArgumentParser(description='UCI502 aggregate and CPU forecast feasibility probe')
parser.add_argument('--source', type=Path, help='Official online_retail_II.xlsx')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]/'data')
parser.add_argument('--model-only', action='store_true')
args = parser.parse_args()
OUT = args.output
SRC = args.source
if not args.model_only and SRC is None:
    parser.error('--source XLSX is required unless --model-only')
CUTOFF = pd.Timestamp('2011-10-03')

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

def probe():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = pd.read_excel(SRC, sheet_name=None, engine='openpyxl')
    print('Workbook loaded', {k: len(v) for k,v in sheets.items()}, flush=True)
    sheet_info = []
    frames = []
    for name, frame in sheets.items():
        sheet_info.append({'name':name,'rows':len(frame),'columns':list(frame.columns)})
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    original_columns = list(raw.columns)
    schema_map = {'InvoiceNo':'Invoice','UnitPrice':'Price','CustomerID':'Customer ID'}
    raw = raw.rename(columns=schema_map)
    raw['Invoice'] = raw['Invoice'].astype('string').str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
    raw['StockCode'] = raw['StockCode'].astype('string').str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
    raw['InvoiceDate'] = pd.to_datetime(raw['InvoiceDate'], errors='coerce')
    raw['Quantity'] = pd.to_numeric(raw['Quantity'], errors='coerce')
    raw['Price'] = pd.to_numeric(raw['Price'], errors='coerce')
    raw['date'] = raw['InvoiceDate'].dt.normalize()
    duplicate_cols = [c for c in ['Invoice','StockCode','Description','Quantity','InvoiceDate','Price','Customer ID','Country'] if c in raw]
    exact_dup = raw.duplicated(subset=duplicate_cols, keep='first')
    cancelled = raw['Invoice'].str.startswith('C', na=False)
    physical = raw['StockCode'].str.fullmatch(r'\d{5}[A-Z]?', na=False)
    positive = (raw['Quantity'] > 0) & (raw['Price'] > 0) & raw['InvoiceDate'].notna() & ~cancelled
    clean = raw.loc[positive & physical & ~exact_dup].copy()
    # Each invoice-SKU pair represents one model pick visit; original quantities remain handling load.
    visits = clean.groupby(['Invoice','StockCode'], sort=False, as_index=False).agg(
        timestamp=('InvoiceDate','min'),quantity=('Quantity','sum'),line_count=('Quantity','size'))
    visits['date'] = visits['timestamp'].dt.normalize()
    historical = visits[visits['date'] < CUTOFF]
    frequency = historical.groupby('StockCode')['Invoice'].nunique().sort_values(ascending=False, kind='mergesort')
    selected = frequency.head(20).index.tolist()
    train_descriptions = clean[(clean['date'] < CUTOFF) & clean['StockCode'].isin(selected)]
    def label(group):
        values = group.dropna().astype(str).str.strip()
        counts = values.value_counts()
        return counts.index[0] if len(counts) else ''
    descriptions = train_descriptions.groupby('StockCode')['Description'].agg(label).to_dict()
    first_sales = historical.groupby('StockCode')['date'].min().to_dict()
    # Days are fixed from all eligible positive merchandise visits, before restricting assortment.
    observed = pd.DatetimeIndex(sorted(visits.loc[visits['date'] >= CUTOFF,'date'].unique()))
    test_days = observed[observed.dayofweek < 5][:20]
    if len(test_days) != 20:
        raise ValueError('Need twenty observed weekdays')
    panel_end = test_days.max()
    dates = pd.date_range(visits['date'].min(), panel_end, freq='D')
    selected_visits = visits[visits['StockCode'].isin(selected) & (visits['date'] <= panel_end)].copy()
    daily = selected_visits.groupby(['StockCode','date'],as_index=False).agg(
        pick_visits=('Invoice','nunique'),units=('quantity','sum'),source_lines=('line_count','sum'))
    grid = pd.MultiIndex.from_product([selected,dates],names=['StockCode','date']).to_frame(index=False)
    daily = grid.merge(daily,on=['StockCode','date'],how='left')
    for col in ['pick_visits','units','source_lines']:
        daily[col] = daily[col].fillna(0).astype('int64')
    daily['sku_id'] = daily['StockCode']
    daily['is_train_date'] = daily['date'] < CUTOFF
    daily['is_test_date'] = daily['date'].isin(test_days)
    daily['is_sunday'] = daily['date'].dt.dayofweek == 6
    daily['after_first_observation'] = daily.apply(lambda row: row['date'] >= first_sales[row['StockCode']],axis=1)
    daily = daily.drop(columns='StockCode').sort_values(['sku_id','date'])
    daily['date'] = daily['date'].dt.strftime('%Y-%m-%d')
    daily.to_csv(OUT/'daily_pick_visits_20sku.csv', index=False)
    sku_table = pd.DataFrame([{'sku_id':s,'description':descriptions.get(s,''),
        'train_pick_visits':int(frequency[s]),'first_observed_sale':first_sales[s].strftime('%Y-%m-%d'),
        'selection_rank':i+1} for i,s in enumerate(selected)])
    sku_table.to_csv(OUT/'sku_master_20.csv',index=False)
    test_visits = visits[visits['date'].isin(test_days)]
    chosen_test = test_visits[test_visits['StockCode'].isin(selected)].copy()
    order_times = chosen_test.groupby('Invoice')['timestamp'].min().sort_values(kind='mergesort')
    anon = {str(k):f'ORD-{i+1:05d}' for i,k in enumerate(order_times.index)}
    chosen_test['order_id'] = chosen_test['Invoice'].astype(str).map(anon)
    chosen_test['sku_id'] = chosen_test['StockCode']
    chosen_test['invoice_timestamp_replay'] = chosen_test['Invoice'].map(order_times).dt.strftime('%Y-%m-%dT%H:%M:%S')
    chosen_test['date'] = chosen_test['date'].dt.strftime('%Y-%m-%d')
    chosen_test[['order_id','sku_id','quantity','line_count','invoice_timestamp_replay','date']].sort_values(
        ['invoice_timestamp_replay','order_id','sku_id']).to_csv(OUT/'test_basket_lines_20days.csv', index=False)
    pd.DataFrame({'date':test_days.strftime('%Y-%m-%d')}).to_csv(OUT/'test_dates.csv',index=False)
    invoice_times = clean.groupby('Invoice')['InvoiceDate'].nunique()
    coverage = {
        'test_all_physical_pick_visits':len(test_visits),
        'test_selected_pick_visits':len(chosen_test),
        'test_pick_visit_coverage':len(chosen_test)/len(test_visits),
        'test_all_physical_invoices':int(test_visits['Invoice'].nunique()),
        'test_invoices_touching_selection':int(chosen_test['Invoice'].nunique()),
        'test_invoice_touch_coverage':chosen_test['Invoice'].nunique()/test_visits['Invoice'].nunique(),
        'test_invoices_completely_within_selection':int(sum(set(g['StockCode']).issubset(set(selected)) for _,g in test_visits.groupby('Invoice'))),
        'test_selected_units':float(chosen_test['quantity'].sum()),
        'test_all_physical_units':float(test_visits['quantity'].sum()),
    }
    manifest = {
        'created_date':'2026-11-06','source':{'uci_id':502,'url':'https://archive.ics.uci.edu/dataset/502/online+retail+ii',
            'download_url':'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip',
            'xlsx_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'license':'CC BY 4.0',
            'attribution':'Daqing Chen, Online Retail II, UCI Machine Learning Repository, DOI 10.24432/C5CG6D'},
        'sheets':sheet_info,'raw_rows':len(raw),'raw_columns':original_columns,
        'raw_date_min':raw['InvoiceDate'].min(),'raw_date_max':raw['InvoiceDate'].max(),
        'rows_missing_customer_id':int(raw['Customer ID'].isna().sum()) if 'Customer ID' in raw else None,
        'exact_duplicate_rows':int(exact_dup.sum()),'cancellation_prefix_rows':int(cancelled.sum()),
        'nonpositive_quantity_rows':int((raw['Quantity'] <= 0).sum()),'nonpositive_price_rows':int((raw['Price'] <= 0).sum()),
        'positive_nonmerchandise_pattern_rows':int((positive & ~physical).sum()),
        'clean_positive_merchandise_rows':len(clean),'unique_invoice_sku_visits':len(visits),
        'invoices_with_multiple_timestamps':int((invoice_times > 1).sum()),
        'raw_sunday_rows':int((raw['date'].dt.dayofweek == 6).sum()),
        'raw_dayofweek_counts':raw['date'].dt.dayofweek.value_counts().sort_index().to_dict(),
        'cutoff_exclusive':'2011-10-03','selection_rule':'top20 by distinct positive-merchandise invoice-SKU visits strictly before cutoff; tie stable',
        'merchandise_rule':'StockCode fullmatch 5 digits optionally followed by one letter; Quantity>0; Price>0; no C invoice; earliest timestamp per invoice-SKU',
        'duplicate_policy':'exact normalized source row duplicates removed before quantities aggregated; visit target collapses invoice-SKU',
        'test_dates':test_days.strftime('%Y-%m-%d').tolist(),
        'test_selection_rule':'first20 observed Monday-Friday transaction dates at/after cutoff, determined from all eligible merchandise before selecting20SKU',
        'zero_policy':'missing calendar dates filled0 observed invoice visits; zero is not proof of zero latent demand or stock availability',
        'privacy':'No Customer ID or original Invoice exported; pseudonymous order_id only. Product codes/descriptions are public source merchandise.',
        'provenance':'Historical UK online gift-retailer invoices; operational warehouse, geometry, picker timings and arrivals interpretation are scenario assumptions.',
        'scope':'20-SKU assortment slice; omitted items are not simulated. Invoice timestamps are replay timestamps, not verified warehouse-arrival times.',
        'coverage':coverage,'selected_skus':selected,'elapsed_seconds':time.perf_counter()-started,
    }
    dump(OUT/'data_manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=False,default=str,indent=2),flush=True)
    print(sku_table.to_string(index=False),flush=True)

def model():
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder
    started=time.perf_counter()
    daily=pd.read_csv(OUT/'daily_pick_visits_20sku.csv',parse_dates=['date'])
    daily=daily.sort_values(['sku_id','date']).reset_index(drop=True)
    numeric=[]
    for lag in [1,2,7,14,28]:
        col=f'lag_{lag}';daily[col]=daily.groupby('sku_id')['pick_visits'].shift(lag);numeric.append(col)
    for window in [7,28]:
        col=f'mean_{window}';daily[col]=daily.groupby('sku_id')['pick_visits'].transform(lambda s:s.shift(1).rolling(window,min_periods=window).mean());numeric.append(col)
    daily['dow']=daily['date'].dt.dayofweek;daily['month']=daily['date'].dt.month
    numeric += ['dow','month']
    first=pd.read_csv(OUT/'sku_master_20.csv',parse_dates=['first_observed_sale']).set_index('sku_id')['first_observed_sale']
    daily['sufficient_sku_history']=daily['date'] >= daily['sku_id'].map(first)+pd.Timedelta(days=28)
    frame=daily.dropna(subset=numeric).copy()
    features=numeric+['sku_id']
    training=frame[(frame['date']<CUTOFF) & (frame['dow']<5) & frame['sufficient_sku_history']]
    test=frame[frame['is_test_date']].copy()
    transform=ColumnTransformer([('sku',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['sku_id']),('numbers','passthrough',numeric)])
    estimator=HistGradientBoostingRegressor(loss='poisson',max_iter=150,max_leaf_nodes=15,learning_rate=.06,l2_regularization=1.,random_state=42)
    pipeline=make_pipeline(transform,estimator)
    pipeline.fit(training[features],training['pick_visits'])
    test['model_hgb']=np.maximum(0.,pipeline.predict(test[features]))
    test['naive_lag7']=test['lag_7']
    test['naive_mean28']=test['mean_28']
    # 28-day means mix observed weekdays with Sunday transactions; weekday-adjusted baseline from past4 same weekdays.
    same=[]
    for lag in [7,14,21,28]:same.append(daily.groupby('sku_id')['pick_visits'].shift(lag))
    daily['naive_sameweekday4']=pd.concat(same,axis=1).mean(axis=1)
    test=test.merge(daily[['sku_id','date','naive_sameweekday4']],on=['sku_id','date'])
    results={}
    for name in ['naive_lag7','naive_mean28','naive_sameweekday4','model_hgb']:
        err=test[name]-test['pick_visits']; actual=float(test['pick_visits'].sum())
        results[name]={'mae':float(err.abs().mean()),'wape':float(err.abs().sum()/actual),'bias':float(err.sum()/actual)}
    test[['sku_id','date','pick_visits','naive_lag7','naive_mean28','naive_sameweekday4','model_hgb']].to_csv(OUT/'forecast_probe_predictions.csv',index=False)
    result={'target':'unique invoice-SKU visits per observed day','train_rows':len(training),'test_rows':len(test),
        'cutoff_exclusive':'2011-10-03','models':'fixed prespecified HGB Poisson; no hyperparameter search; fixed model fit before test',
        'test_protocol':'one-day-ahead rolling observations: lag features use only dates earlier than each forecast date, including earlier test/calendar days; no retraining',
        'selection':'20SKU selected before cutoff. No forecast ranking selection based on test.',
        'metrics':results,'elapsed_seconds':time.perf_counter()-started,
        'limitations':'Exploratory forecast probe, not completed slotting evaluation. Weekdays scored, actual historical weekend transactions remain valid lag inputs. No real warehouse savings claim.'}
    dump(OUT/'forecast_probe_metrics.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    if '--model-only' in sys.argv:model()
    else:probe()
