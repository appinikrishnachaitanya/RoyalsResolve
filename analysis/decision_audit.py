"""Audit the actual selection objective, without refitting or changing publication ranks.

Reproduces the primary output and wicket bootstrap, eligibility and role tags.
Other pressure definitions reclassify ordinary baselines and eligibility too.
"""
import json
import numpy as np
import pandas as pd
from pipeline import ROOT
from selection_policy import order_candidates, submission_excluded_ids


def metrics(d, role, mask, prior=60, seed=2718, reps=400):
    col='striker_id' if role=='batting' else 'bowler_id'
    name='striker_name' if role=='batting' else 'bowler_name'
    rows=d[d.extra.ne('wide')] if role=='batting' else d
    q=rows[mask.reindex(rows.index,fill_value=False)]
    rng=np.random.default_rng(seed);result=[]
    for pid,g in q.groupby(col):
        a=rows[rows[col]==pid];u=a[~a.index.isin(g.index)]
        if len(g)<30 or g.match_id.nunique()<5 or len(u)<60 or u.match_id.nunique()<5:continue
        formats=list(g.groupby('is_ipl').size().index)
        if any(len(u[u.is_ipl==fmt])<30 or u[u.is_ipl==fmt].match_id.nunique()<3 for fmt in formats):continue
        mids=a.match_id.unique();ix=rng.integers(0,len(mids),(reps,len(mids)))
        rr=g.groupby('match_id')[role+'_residual'].agg(['sum','count']).reindex(mids,fill_value=0).to_numpy()
        sums=rr[ix,0].sum(axis=1);counts=rr[ix,1].sum(axis=1);valid=counts>0
        ci=np.quantile(100*sums[valid]/(counts[valid]+prior),[.025,.975])
        actual=g.credit_wicket.astype(int) if role=='bowling' else ((g.dismissed_player_id==g.striker_id)&g.is_wicket).astype(int)
        expected=g.credit_wicket_expected if role=='bowling' else g.dismissal_expected
        delta=(actual-expected)*(1 if role=='bowling' else -1)
        wk=g.assign(delta=delta).groupby('match_id').delta.sum().reindex(mids,fill_value=0).to_numpy()
        wi=np.quantile(100*wk[ix].sum(axis=1)[valid]/(counts[valid]+prior),[.025,.975])
        phases=[str(k) for k,p in a.groupby('phase') if len(p)>=60 and p.match_id.nunique()>=5]
        roles=phases
        if role=='batting':
            roles=[]
            for tag,condition in [('Opener',a.xi_order<=2),('Middle order',a.xi_order.between(3,5))]:
                p=a[condition]
                if len(p)>=60 and p.match_id.nunique()>=5:roles.append(tag)
            if 'Death' in phases:roles.append('Death overs')
        usual=sum(len(p)*u[u.is_ipl==fmt][role+'_residual'].mean() for fmt,p in g.groupby('is_ipl'))/len(g)
        result.append({'id':int(pid),'name':str(g[name].mode().iloc[0]),'rank':1,'roles':roles,'balls':len(g),'matches':int(g.match_id.nunique()),'ipl_balls':int(g.is_ipl.sum()),'t20i_balls':int((~g.is_ipl).sum()),'pressure_score':round(float(100*g[role+'_residual'].sum()/(len(g)+prior)),4),'pressure_interval':ci.round(4).tolist(),'wicket_score':round(float(100*delta.sum()/(len(g)+prior)),4),'wicket_interval':wi.round(4).tolist(),'score':round(float(100*(g[role+'_residual'].sum()-len(g)*usual)/(len(g)+prior)),4),'dismissals':int(actual.sum()),'expected_dismissals':round(float(expected.sum()),4),'dismissal_net_per_100':round(float(100*(actual-expected).sum()/(len(g)+prior)),4)})
    return order_candidates(result,role,submission_excluded_ids())


def run():
    d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
    published=json.loads((ROOT/'results/public/analysis.json').read_text())
    feasible=d.innings.eq(1)|((d.need>0)&(d.need<=6*d.remaining))
    collapse=d.prior_wickets12>=2
    masks={
        'Published':d.baseline_pressure,
        'Broader':(((d.innings==2)&(d.remaining<=72)&(d.rrr>=7))|((d.innings==1)&(d.remaining<=36)&(d.lost>=2))|collapse)&feasible,
        'Narrower':(((d.innings==2)&(d.remaining<=48)&(d.rrr>=9))|((d.innings==1)&(d.remaining<=24)&(d.lost>=4))|collapse)&feasible,
        'Late demand only':d.late_demand_pressure&feasible,
    }
    out={'analysis_id':published['analysis_id'],'replicates':400,'model_uncertainty':'conditional on frozen contextual models; no model refits','roles':{}}
    for role,key in [('batting','batters'),('bowling','bowlers')]:
        primary=metrics(d,role,masks['Published'])
        saved=published[key+'_all']
        assert [p['id'] for p in primary]==[p['id'] for p in saved], 'Audit must reproduce the actual production order'
        for a,b in zip(primary,saved):
            assert abs(a['pressure_score']-b['pressure_score'])<.0001
            assert np.allclose(a['pressure_interval'],b['pressure_interval'],atol=.0001)
            assert np.allclose(a['wicket_interval'],b['wicket_interval'],atol=.0001)
        variants=[]
        specs=[(label,mask,60,2718,400,d) for label,mask in masks.items() if label!='Published']
        specs += [('IPL only',masks['Published'],60,2718,400,d[d.is_ipl])]
        specs += [(f'Prior {prior}',masks['Published'],prior,2718,400,d) for prior in [30,120]]
        specs += [(f'Seed {seed}',masks['Published'],60,seed,400,d) for seed in [42,31415,271828]]
        specs += [('2000 resamples',masks['Published'],60,2718,2000,d)]
        base_ids={p['id'] for p in primary[:10]}
        ipl=[]
        for label,mask,prior,seed,reps,source in specs:
            ranked=metrics(source,role,mask,prior,seed,reps)
            byid={p['id']:p for p in ranked}
            matched=[(p,byid[p['id']]) for p in primary[:10] if p['id'] in byid]
            variants.append({'label':label,'overlap':len(base_ids & {p['id'] for p in ranked[:10]}),'max_rank_move':max((abs(a['rank']-b['rank']) for a,b in matched),default=None),'tier_changes':sum(a['selection_tier']!=b['selection_tier'] for a,b in matched) if role=='bowling' else None,'unavailable':10-len(matched),'top10':[p['name'] for p in ranked[:10]],'rank_movement':[{'id':a['id'],'name':a['name'],'primary_rank':a['rank'],'variant_rank':b['rank'],'primary_tier':a['selection_tier'],'variant_tier':b['selection_tier']} for a,b in matched]})
            if label=='IPL only':ipl=ranked
        out['roles'][role]={'primary':primary,'ipl_only':ipl,'stability':variants}
        print(role,[(v['label'],v['overlap'],v['max_rank_move'],v['tier_changes']) for v in variants],flush=True)
    bowl=out['roles']['bowling']['primary']
    example=None
    for p in bowl[:10]:
        for q in bowl:
            if p['evidence_group']==q['evidence_group'] and p['selection_tier']<q['selection_tier'] and p['pressure_interval'][0]>=q['pressure_interval'][0] and p['wicket_interval'][0]>=q['wicket_interval'][0] and (p['pressure_interval'][0]>q['pressure_interval'][0] or p['wicket_interval'][0]>q['wicket_interval'][0]):
                example={'a':p,'b':q};break
        if example:break
    out['dominance_example']=example
    (ROOT/'artifacts/private/decision-audit.json').write_text(json.dumps(out,indent=2))
    print('Exact primary reproduction and decision stability audit complete.')


if __name__=='__main__':run()
