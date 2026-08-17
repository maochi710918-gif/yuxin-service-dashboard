# -*- coding: utf-8 -*-
"""
Extract a minimal, PII-scrubbed dataset from 零件DMS資料庫報表.xlsx for a live,
client-side-computed KPI tool. License plates are replaced with synthetic IDs
(V00001...) that stay consistent across all tables so joins/dedup still work,
but the real plate number, customer name, phone, email, address etc. are never
shipped. Depot names, model codes, categories, and amounts are not PII and are
kept as-is.
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

PATH = r'C:\Users\ES\OneDrive\桌面\AI參照\零件儀錶板\零件DMS資料庫報表.xlsx'
OUT = r'C:\Users\ES\AppData\Local\Temp\claude\C--Users-ES\a1df95fb-1284-4f44-8e80-159edf8b91cf\scratchpad\yuxin-service-dashboard\docs\parts-kpi-data.json'

def classify(p):
    p = str(p).strip()
    L = len(p)
    dash = p.find('-')
    dash1 = dash + 1 if dash >= 0 else -1
    if p[:1] == '軍':
        return 'army'
    if L == 6 and dash1 == -1:
        return 'rental'
    cond2 = (
        (L == 8 and dash1 == 4 and p[:1] == 'R') or
        (dash1 == 3 and len(p) > 1 and p[0] == p[1]) or
        (dash1 == 5 and len(p) >= 6 and p[-1] == p[5])
    )
    if cond2:
        return 'rental'
    if L == 6 and dash1 in (3, 4):
        return 'taxi'
    return 'general'

KW_MAP = {
    '劃線碟': [r'劃線碟'],
    '電瓶樁頭': [r'椿頭', r'樁頭'],
    '冷煤強化劑': [r'冷煤強化劑'],
    '冷氣系統養護': [r'冷氣系統'],
    '鈦晶內裝': [r'鈦晶.*內裝'],
    '鈦晶外觀': [r'鈦晶.*外觀'],
    '空力雨刷': [r'空力雨刷'],
    '電動窗養護': [r'電動窗'],
    '碟式煞車潤滑': [r'卡鉗.{0,2}潤滑', r'煞車.*(潤滑|滑銷)'],
}
def classify_item(desc):
    desc = str(desc)
    for cat, pats in KW_MAP.items():
        if any(re.search(p, desc) for p in pats):
            return cat
    return None

# ---------------- plate -> synthetic id ----------------
plate_map = {}
def pid(plate):
    p = str(plate).strip()
    if not p or p == 'nan':
        return None
    if p not in plate_map:
        plate_map[p] = f'V{len(plate_map)+1:05d}'
    return plate_map[p]

print('Loading sheets...')
teiho = pd.read_excel(PATH, sheet_name='定保台數', header=14)
nvs = pd.read_excel(PATH, sheet_name='NVS明細', header=17)
addback = pd.read_excel(PATH, sheet_name='加價購或零件換購轉回原價格', header=1)
oil = pd.read_excel(PATH, sheet_name='油品銷售明細', header=17)
c12t32_whitelist = pd.read_excel(PATH, sheet_name='c12t32對象車型規格選配', header=5)
c12t32_bridge = pd.read_excel(PATH, sheet_name='比對c12t32對象車型規格選配', header=18)
t33_project = pd.read_excel(PATH, sheet_name='L34&T33專案車型', header=0)
tsale = pd.read_excel(PATH, sheet_name='輪胎&電瓶銷售明細', header=16)
tb = pd.read_excel(PATH, sheet_name='輪胎&電瓶有費台數', header=11)
targets = pd.read_excel(PATH, sheet_name='六大各廠目標', header=0)
parts6 = pd.read_excel(PATH, sheet_name='六大銷售明細(零件)', header=17)
labor6 = pd.read_excel(PATH, sheet_name='六大銷售明細(工資)', header=17)

# ---------------- 1. vehicles (定保台數, NISSAN only) ----------------
teiho['brand_ok'] = teiho['品牌'].astype(str).str.strip().str.upper() == 'NISSAN'
nissan = teiho[teiho['brand_ok']].copy()
nissan['pid'] = nissan['牌照號碼'].apply(pid)
nissan['plate_cls'] = nissan['牌照號碼'].apply(classify)
nissan['is_ev'] = nissan['牌照號碼'].astype(str).str.strip().str.startswith('E')
nissan['owner_len'] = nissan['車主'].astype(str).str.len()
nissan['is_company'] = (nissan['plate_cls'] == 'general') & (~nissan['is_ev']) & (nissan['owner_len'] > 4)

# C12/T32 whitelist eligibility
wl_set = set(c12t32_whitelist['合併'].dropna().astype(str).str.strip())
bridge = c12t32_bridge.copy()
bridge['pid'] = bridge['牌照號碼'].apply(pid)
bridge['combined'] = (bridge['車型代碼'].astype(str).str.strip() +
                       bridge['規格'].astype(str).str.strip() +
                       bridge['選配碼'].astype(str).str.strip())
bridge['eligible'] = bridge['combined'].isin(wl_set)
elig_by_pid = bridge.groupby('pid')['eligible'].any().to_dict()

# T33 project exclusion
t33_regs = set(t33_project['regono'].dropna().astype(str).str.strip())

vehicles = []
for _, r in nissan.iterrows():
    vid = r['pid']
    if pd.isna(vid):
        continue
    model = str(r['車型代碼']).strip().upper()
    plate_raw = str(r['牌照號碼']).strip()
    rec = {
        'id': vid,
        'model': model,
        'depot': str(r['服務廠']).strip(),
        'cls': r['plate_cls'],
        'ev': bool(r['is_ev']),
        'company': bool(r['is_company']),
    }
    if model[:3] in ('C12', 'T32'):
        rec['c12t32_ok'] = bool(elig_by_pid.get(vid, False))
    if model[:3] == 'T33':
        rec['t33_excl'] = plate_raw in t33_regs
    vehicles.append(rec)

print('vehicles:', len(vehicles))

# ---------------- 2. NVS rows (price resolved, tax-exclusive) ----------------
addback_map = dict(zip(addback['件號'].astype(str).str.strip(), addback['金額']))
def resolve_nvs(row):
    pt = row['價別']
    if pt in ('特價', '理賠價', '售價'):
        return row['金額']
    if pt in ('加價購', '零件換購'):
        return addback_map.get(str(row['項目']).strip())
    return None

nvs['pid'] = nvs['牌照號碼'].apply(pid)
nvs['resolved'] = nvs.apply(resolve_nvs, axis=1)
nvs_rows = [
    {'id': row['pid'], 'depot': str(row['服務廠']).strip(), 'amt': round(float(row['resolved']), 2)}
    for _, row in nvs.iterrows()
    if pd.notna(row['pid']) and pd.notna(row['resolved'])
]
print('nvs_rows:', len(nvs_rows))

# ---------------- 3. oil hits (S package part codes) ----------------
S_PART_CODES = {'101210W30S23','101225W30S23','101220W20123','101210W20C23','101220530123'}
oil['pid'] = oil['牌照號碼'].apply(pid)
oil_hits = [
    {'id': row['pid']}
    for _, row in oil.iterrows()
    if str(row['項目']).strip() in S_PART_CODES and pd.notna(row['pid'])
]
print('oil_hits:', len(oil_hits))

# ---------------- 4. tire/battery sales (self-pay, net qty > 0) ----------------
tsale['pid'] = tsale['牌照號碼'].apply(pid)
tsale['net_qty'] = tsale['數量'].fillna(0) - tsale['退庫'].fillna(0)
ts = tsale[(tsale['工單類別'] == '自費') & (tsale['零件分類'].isin(['輪胎', '電瓶'])) & (tsale['net_qty'] > 0)]
tb_sales_rows = [
    {'id': row['pid'], 'cat': row['零件分類']}
    for _, row in ts.iterrows() if pd.notna(row['pid'])
]
print('tb_sales_rows:', len(tb_sales_rows))

# ---------------- 5. tire/battery denominator pool ----------------
tb['pid'] = tb['牌照號碼'].apply(pid)
age_col = [c for c in tb.columns if '車齡' in str(c)][0]
tb['is_selfpay'] = tb['工單類別'].astype(str).str.contains('自費', na=False)
tb_pool_rows = [
    {
        'id': row['pid'], 'model': str(row['車型代碼']).strip().upper(),
        'age': (None if pd.isna(row[age_col]) else float(row[age_col])),
        'mi': (None if pd.isna(row['本次進廠里程']) else float(row['本次進廠里程'])),
        'sp': bool(row['is_selfpay']),
        'depot': str(row['服務廠']).strip(),
    }
    for _, row in tb.iterrows() if pd.notna(row['pid'])
]
print('tb_pool_rows:', len(tb_pool_rows))

# ---------------- 6. six-category sales (parts + labor, classified) ----------------
def six_cat_rows(df):
    out = []
    for _, row in df.iterrows():
        cat = classify_item(row['說明'])
        if cat is None:
            continue
        amt = row['金額']
        cost = row['成本']
        if pd.isna(amt):
            continue
        out.append({
            'depot': str(row['服務廠']).strip(),
            'cat': cat,
            'amt': round(float(amt), 2),
            'cost': (0 if pd.isna(cost) else round(float(cost), 2)),
        })
    return out

six_rows = six_cat_rows(parts6) + six_cat_rows(labor6)
print('six_rows:', len(six_rows))

# ---------------- 7. six-category monthly targets (annual/12) ----------------
row_labels = targets.iloc[:, 1].astype(str).tolist()
def target_row(label):
    idx = row_labels.index(label)
    return targets.iloc[idx, 2:11].tolist()

cats9 = ['劃線碟','電瓶樁頭','冷煤強化劑','冷氣系統養護','鈦晶內裝','鈦晶外觀','空力雨刷','電動窗養護','碟式煞車潤滑']
rev_annual = target_row('營收目標(含工)')
profit_annual = target_row('獲利目標(含工)')
six_targets = {
    cats9[i]: {
        'revM': round(float(rev_annual[i]) / 12, 2),
        'profitM': round(float(profit_annual[i]) / 12, 2),
    }
    for i in range(9)
}

# ---------------- 8. depot list ----------------
depots = sorted(set(
    [v['depot'] for v in vehicles] +
    [r['depot'] for r in nvs_rows] +
    [r['depot'] for r in six_rows]
) - {'', 'nan', 'None'})

data = {
    'meta': {
        'period': '2026-08', 'periodLabel': '2026-08-01 ~ 08-31',
        'dealer': '裕信汽車', 'brand': 'NISSAN',
        'vehicleCount': len(vehicles),
    },
    'depots': depots,
    'vehicles': vehicles,
    'nvsRows': nvs_rows,
    'oilHits': oil_hits,
    'tbSalesRows': tb_sales_rows,
    'tbPoolRows': tb_pool_rows,
    'sixRows': six_rows,
    'sixTargets': six_targets,
}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

import os
print('Written:', OUT, ' size(KB)=', round(os.path.getsize(OUT)/1024, 1))
print('depots:', depots)
