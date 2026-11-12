"""Supporting coach metrics; never extra ranking weights."""
import numpy as np
import pandas as pd

def prepare(d):
    d=d.sort_values(['match_id','innings','innings_ball_num']).copy()
    playerkeys=['match_id','innings','striker_id']
    d['faced_legal_before']=d.groupby(playerkeys).legal.cumsum()-d.legal
    entries=d.groupby(playerkeys,as_index=False).first()[playerkeys+['phase','lost','used']]
    entries=entries.rename(columns={'phase':'entry_phase','lost':'entry_lost','used':'entry_used'})
    # Wickets in the preceding 12 legal balls, computed at the actual first exposure.
    recent={}
    for (mid,inn),g in d.groupby(['match_id','innings']):
        fallen=g[g.wicket==1]
        for row in entries[(entries.match_id==mid)&(entries.innings==inn)].itertuples():
            recent[(mid,inn,row.striker_id)]=int(((fallen.used>=row.entry_used-12)&(fallen.used<row.entry_used)).sum())
    entries['collapse_entry']=[recent[(r.match_id,r.innings,r.striker_id)]>=2 for r in entries.itertuples()]
    d=d.merge(entries,on=playerkeys,how='left',validate='many_to_one')
    d['boundary']=(d.is_four|d.is_six).astype(int)
    # Every follow-up delivery counts once, even after consecutive boundaries.
    overkeys=['match_id','innings','overid']
    d['after_boundary']=(d.groupby(overkeys).boundary.cumsum()-d.boundary)>0
    return d

def metric(g,role):
    legal=g[g.legal];runs=legal.runs.sum();bound=legal[legal.boundary==1].runs.sum()
    return {'events':len(g),'legal_balls':len(legal),'matches':int(g.match_id.nunique()),'innings':int(g.groupby(['match_id','innings']).ngroups),'bat_runs':int(g.runs.sum()),'runs_per_100_legal':round(float(100*runs/max(1,len(legal))),2),'dot_percent':round(float(100*legal['dot'].mean()),2) if len(legal) else None,'dismissals':int(((g.dismissed_player_id==g.striker_id)&g.is_wicket).sum()),'contextual_runs_per_100':round(float(100*g[role+'_residual'].mean()),2),'nonboundary_runs_per_100_legal':round(float(100*(runs-bound)/max(1,len(legal))),2),'nonboundary_scoring_percent':round(float(100*((legal.runs>0)&(legal.boundary==0)).sum()/max(1,len(legal))),2),'boundary_share_bat_runs_percent':round(float(100*bound/max(1,runs)),2)}

def dossier(d,pid,role,key):
    col='striker_id' if role=='batting' else 'bowler_id';g=d[d[col]==pid];pressure=g[g[key]]
    match=pressure.groupby('match_id')[role+'_residual'].mean()*100
    rng=np.random.default_rng(2718)
    if len(match)>=5:
        boot=rng.choice(match.to_numpy(),(400,len(match)),replace=True).mean(axis=1)
        downside={'matches':len(match),'lower_quartile':round(float(match.quantile(.25)),2),'median':round(float(match.median()),2),'unfavourable_matches':int((match<0).sum()),'mean_interval':np.quantile(boot,[.025,.975]).round(2).tolist(),'unit':'unpooled runs / 100 events per independent match; variability differs from mean uncertainty'}
    else:downside=None
    result={'downside':downside}
    if role=='batting':
        first=g[g.faced_legal_before<6]
        readiness=[]
        for (phase,collapse),sg in first.groupby(['entry_phase','collapse_entry']):
            if sg.match_id.nunique()<5:continue
            r=metric(sg,role);r.update({'entry_phase':phase,'collapse_entry':bool(collapse),'dismissal_probability_per_innings':round(float(r['dismissals']/max(1,r['innings'])),4)})
            readiness.append(r)
        recovery=[]
        for (phase,collapse),sg in g.groupby(['entry_phase','collapse_entry']):
            if sg.match_id.nunique()>=5:
                r=metric(sg,role);r.update({'entry_phase':phase,'collapse_entry':bool(collapse)});recovery.append(r)
        result.update({'entry_readiness':readiness,'scoring_without_boundaries':metric(g,role),'recovery_assignments':recovery})
    else:
        after=g[g.after_boundary]
        result.update({'boundary_damage_control':({'events':len(after),'legal_balls':int(after.legal.sum()),'matches':int(after.match_id.nunique()),'boundary_percent':round(float(after.boundary.mean()*100),2),'boundary_runs':int(after.loc[after.boundary==1,'bowler_runs'].sum()),'runs_conceded':int(after.bowler_runs.sum()),'runs_prevented':round(float(after.bowling_residual.sum()),2),'expected_boundary_percent':round(float(after.bowling_boundary_expected.mean()*100),2)} if after.match_id.nunique()>=5 else None),'costly_delivery_exposure':{'events':len(g),'legal_balls':int(g.legal.sum()),'verified_wides':int((g.extra=='wide').sum()),'wides_per_100_events':round(float(100*(g.extra=='wide').mean()),2),'no_balls':'not estimated: ambiguous source types quarantined','boundaries_per_100_legal':round(float(100*g.loc[g.legal,'boundary'].mean()),2),'wide_run_cost':int(g.loc[g.extra=='wide','bowler_runs'].sum())}})
    return result

def compare(d,a,b,role,key,phase=None):
    """Common innings/phase/IPL strata, equal stratum weights and match bootstrap."""
    col='striker_id' if role=='batting' else 'bowler_id';x=d[(d[col]==a)&d[key]];y=d[(d[col]==b)&d[key]]
    if phase:
        x=x[x.phase==phase];y=y[y.phase==phase]
    strata=['innings','phase','is_ipl'];xs={k:g for k,g in x.groupby(strata)};ys={k:g for k,g in y.groupby(strata)}
    common=[k for k in xs.keys()&ys.keys() if xs[k].match_id.nunique()>=3 and ys[k].match_id.nunique()>=3 and len(xs[k])>=10 and len(ys[k])>=10]
    if not common:return None
    gx=pd.concat([xs[k] for k in common]);gy=pd.concat([ys[k] for k in common])
    if min(gx.match_id.nunique(),gy.match_id.nunique())<5 or min(len(gx),len(gy))<30:return None
    delta=np.mean([xs[k][role+'_residual'].mean()-ys[k][role+'_residual'].mean() for k in common])*100
    # Resample the union of match clusters jointly, preserving shared-match dependence.
    mids=np.union1d(gx.match_id.unique(),gy.match_id.unique());rng=np.random.default_rng(2718);boots=[]
    prepared=[]
    for k in common:
        prepared.append([g.groupby('match_id')[role+'_residual'].agg(['sum','count']).reindex(mids,fill_value=0).to_numpy() for g in [xs[k],ys[k]]])
    for _ in range(400):
        ix=rng.integers(0,len(mids),len(mids));values=[]
        for ga,gb in prepared:
            sa,na=ga[ix].sum(axis=0);sb,nb=gb[ix].sum(axis=0)
            if na and nb:values.append(sa/na-sb/nb)
        if len(values)==len(common):boots.append(np.mean(values)*100)
    if len(boots)<100:return None
    lo,hi=np.quantile(boots,[.025,.975])
    return {'a':int(a),'b':int(b),'phase':phase or 'Shared assignments','difference':round(float(delta),3),'interval':[round(float(lo),3),round(float(hi),3)],'a_events':len(gx),'b_events':len(gy),'a_matches':int(gx.match_id.nunique()),'b_matches':int(gy.match_id.nunique()),'a_excluded_nonoverlap':len(x)-len(gx),'b_excluded_nonoverlap':len(y)-len(gy),'strata':len(common),'verdict':'A stronger case' if lo>0 else 'B stronger case' if hi<0 else 'Inconclusive','reference':'equal weight across shared innings / phase / IPL strata; pressure-only'}

def selection_validation(d,role,key):
    col='striker_id' if role=='batting' else 'bowler_id';reports=[]
    for year in [2024,2025,2026]:
        prior=d[d.year<year];future=d[(d.year==year)&d[key]]
        rows=[]
        for pid,g in prior.groupby(col):
            pg=g[g[key]]
            if len(pg)<30 or pg.match_id.nunique()<5:continue
            simple=g[g.baseline_pressure]
            ordinary=(g.runs.mean() if role=='batting' else -g.bowler_runs.sum()/max(1,g.legal.sum()))
            average=float(g.runs.sum()/max(1,((g.dismissed_player_id==pid)&g.is_wicket).sum()))
            rows.append({'ordinary_average':average,'id':pid,'contextual':pg[role+'_residual'].sum()/(len(pg)+60),'conservative':pg[role+'_residual'].mean()-1.96*pg.groupby('match_id')[role+'_residual'].mean().std()/np.sqrt(pg.match_id.nunique()),'ordinary':ordinary,'phase_rate_baseline':simple[role+'_residual'].sum()/(len(simple)+60)})
        if not rows:continue
        for policy in ['contextual','conservative','ordinary','phase_rate_baseline']+(['ordinary_average'] if role=='batting' else []):
            selected=sorted(rows,key=lambda x:(-x[policy],x['id']))[:10];ids=[p['id'] for p in selected];test=future[future[col].isin(ids)]
            reports.append({'year':year,'policy':policy,'selected':len(ids),'observed_later':int(test[col].nunique()),'future_events':len(test),'future_matches':int(test.match_id.nunique()),'future_contribution':round(float(100*test[role+'_residual'].mean()),3) if len(test) else None})
    return reports
