"""Exploratory chronological policy checks on identical IPL follow-up cohorts."""
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from pipeline import ROOT, summarize, CFG
from selection_policy import order_candidates, submission_excluded_ids


def run():
    d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
    out=[]
    for year in [2025,2026]:
        for role,col in [('batting','striker_id'),('bowling','bowler_id')]:
            prior=d[d.year<year]
            candidates=order_candidates(summarize(prior,role),role,submission_excluded_ids())
            future=d[(d.year==year)&d.is_ipl&d[f'{role}_0.2']]
            if role=='batting':future=future[future.extra.ne('wide')]
            measured={int(pid):100*float(g[role+'_residual'].mean()) for pid,g in future.groupby(col) if len(g)>=10 and g.match_id.nunique()>=2}
            wicket_followup = {}
            if role == 'bowling':
                future_wickets = future.assign(
                    wicket_residual=future.credit_wicket.astype(int)-future.credit_wicket_expected)
                wicket_followup = (100*future_wickets.groupby(col).wicket_residual.mean()).to_dict()
            common=[p for p in candidates if p['id'] in measured]
            ids=[p['id'] for p in common]
            if len(ids)<4:
                out.append({'year':year,'role':role,'eligible':len(candidates),'measured':len(ids),'status':'too few measurable players'})
                continue
            a=prior[prior[col].isin(ids)]
            if role=='batting':a=a[a.extra.ne('wide')]
            raw={}
            for pid,g in a.groupby(col):
                w=np.where(g.is_ipl,float(CFG['ipl_evidence_weight']),1.0)
                raw[int(pid)]=float(100*np.average(g.runs,weights=w) if role=='batting' else -6*np.sum(w*g.bowler_runs)/np.sum(w*g.legal))
            y=np.array([measured[p['id']] for p in common])
            predictors={'coach_order':-np.array([p['rank'] for p in common]),'improvement':np.array([p['score'] for p in common]),'raw_rate':np.array([raw[p['id']] for p in common])}
            record={'year':year,'role':role,'eligible':len(candidates),'measured':len(ids),'correlations':{}}
            rng=np.random.default_rng(2718)
            draws=rng.integers(0,len(ids),(400,len(ids)))
            for label,x in predictors.items():
                boots=[float(spearmanr(x[ix],y[ix]).statistic) for ix in draws if len(set(ix))>=3]
                boots=[v for v in boots if np.isfinite(v)]
                record['correlations'][label]={'rho':round(float(spearmanr(x,y).statistic),3),'interval':np.quantile(boots,[.025,.975]).round(3).tolist()}
            if role == 'bowling':
                wicket_y = np.array([wicket_followup[pid] for pid in ids])
                record['wicket_correlations'] = {}
                for label, x in {
                    'coach_order': predictors['coach_order'],
                    'wicket_lower_bound': np.array([p['wicket_interval'][0] for p in common]),
                }.items():
                    rho = float(spearmanr(x, wicket_y).statistic)
                    boots = [float(spearmanr(x[ix], wicket_y[ix]).statistic)
                             for ix in draws if len(set(ix)) >= 3]
                    boots = [v for v in boots if np.isfinite(v)]
                    record['wicket_correlations'][label] = {
                        'rho': round(rho, 3) if np.isfinite(rho) else None,
                        'interval': np.quantile(boots, [.025, .975]).round(3).tolist() if boots else None,
                    }
            out.append(record)
            print(json.dumps(record),flush=True)
    result={'ipl_weight':float(CFG['ipl_evidence_weight']),'rank_policy':CFG['rank_policy'],'target':'next-season IPL pressure contextual run output; at least 10 events and 2 matches; identical follow-up cohorts','status':'exploratory, previously inspected seasons; not prospective validation; bowling run and credited-wicket outcomes are evaluated separately','results':out}
    (ROOT/'artifacts/private/coach-backtest.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':run()
