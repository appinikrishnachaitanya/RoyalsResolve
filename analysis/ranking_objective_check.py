"""Compare ranking objectives on common players and common future outcomes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from score_validation import estimate_lift
ROOT=Path(__file__).resolve().parents[1]

def estimates(d,role,training):
    col='striker_id' if role=='batting' else 'bowler_id';key=role+'_0.2';out={}
    if role=='batting':d=d[d.extra.ne('wide')]
    for pid,g in d.groupby(col):
        e=estimate_lift(g,key,role+'_residual',training_sample=training)
        if e is None:continue
        q=g[g[key]];n=len(q);shrink=n/(n+60) if training else 1
        e['lift_score']=e['lift']*shrink
        e['absolute_score']=100*q[role+'_residual'].mean()*shrink
        e['blend_70_absolute_30_lift']=.7*e['absolute_score']+.3*e['lift_score']
        e['simple_rate']=100*g.runs.sum()/len(g) if role=='batting' else -6*g.bowler_runs.sum()/max(1,int(g.legal.sum()))
        e['wickets_per100']=100*(q.credit_wicket.sum() if role=='bowling' else ((q.dismissed_player_id==pid)&q.is_wicket).sum())/n
        out[int(pid)]=e
    return out

def run():
    d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet');out={'purpose':'Exploratory common-cohort objective comparison. Both years have already been inspected; not prospective confirmation. Blended weights are a sensitivity choice, not calibrated auction utility.','folds':[]}
    for end,year in [(2024,2025),(2025,2026)]:
        for role in ['batting','bowling']:
            train=estimates(d[d.year.le(end)],role,True);future=estimates(d[d.year.eq(year)],role,False);ids=sorted(train.keys()&future.keys());rng=np.random.default_rng(742+end)
            samples=rng.integers(0,len(ids),size=(1000,len(ids)))
            result={'train_through':end,'test_year':year,'role':role,'training_eligible':len(train),'common_future_players':len(ids),'comparisons':{}}
            for objective in ['lift_score','absolute_score','blend_70_absolute_30_lift','simple_rate']:
                p=np.array([train[i][objective] for i in ids]);metrics={}
                for target in ['lift_score','absolute_score','wickets_per100']:
                    y=np.array([future[i][target] for i in ids]);rho=float(spearmanr(p,y).statistic);boots=[]
                    for ix in samples:
                        if np.ptp(p[ix]) and np.ptp(y[ix]):boots.append(float(spearmanr(p[ix],y[ix]).statistic))
                    baseline=np.array([train[i]['lift_score'] for i in ids]);paired=[]
                    for ix in samples:
                        if np.ptp(p[ix]) and np.ptp(y[ix]) and np.ptp(baseline[ix]):paired.append(float(spearmanr(p[ix],y[ix]).statistic-spearmanr(baseline[ix],y[ix]).statistic))
                    metrics[target]={'spearman':rho,'player_bootstrap95':[float(x) for x in np.quantile(boots,[.025,.975])],'paired_rho_difference_vs_lift95':[float(x) for x in np.quantile(paired,[.025,.975])]} 
                result['comparisons'][objective]=metrics
            out['folds'].append(result)
    chase=d[d.innings.eq(2)&d.baseline_pressure];extreme=chase[chase.need>6*chase.remaining]
    out['operational_pressure_audit']={'chase_events':len(chase),'beyond_six_runs_per_remaining_legal_ball':len(extreme),'note':'Diagnostic maximum assumes no extras; not a mathematical impossibility claim or a validated pressure cutoff.'}
    path=ROOT/'artifacts/private/ranking_objective_check.json';path.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':run()
