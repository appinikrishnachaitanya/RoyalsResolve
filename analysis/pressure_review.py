"""Create blinded pressure-review sheets and audit completed human labels."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score,balanced_accuracy_score
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/private/pressure_review'
SEED=8914

def partition(mid):
    return 'evaluation' if int(hashlib.sha256(f'{SEED}:{mid}'.encode()).hexdigest()[:8],16)%4==0 else 'development'

def build():
    for existing in OUT.glob('*_reviewer_*.csv'):
        if pd.read_csv(existing).reviewer_id.notna().any():raise ValueError('Completed reviewer work exists; refusing to overwrite it')
    d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
    d['partition']=d.match_id.map(partition)
    d['case_group']=np.select([
        d.innings.eq(2)&d.remaining.le(6)&d.need.gt(36),
        d.innings.eq(2)&d.remaining.le(12)&d.need.between(1,18),
        d.innings.eq(2)&d.remaining.ge(24)&d.rrr.lt(6),
        d.innings.eq(1)&d.prior_wickets.ge(2),
        d.innings.eq(1)&d.remaining.le(30),
        d.remaining.ge(108)],['very_difficult_chase','close_finish','low_required_rate','recent_wickets','first_innings_late','opening'],default='other')
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for split in ['development','evaluation']:
        chosen=[];seen=set()
        for _,g in d[d.partition.eq(split)].groupby('case_group'):
            for _,r in g.sample(frac=1,random_state=SEED).iterrows():
                # At most one delivery per match, preventing same-match clue leakage.
                if r.match_id in seen:continue
                chosen.append(r);seen.add(r.match_id)
                if sum(x.case_group==r.case_group for x in chosen)>=8:break
        sample=pd.DataFrame(chosen).sort_values(['match_id','innings','innings_ball_num'])
        rows=[]
        for r in sample.itertuples():
            case=hashlib.sha256(f'{r.match_id}:{r.innings}:{r.innings_ball_num}'.encode()).hexdigest()[:12]
            rows.append(dict(case_id=case,format='IPL' if r.is_ipl else 'T20I',innings=r.innings,score_before=r.score,wickets_lost=r.lost,legal_balls_left=r.remaining,runs_needed=r.need if r.innings==2 else '',required_rate=round(r.rrr,2) if r.innings==2 else '',wickets_previous_six_balls=r.prior_wickets,dots_previous_six_balls=r.prior_dots,difficulty_0_to_2='',stakes_0_to_2='',reviewer_id='',reason=''))
            manifest.append(dict(case_id=case,partition=split,match_id=int(r.match_id),case_group=r.case_group,operational_pressure=bool(r.baseline_pressure)))
        sheet=pd.DataFrame(rows).sample(frac=1,random_state=SEED)
        for reviewer in ['A','B']:sheet.to_csv(OUT/f'{split}_reviewer_{reviewer}.csv',index=False)
    pd.DataFrame(manifest).to_csv(OUT/'private_key.csv',index=False)
    summary={'seed':SEED,'source_sha256':hashlib.sha256((ROOT/'artifacts/private/evaluated.parquet').read_bytes()).hexdigest(),'cases':pd.DataFrame(manifest).partition.value_counts().to_dict(),'warning':'Retrospective split: all source seasons have previously been inspected. This is not a pristine prospective holdout.'}
    (OUT/'manifest.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2));print('Private review sheets:',OUT)

def evaluate(split):
    a=pd.read_csv(OUT/f'{split}_reviewer_A.csv');b=pd.read_csv(OUT/f'{split}_reviewer_B.csv')
    for sheet in [a,b]:
        if sheet.case_id.duplicated().any():raise ValueError('Duplicate review cases')
        if sheet.reviewer_id.isna().any():raise ValueError('Independent reviewer IDs required')
        for col in ['difficulty_0_to_2','stakes_0_to_2']:
            if not sheet[col].isin([0,1,2]).all():raise ValueError('All cases need human labels 0, 1 or 2')
    z=a.merge(b,on='case_id',suffixes=('_a','_b'),validate='one_to_one')
    if len(z)!=len(a) or len(z)!=len(b):raise ValueError('Review sheets do not cover the same cases')
    if set(a.reviewer_id)&set(b.reviewer_id):raise ValueError('Reviewers must be independent people')
    key=pd.read_csv(OUT/'private_key.csv');z=z.merge(key,on='case_id',validate='one_to_one')
    result={'partition':split,'cases':len(z),'axes':{}}
    for axis in ['difficulty','stakes']:
        ca=axis+'_0_to_2_a';cb=axis+'_0_to_2_b';agree=z[ca].eq(z[cb])
        target=z.loc[agree,ca].eq(2);pred=z.loc[agree,'operational_pressure']
        result['axes'][axis]={'agreement':float(agree.mean()),'weighted_kappa':float(cohen_kappa_score(z[ca],z[cb],weights='quadratic')),'consensus_cases':int(agree.sum()),'operational_balanced_accuracy_on_consensus':float(balanced_accuracy_score(target,pred)) if target.nunique()==2 else None}
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evaluate',choices=['development','evaluation']);args=p.parse_args()
    if args.evaluate:evaluate(args.evaluate)
    else:build()
