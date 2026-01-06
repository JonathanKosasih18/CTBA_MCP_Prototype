import re, csv, io
from difflib import SequenceMatcher
p='real_data.sql'
s=open(p,encoding='utf-8',errors='ignore').read()

def extract_rows(table):
    pat=re.compile(r"INSERT INTO `"+re.escape(table)+r"`.*?VALUES\s*(\(.+?\));",re.S)
    rows=[]
    for m in pat.finditer(s):
        block=m.group(1)
        parts=re.split(r"\),\s*\(", block)
        for i,part in enumerate(parts):
            part=part.strip()
            if i==0 and part.startswith('('):
                part=part[1:]
            if i==len(parts)-1 and part.endswith(');'):
                part=part[:-2]
            if part.endswith(')'):
                part=part[:-1]
            rows.append(part)
    return rows

clinic_rows=extract_rows('clinics')
customer_rows=extract_rows('customers')

# parse tuple helper
import csv, io

def parse_tuple(t):
    f=io.StringIO(t)
    reader=csv.reader(f, delimiter=',', quotechar="'", escapechar='\\')
    row=next(reader)
    return [c.strip() for c in row]

# build dicts
clinics=[]
for r in clinic_rows:
    try:
        cols=parse_tuple(r)
    except Exception:
        continue
    if len(cols)>11:
        cid=cols[0].strip()
        clinicname=(cols[2].strip("' ") if cols[2]!="NULL" else '').strip()
        custcode=(cols[11].strip("' ") if cols[11]!="NULL" else '').strip()
        clinics.append((cid,custcode,clinicname))

customers={}
for r in customer_rows:
    try:
        cols=parse_tuple(r)
    except Exception:
        continue
    if len(cols)>2:
        cid=cols[0].strip()
        custname=(cols[2].strip("' ") if cols[2]!="NULL" else '').strip()
        customers[cid]=custname

# normalize helper
import re

def norm(s):
    s=(s or '').lower()
    s=re.sub(r"\b(dr|drg|drg\.|dr\.|mrs\.|mr\.|sp\.|sp)\b","",s)
    s=re.sub(r"[^0-9a-z ]+"," ",s)
    s=re.sub(r"\s+"," ",s).strip()
    return s

# compute similarities
results=[]
all_customers_list=[(k,customers[k]) for k in customers]
for cid,custcode,clinicname in clinics:
    clinic_norm=norm(clinicname)
    mapped_name=customers.get(custcode) if custcode else None
    mapped_norm=norm(mapped_name) if mapped_name else ''
    best=(None, None, 0.0)
    if mapped_name:
        score=SequenceMatcher(None, clinic_norm, mapped_norm).ratio()
        best=(custcode, mapped_name, score)
    for k,name in all_customers_list:
        nm=norm(name)
        if not nm:
            continue
        score=SequenceMatcher(None, clinic_norm, nm).ratio()
        if score>best[2]:
            best=(k,name,score)
    results.append((cid,custcode,clinicname,best[0],best[1],best[2]))

# sort by score desc
results_sorted=sorted(results, key=lambda x: x[5], reverse=True)

# filter high-confidence matches (score>=0.75)
high=[r for r in results_sorted if r[5]>=0.75]
medium=[r for r in results_sorted if 0.6<=r[5]<0.75]

# print summary and top examples
print('clinics parsed:', len(clinics))
print('customers parsed:', len(customers))
print('high-confidence matches (>=0.75):', len(high))
print('medium-confidence matches (0.6-0.75):', len(medium))
print('\nTop 30 fuzzy matches (clinic_id | clinicname | custcode -> candidate_id | custname | score):')
for r in results_sorted[:30]:
    print(r[0],'|',r[2],'|',r[1],'->',r[3],'|',r[4],'|',round(r[5],3))

# examples of unmapped custcode with good candidate
unmapped_candidates=[r for r in results_sorted if (not r[1] or r[1] not in customers) and r[5]>=0.6]
print('\nExample unmapped clinics with good candidate (>=0.6):')
for r in unmapped_candidates[:20]:
    print(r[0],'|',r[2],'| custcode=',r[1],'=> candidate id',r[3],'name',r[4],'score',round(r[5],3))

# write small CSV of top matches
with open('fuzzy_matches_top50.csv','w',encoding='utf-8',newline='') as f:
    w=csv.writer(f)
    w.writerow(['clinic_id','custcode','clinicname','candidate_customer_id','candidate_name','score'])
    for r in results_sorted[:50]:
        w.writerow([r[0],r[1],r[2],r[3],r[4],round(r[5],3)])

print('\nWrote fuzzy_matches_top50.csv')
