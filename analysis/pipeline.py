"""Versioned offline analysis; source delivery tables remain private.

Run from repository root: python analysis/pipeline.py
"""
import hashlib, json, platform, re
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yaml
from supporting import prepare, dossier, compare, selection_validation, role_rows
from decision_views import raw_stars, matchups, private_replay
from selection_policy import order_candidates, submission_excluded_ids
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config/methodology_v1.yaml').read_text())
KEYS=['match_id','innings']

def before(df,col):
    return df.groupby(KEYS)[col].cumsum()-df[col]

def reconstruct(b,m,legacy=False):
    """Reconcile source no-ball codes; reject contradictions rather than labels."""
    b=b.sort_values(KEYS+['innings_ball_num']).copy()
    b['extra']=b.extras_type.fillna('None')
    b['legal']=~b.extra.isin(['wide','Overstep','other'])
    b['total']=b.runs+b.extras1_runs+b.extras_2_runs
    b['bowler_runs']=b.runs+np.where(b.extra.isin(['wide','Overstep','other']),b.extras1_runs,0)
    b['wicket']=b.is_wicket.astype(int)
    b['credit_wicket']=b.is_wicket & b.dismissal_type.isin(['Caught','Bowled','LBW','Stump','Hit Wicket'])
    b['score']=before(b,'total');b['lost']=before(b,'wicket');b['used']=before(b,'legal')
    b['remaining']=120-b.used
    b['phase']=np.select([b.used<36,b.used<90],['Powerplay','Middle overs'],default='Death')
    b['dot']=(b.total==0)&b.legal
    b['prior_dots']=0; b['prior_wickets']=0; b['prior_wickets12']=0
    for _,g in b.groupby(KEYS):
        for source,target in [('dot','prior_dots'),('wicket','prior_wickets')]:
            values=g[source].to_numpy(dtype=int); c=np.r_[0,np.cumsum(values)]
            used=g.used.to_numpy(); left=np.searchsorted(used,used-6,side='left')
            b.loc[g.index,target]=c[np.arange(len(g))]-c[left]
            if source=='wicket':
                left12=np.searchsorted(used,used-12,side='left')
                b.loc[g.index,'prior_wickets12']=c[np.arange(len(g))]-c[left12]
    reasons={}
    def reject(ids,reason):
        for i in ids:reasons.setdefault(int(i),[]).append(reason)
    if legacy:
        reject(b.loc[b.extra.isin(['Overstep','other','Penalty']),'match_id'].unique(),'ambiguous extras semantics / penalty timing')
    else:
        nb=b.extra.isin(['Overstep','other'])
        invalid_nb=nb & ((b.extras1_runs!=1) | ((b.runs>0)&(b.extras_2_runs>0)) | (b.is_wicket & ~b.dismissal_type.isin(['RunOut','Obstructing the Field','Hit Ball Twice'])))
        reject(b.loc[invalid_nb,'match_id'].unique(),'no-ball signature or dismissal inconsistent')
        reject(b.loc[b.extra=='Penalty','match_id'].unique(),'penalty timing unresolved')
        reject(b.loc[~b.extra.isin(['None','wide','Overstep','other','byes','legbyes','Penalty']),'match_id'].unique(),'unknown extras code')
    reject(b.loc[(b.extra=='None')&((b.extras1_runs!=0)|(b.extras_2_runs!=0)),'match_id'].unique(),'untyped extras')
    reject(m.loc[m[['first_inn_revised_overs','second_inn_revised_overs','revised_target']].notna().any(axis=1),'match_id'],'revised length or target timing unknown')
    reject(b.loc[b.innings>2,'match_id'].unique(),'super over')
    reject(m.loc[m.result.fillna('').str.contains('abandon|no result|tied|eliminator',case=False),'match_id'],'abandoned / tied / eliminator')
    overs=b[b.innings<=2].groupby(KEYS+['overid']).legal.sum()
    reject(overs[overs>6].index.get_level_values(0),'over has more than six inferred legal deliveries')
    last_over=b[b.innings<=2].groupby(KEYS).overid.max()
    incomplete=[mid for (mid,inn,ov),n in overs.items() if ov<last_over.loc[(mid,inn)] and n!=6]
    if not legacy:reject(incomplete,'non-final over does not reconcile to six legal balls')
    finals=b[b.innings<=2].groupby(KEYS).agg(total=('total','sum'),balls=('legal','sum'),wickets=('wicket','sum'),team=('batting_team_id','first'))
    for mid,g in finals.groupby(level=0):
        if len(g)!=2 or set(g.index.get_level_values(1))!={1,2}:
            reject([mid],'missing regulation innings');continue
        f,c=g.loc[(mid,1)],g.loc[(mid,2)]
        if (f.balls!=120 and f.wickets!=10) or f.balls>120 or c.balls>120:
            reject([mid],'incomplete or inconsistent regulation innings');continue
        if c.total<=f.total and c.balls!=120 and c.wickets!=10:
            reject([mid],'nonterminal chase');continue
        mm=m[m.match_id==mid].iloc[0]
        inferred=c.team if c.total>f.total else f.team
        if inferred!=mm.win_team_id or c.total==f.total: reject([mid],'winner reconciliation failed')
        run_margin=re.search(r'won by (\d+) runs?',str(mm.result),re.I)
        wicket_margin=re.search(r'won by (\d+) wickets?',str(mm.result),re.I)
        if not legacy and run_margin and f.total-c.total!=int(run_margin.group(1)):reject([mid],'run margin does not reconcile')
        if not legacy and wicket_margin and (10-c.wickets!=int(wicket_margin.group(1)) or c.total<=f.total):reject([mid],'wicket margin does not reconcile')
    b=b.merge(m[['match_id','comp_id','match_date','venue_id','win_team_id']],on='match_id',validate='many_to_one')
    targets=finals.xs(1,level='innings').total+1
    b['target']=b.match_id.map(targets);b['need']=b.target-b.score
    b['rrr']=6*b.need/b.remaining.clip(lower=1)
    b['year']=pd.to_datetime(b.match_date).dt.year
    b['retained']=~b.match_id.isin(reasons)&b.innings.isin([1,2])
    return b,finals,reasons

def features(d,benchmark):
    chase=(d.innings==2).astype(int)
    need=np.where(chase,d.need,benchmark-d.score)
    return np.column_stack([d.score,d.lost,d.remaining,need,need/d.remaining.clip(lower=1),chase,d.used<36,d.used>=90])

def probability(model,d,benchmark):
    p=model.predict_proba(features(d,benchmark))[:,1]
    need=np.where(d.innings==2,d.need,benchmark-d.score)
    return np.where(need<=0,1,np.where((d.remaining<=0)|(d.lost>=10),0,p))

def tolerance(model,d,benchmark,role,tau):
    q=probability(model,d,benchmark)
    if role=='bowling':q=1-q
    margin=np.zeros(len(d),dtype=int);alive=q>=tau
    margin[~alive]=-1
    for k in range(1,CFG['stress_horizon']+1):
        stress=d.copy();stress['remaining']=d.remaining-k;stress['used']=d.used+k
        if role=='bowling':stress['score']=d.score+4*k;stress['need']=d.need-4*k
        v=probability(model,stress,benchmark)
        if role=='bowling':v=1-v
        alive &= (k<=d.remaining)&(v>=tau)
        margin[alive]=k
    return margin,q

def episodes(d,mask):
    # One contiguous role-side passage per innings; player exposure inherits its ID.
    entry=mask & (~mask.groupby([d.match_id,d.innings]).shift(fill_value=False))
    number=entry.groupby([d.match_id,d.innings]).cumsum()
    return d.match_id.astype(str)+'/'+d.innings.astype(str)+'/'+number.astype(str)

def context_x(d):
    return np.column_stack([d.used,d.lost,d.score/(d.used+6),d.rrr*(d.innings==2),d.innings,d.used<36,d.used>=90,d.is_ipl])

def fit_oos(b,finals):
    b=b[b.retained].copy();out=[];validation=[]
    for year in [2023,2024,2025,2026]:
        train=b[b.year<year];test=b[b.year==year].copy()
        if len(test)==0 or train.match_id.nunique()<30:continue
        first=finals.xs(1,level='innings');train_ids=train.match_id.unique()
        benchmark=float(first.loc[first.index.isin(train_ids),'total'].median())
        finaltotal=train.set_index(KEYS).index.map(finals.total)
        y=np.where(train.innings==2,train.batting_team_id==train.win_team_id,finaltotal>=benchmark).astype(int)
        # Each match contributes equal total fitting weight, irrespective of length.
        weights=1/train.groupby('match_id').match_id.transform('size').to_numpy()
        models={}
        for name,degree in [('logistic',1),('quadratic_logistic',2)]:
            model=make_pipeline(PolynomialFeatures(degree,include_bias=False),StandardScaler(),LogisticRegression(C=1,max_iter=1000))
            model.fit(features(train,benchmark),y,logisticregression__sample_weight=weights*len(train)/train.match_id.nunique())
            models[name]=model
        finaltest=test.set_index(KEYS).index.map(finals.total)
        yt=np.where(test.innings==2,test.batting_team_id==test.win_team_id,finaltest>=benchmark).astype(int)
        record={'year':year,'train_matches':int(train.match_id.nunique()),'test_matches':int(test.match_id.nunique()),'benchmark':benchmark,'models':{}}
        for name,model in models.items():
            pred=probability(model,test,benchmark)
            bins=[]
            for low in np.arange(0,1,.2):
                ix=(pred>=low)&(pred<low+.2)
                bins.append({'low':round(float(low),1),'rows':int(ix.sum()),'predicted':float(pred[ix].mean()) if ix.any() else None,'observed':float(yt[ix].mean()) if ix.any() else None})
            record['models'][name]={'brier':float(brier_score_loss(yt,pred)),'log_loss':float(log_loss(yt,np.clip(pred,1e-6,1-1e-6))),'calibration':bins}
        # Freeze simple linear logistic, avoiding holdout-led model selection.
        model=models['logistic'];test['viability']=probability(model,test,benchmark)
        for role in ['batting','bowling']:
            for tau in CFG['tau_sensitivity']:
                margin,q=tolerance(model,test,benchmark,role,tau)
                label=(q>=.2)&(q<=.8)&(margin>=0)&(margin<=CFG['tolerance_cutoff'])
                key=f'{role}_{tau}'
                test[key]=label;test[key+'_episode']=episodes(test,pd.Series(label,index=test.index))
            test[role+'_margin']=tolerance(model,test,benchmark,role,CFG['tau'])[0]
        for role in ['batting','bowling']:
            target='runs' if role=='batting' else 'bowler_runs'
            reg=make_pipeline(StandardScaler(),Ridge(alpha=60))
            role_train=role_rows(train,role)
            reg.fit(context_x(role_train),role_train[target])
            test[role+'_expected']=np.clip(reg.predict(context_x(test)),0,6)
            test[role+'_residual']=(test[target]-test[role+'_expected'])*(1 if role=='batting' else -1)
        boundary_model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500))
        boundary_model.fit(context_x(train),(train.is_four|train.is_six).astype(int))
        test['bowling_boundary_expected']=boundary_model.predict_proba(context_x(test))[:,1]
        dismissal_model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500))
        dismissal_model.fit(context_x(train),(train.is_wicket & (train.dismissed_player_id==train.striker_id)).astype(int))
        test['dismissal_expected']=dismissal_model.predict_proba(context_x(test))[:,1]
        credit_model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500))
        credit_model.fit(context_x(train),train.credit_wicket.astype(int))
        test['credit_wicket_expected']=credit_model.predict_proba(context_x(test))[:,1]
        out.append(test);validation.append(record)
    return pd.concat(out,ignore_index=True),validation

def summarize(d,role,mask=None,minimum=True,ipl_weight=None):
    ipl_weight=float(CFG.get('ipl_evidence_weight',1.0) if ipl_weight is None else ipl_weight)
    format_weight=lambda fmt: ipl_weight if fmt else 1.0
    d=role_rows(d,role)
    if mask is not None:mask=mask.reindex(d.index,fill_value=False)
    player='striker_id' if role=='batting' else 'bowler_id';name='striker_name' if role=='batting' else 'bowler_name'
    key=f'{role}_{CFG["tau"]}';q=d[d[key] if mask is None else mask]
    result=[];rng=np.random.default_rng(CFG['seed'])
    for pid,g in q.groupby(player):
        matches=g.match_id.nunique()
        allg=d[d[player]==pid];r=g[role+'_residual'];selected_idx=allg.index.isin(g.index);pressure_all=allg.loc[selected_idx];nonpressure=allg.loc[~selected_idx]
        pressure_format_counts=g.groupby('is_ipl').size().to_dict()
        normal_by_format=nonpressure.groupby('is_ipl')[role+'_residual'].agg(['mean','count'])
        format_supported=all(fmt in normal_by_format.index and int(normal_by_format.loc[fmt,'count'])>=CFG['min_usual_format_balls'] and nonpressure[nonpressure.is_ipl==fmt].match_id.nunique()>=CFG['min_usual_format_matches'] for fmt in pressure_format_counts)
        ipl_role=allg[allg.is_ipl]
        if minimum and (len(g)<CFG['min_pressure_balls'] or matches<CFG['min_pressure_matches'] or len(nonpressure)<CFG['min_usual_balls'] or nonpressure.match_id.nunique()<CFG['min_usual_matches'] or not format_supported):continue
        usual_by_format={fmt:float(normal_by_format.loc[fmt,'mean']) for fmt in pressure_format_counts if fmt in normal_by_format.index}
        pressure_n=len(g)
        weight_sum=sum(format_weight(fmt)*count for fmt,count in pressure_format_counts.items())
        usual_residual=sum(format_weight(fmt)*count*usual_by_format.get(fmt,0.0) for fmt,count in pressure_format_counts.items())/weight_sum
        weighted_residual_sum=pressure_n*float(np.average(r,weights=np.where(g.is_ipl,ipl_weight,1.0)))
        usual=100*usual_residual
        uplift_sum=weighted_residual_sum-pressure_n*usual_residual
        score=100*uplift_sum/(pressure_n+CFG['pooling_balls'])
        pressure_score=100*weighted_residual_sum/(pressure_n+CFG['pooling_balls'])
        # Resample whole matches; within each replicate, compare pressure and usual
        # residuals inside the same format and reweight to that replicate's pressure mix.
        mids=allg.match_id.unique();ix=rng.integers(0,len(mids),(CFG['bootstrap_replicates'],len(mids)))
        pparts=pressure_all.groupby(['is_ipl','match_id'])[role+'_residual'].agg(['sum','count'])
        uparts=nonpressure.groupby(['is_ipl','match_id'])[role+'_residual'].agg(['sum','count'])
        boot_delta=np.zeros(CFG['bootstrap_replicates']);boot_pressure=np.zeros(CFG['bootstrap_replicates']);boot_valid=np.ones(CFG['bootstrap_replicates'],dtype=bool)
        boot_weight=np.zeros(CFG['bootstrap_replicates']);boot_output=np.zeros(CFG['bootstrap_replicates'])
        for fmt in pressure_format_counts:
            pa=pparts.xs(fmt,level='is_ipl').reindex(mids,fill_value=0)[['sum','count']].to_numpy()
            ua=uparts.xs(fmt,level='is_ipl').reindex(mids,fill_value=0)[['sum','count']].to_numpy()
            ps,pc=pa[ix,0].sum(axis=1),pa[ix,1].sum(axis=1)
            us,uc=ua[ix,0].sum(axis=1),ua[ix,1].sum(axis=1)
            base=np.divide(us,uc,out=np.zeros_like(us),where=uc>0)
            boot_valid &= (uc>0)|(pc==0)
            boot_delta+=format_weight(fmt)*(ps-pc*base);boot_pressure+=pc
            boot_weight+=format_weight(fmt)*pc;boot_output+=format_weight(fmt)*ps
        boot=100*np.divide(boot_delta,boot_weight,out=np.zeros_like(boot_delta),where=boot_weight>0)*boot_pressure/(boot_pressure+CFG['pooling_balls'])
        valid_boot=boot[boot_valid]
        if len(valid_boot)<100:valid_boot=boot
        low,high=np.quantile(valid_boot,[.025,.975])
        # Separate uncertainty in absolute pressure output from improvement.
        abs_n=boot_pressure
        pressure_interval=np.quantile(100*boot_output[abs_n>0]/boot_weight[abs_n>0]*abs_n[abs_n>0]/(abs_n[abs_n>0]+CFG['pooling_balls']),[.025,.975])
        match_rates=pressure_all.groupby('match_id')[role+'_residual'].mean()*100
        wicket_observed=g.credit_wicket.astype(int) if role=='bowling' else ((g.dismissed_player_id==g.striker_id)&g.is_wicket).astype(int)
        wicket_expected=g.credit_wicket_expected if role=='bowling' else g.dismissal_expected
        wicket_delta=(wicket_observed-wicket_expected)*(1 if role=='bowling' else -1)
        wp=g.assign(wicket_delta=wicket_delta*np.where(g.is_ipl,ipl_weight,1.0)).groupby('match_id').wicket_delta.sum().reindex(mids,fill_value=0).to_numpy()
        wicket_boot=100*np.divide(wp[ix].sum(axis=1),boot_weight,out=np.zeros_like(boot_weight),where=boot_weight>0)*abs_n/(abs_n+CFG['pooling_balls'])
        wicket_interval=np.quantile(wicket_boot[abs_n>0],[.025,.975])
        wicket_score=100*float(np.average(wicket_delta,weights=np.where(g.is_ipl,ipl_weight,1.0)))*pressure_n/(pressure_n+CFG['pooling_balls'])
        removal_scores=[]
        for removed_match in g.match_id.unique():
            rp=g[g.match_id!=removed_match]
            ordinary=nonpressure[nonpressure.match_id!=removed_match]
            counts=rp.groupby('is_ipl').size().to_dict()
            bases=ordinary.groupby('is_ipl')[role+'_residual'].mean().to_dict()
            if any(fmt not in bases for fmt in counts):continue
            delta=sum(format_weight(fmt)*(rp.loc[rp.is_ipl==fmt,role+'_residual'].sum()-n*bases[fmt]) for fmt,n in counts.items())
            delta=delta*len(rp)/sum(format_weight(fmt)*n for fmt,n in counts.items())
            removal_scores.append(100*delta/(len(rp)+CFG['pooling_balls']))
        lbmo=min(removal_scores) if removal_scores else None
        phases=[]
        for phase,pg in allg.groupby('phase'):
            if len(pg)<CFG['min_role_balls'] or pg.match_id.nunique()<CFG['min_role_matches']:continue
            phases.append({'role':phase,'balls':int(len(pg)),'matches':int(pg.match_id.nunique()),'contribution':round(float(pg[role+'_residual'].mean()*100),2),'pressure_balls':int(pg[key].sum()),'role_support':bool(len(pg)>=CFG['min_role_balls'] and pg.match_id.nunique()>=CFG['min_role_matches'])})
        roles=[x['role'] for x in phases]
        if role=='batting':
            # XI position validates usual top-order assignment; death exposure permits overlap.
            openers=allg[allg.xi_order<=2];middle=allg[allg.xi_order.between(3,5)]
            roles=[]
            if len(openers)>=60 and openers.match_id.nunique()>=5:roles.append('Opener')
            if len(middle)>=60 and middle.match_id.nunique()>=5:roles.append('Middle order')
            # Only use actual observed late-phase batting exposure as a
            # finishing label; bowling phase evidence is not batting role evidence.
            if any(x['role']=='Death' and x['role_support'] for x in phases):roles.append('Death overs')
        runs=float(g.runs.sum() if role=='batting' else g.bowler_runs.sum());legal=int(g.legal.sum())
        dismissals=int(((g.dismissed_player_id==pid)&g.is_wicket).sum()) if role=='batting' else int(g.credit_wicket.sum())
        season_rows=[]
        for year,yg in g.groupby('year'):
            all_season=allg[allg.year==year];outside=all_season[~all_season[key]]
            season_counts=yg.groupby('is_ipl').size().to_dict()
            season_weight=sum(format_weight(fmt)*n for fmt,n in season_counts.items())
            season_usual=100*sum(format_weight(fmt)*count*usual_by_format.get(fmt,0.0) for fmt,count in season_counts.items())/season_weight
            season_residual=len(yg)*float(np.average(yg[role+'_residual'],weights=np.where(yg.is_ipl,ipl_weight,1.0)))
            season_runs=float(yg.runs.sum() if role=='batting' else yg.bowler_runs.sum());season_legal=int(yg.legal.sum())
            season_dismissals=int(((yg.dismissed_player_id==pid)&yg.is_wicket).sum()) if role=='batting' else int(yg.credit_wicket.sum())
            season_rate=100*season_runs/max(1,len(yg[yg.extra!='wide'])) if role=='batting' else 6*season_runs/max(1,season_legal)
            season_uplift=season_residual-len(yg)*season_usual/100
            season_rows.append({'year':int(year),'balls':int(len(yg)),'matches':int(yg.match_id.nunique()),'episodes':int(yg[key+'_episode'].nunique()),'score':round(float(100*season_uplift/(len(yg)+CFG['pooling_balls'])),4),'pressure_score':round(float(100*season_residual/(len(yg)+CFG['pooling_balls'])),4),'runs':round(season_runs,2),'expected_runs':round(float(yg[role+'_expected'].sum()),4),'rate':round(float(season_rate),2),'legal_balls':season_legal,'overs':f'{season_legal//6}.{season_legal%6}','dismissals':season_dismissals,'expected_dismissals':round(float(yg.dismissal_expected.sum()),3),'dot_rate':round(float(yg['dot'].mean()*100),2),'boundary_rate':round(float((yg.is_four|yg.is_six).mean()*100),2),'extras':int((yg.extras1_runs+yg.extras_2_runs).sum()),'usual':round(season_usual,4) if season_usual is not None else None,'nonpressure_balls':int(len(outside)),'difference':round(float(yg[role+'_residual'].mean()*100-season_usual),4) if season_usual is not None else None,'first_innings_score':round(float(yg.loc[yg.innings==1,role+'_residual'].mean()*100),2) if (yg.innings==1).any() else None,'chase_score':round(float(yg.loc[yg.innings==2,role+'_residual'].mean()*100),2) if (yg.innings==2).any() else None})
        result.append({'weighted_residual_sum':round(weighted_residual_sum,4),'ipl_evidence_weight':ipl_weight,'ipl_pressure_matches':int(g[g.is_ipl].match_id.nunique()),'ipl_usual_matches':int(nonpressure[nonpressure.is_ipl].match_id.nunique()),'ipl_usual_balls':int(nonpressure.is_ipl.sum()),'wicket_score':round(wicket_score,4),'wicket_interval':wicket_interval.round(4).tolist(),'pressure_interval':pressure_interval.round(4).tolist(),'positive_pressure_matches':int((match_rates>0).sum()),'pressure_match_median':round(float(match_rates.median()),3),'nonpressure_balls':len(nonpressure),'expected_dismissals':round(float(g.dismissal_expected.sum()),3),'id':int(pid),'name':str(g[name].mode().iloc[0]),'roles':roles,'balls':int(len(g)),'legal_balls':legal,'overs':f'{legal//6}.{legal%6}','matches':int(matches),'episodes':int(g[key+'_episode'].nunique()),'runs':runs,'rate':round(100*runs/max(1,len(g[g.extra!='wide'])),2) if role=='batting' else round(6*runs/max(1,legal),2),'dismissals':dismissals,'dot_rate':round(float(g['dot'].mean()*100),2),'boundary_rate':round(float((g.is_four|g.is_six).mean()*100),2),'extras':int((g.extras1_runs+g.extras_2_runs).sum()),'expected_runs':round(float(g[role+'_expected'].sum()),4),'residual_sum':round(float(r.sum()),4),'uplift_sum':round(float(uplift_sum),4),'pressure_score':round(float(pressure_score),4),'score':round(float(score),4),'usual':round(float(usual),4),'usual_matches':int(nonpressure.match_id.nunique()),'difference':round(float(100*weighted_residual_sum/pressure_n-usual),4),'interval':[round(float(low),4),round(float(high),4)],'between_match_sd':round(float((100*pparts['sum']/pparts['count'].replace(0,np.nan)).std()),3),'leave_one_out_worst':round(float(lbmo),4) if lbmo is not None else None,'leave_one_out_checked':len(removal_scores),'phases':phases,'ipl_balls':int(g.is_ipl.sum()),'ipl_role_events':int(len(ipl_role)),'ipl_role_matches':int(ipl_role.match_id.nunique()),'t20i_balls':int(g.is_t20i.sum()),'first_innings_balls':int((g.innings==1).sum()),'chase_balls':int((g.innings==2).sum()),'first_innings_score':round(float(g.loc[g.innings==1,role+'_residual'].mean()*100),2) if (g.innings==1).any() else None,'chase_score':round(float(g.loc[g.innings==2,role+'_residual'].mean()*100),2) if (g.innings==2).any() else None,'seasons':season_rows,'actionability':'Statistical evidence only; 2027 auction status unverified','objection':'Run-only pressure-versus-usual score omits wicket value; intervals are conditional on fitted contextual expectations.','rr_contribution':'Observed role evidence: '+(', '.join(roles) or 'role not established')+'. IPL role exposure in the evaluated window: '+str(int(len(ipl_role)))+' deliveries across '+str(int(ipl_role.match_id.nunique()))+' matches. Pressure samples include '+str(int(g.is_ipl.sum()))+' IPL and '+str(int(g.is_t20i.sum()))+' T20I deliveries. 2027 auction registration and availability are not established.'})
    result.sort(key=lambda x:(-x['score'],-x['matches'],x['id']))
    for i,r in enumerate(result):
        r['rank']=i+1
    return result

def main():
    tables={n:pd.read_parquet(ROOT/f'artifacts/private/{n}.parquet') for n in ['ball_by_ball','matches','competitions','playing_eleven','teams','competition_team_player_mapping']}
    b,m=tables['ball_by_ball'],tables['matches']
    source_deliveries=len(b);source_matches=len(m)
    assert not m.match_id.duplicated().any()
    assert not tables['teams'].duplicated(['comp_id','team_id']).any()
    b,finals,reasons=reconstruct(b,m)
    comps=tables['competitions'];assert not comps.comp_id.duplicated().any()
    b=b.merge(comps[['comp_id','comp_name','match_format','season']],on='comp_id',validate='many_to_one');b['is_ipl']=b.comp_name.str.startswith('IPL ');b['is_t20i']=b.match_format.str.upper().eq('T20I')
    # The problem statement defines the source scope as IPL + T20 Internationals.
    # Exclude other domestic/franchise T20 competitions from pressure estimation.
    in_scope=b.is_ipl|b.is_t20i;scope_match_ids=set(b.loc[in_scope,'match_id'].astype(int))
    scope_deliveries=int(in_scope.sum());scope_matches=len(scope_match_ids)
    b=b.loc[in_scope].copy();m=m[m.match_id.isin(scope_match_ids)].copy()
    finals=finals[finals.index.get_level_values(0).isin(scope_match_ids)]
    reasons={mid:rs for mid,rs in reasons.items() if mid in scope_match_ids}
    xi=tables['playing_eleven'];xi=xi.groupby(['match_id','team_id','player_id']).batting_order.agg(lambda s:s.iloc[0] if s.nunique()==1 else np.nan).reset_index()
    n=len(b);b=b.merge(xi.rename(columns={'team_id':'batting_team_id','player_id':'striker_id','batting_order':'xi_order'}),on=['match_id','batting_team_id','striker_id'],how='left',validate='many_to_one');assert len(b)==n
    oos,validation=fit_oos(b,finals)
    oos['late_demand_pressure']=((oos.innings==2)&(oos.remaining<=60)&(oos.rrr>=8))|((oos.innings==1)&(oos.remaining<=30)&(oos.lost>=3))
    chase_not_decided=(oos.innings==1)|((oos.need>0)&(oos.need<=6*oos.remaining))
    oos['baseline_pressure']=(oos.late_demand_pressure | (oos.prior_wickets12>=2)) & chase_not_decided
    margin_coverage={role:len(summarize(oos,role)) for role in ['batting','bowling']}
    fallback=True  # Explicit published operational policy; margin coverage cannot silently switch the estimand.
    if fallback:
        for role in ['batting','bowling']:
            oos[role+'_margin_label']=oos[f'{role}_0.2']
            oos[f'{role}_0.2']=oos.baseline_pressure
            oos[f'{role}_0.2_episode']=episodes(oos,oos.baseline_pressure)
    oos=prepare(oos)
    oos.to_parquet(ROOT/'artifacts/private/evaluated.parquet',index=False)
    (ROOT/'artifacts/private/exclusions.json').write_text(json.dumps(reasons,indent=2))
    audit=json.loads((ROOT/'artifacts/private/audit.json').read_text())
    exclusion_counts={}
    for rs in reasons.values():
        for r in set(rs):exclusion_counts[r]=exclusion_counts.get(r,0)+1
    configraw=(ROOT/'config/methodology_v1.yaml').read_bytes()
    codehash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'analysis').glob('*.py')))).hexdigest()
    aid=hashlib.sha256(configraw+json.dumps(audit['manifest'],sort_keys=True).encode()+codehash.encode()).hexdigest()[:16]
    result={'analysis_id':aid,'version':CFG['version'],'generated':datetime.now(timezone.utc).isoformat(),'status':'Historical pressure improvement with separate output and reliability evidence','config':CFG,'provenance':{'code_sha256':codehash,'config_sha256':hashlib.sha256(configraw).hexdigest(),'python':platform.python_version(),'input_zip_sha256':audit.get('input_zip_sha256'),'input_manifest':audit['manifest']},'pressure_policy':'late_demand_or_recent_collapse','margin_eligible_counts':margin_coverage,'audit':{'excluded_innings':int(b.loc[~b.retained].groupby(KEYS).ngroups),'retained_innings':int(b.loc[b.retained].groupby(KEYS).ngroups),'deliveries':source_deliveries,'matches':source_matches,'scope_deliveries':scope_deliveries,'scope_matches':scope_matches,'out_of_scope_deliveries':source_deliveries-scope_deliveries,'out_of_scope_matches':source_matches-scope_matches,'date_range':audit['date_range'],'retained_matches':int(b.loc[b.retained,'match_id'].nunique()),'retained_deliveries':int(b.retained.sum()),'excluded_matches':len(reasons),'excluded_deliveries':int((~b.retained).sum()),'exclusion_reasons_overlapping':exclusion_counts,'oos_matches':int(oos.match_id.nunique()),'oos_deliveries':len(oos),'warmup_deliveries':int(b.retained.sum()-len(oos)),'duplicate_delivery_keys':audit['duplicate_delivery_keys'],'competitions':int(b.comp_id.nunique()),'missing_xi_order':int(b.xi_order.isna().sum()),'schema':{k:{'rows':v['rows'],'columns':list(v['columns'])} for k,v in audit['tables'].items()}},'validation':validation,'limitations':['Rankings use contextual run residuals; wicket-resource values are tested separately. The operational pressure rule is an explicit choice, not a validated universal measure.','Primary model is linear logistic; quadratic candidate evaluated but no superiority claim or automatic selection.','Margin labels are an operational hypothesis; no psychological pressure ground truth. Stress support/extrapolation validation is pending.','First-innings median benchmark is a modelling assumption; first/chase figures are separate. Overall run residual ranking pools their exposure without claiming identical viability scales.','Opponent strength, venue effects, hierarchical season effects and supported pace/spin comparisons are not yet fitted.','Player estimates use fixed exposure shrinkage and match bootstrap, not a fitted hierarchical posterior.','2026 holdout metrics are reported; models and policy were developed in this implementation, not prospectively preregistered. Policy comparisons are retrospective and not confirmatory evidence of superiority.','Auction availability, 2027 rules, purse and submission dropdown IDs are unverified. No actionable TARGET list is asserted.','Ranking scores compare pressure residuals with each player’s non-pressure contextual residual baseline. Pairwise candidate comparisons use common assignment strata and contextual contribution; venue/opponent/position confounds remain.']}
    for role,label in [('batting','batters'),('bowling','bowlers')]:
        research=summarize(oos,role)
        result[label+'_research']=[{k:p[k] for k in ['id','name','rank','score','pressure_score','matches','balls','ipl_balls']} for p in research]
        ranked=order_candidates(research,role,submission_excluded_ids())
        assert len(ranked)>=10,'Insufficient IPL-supported candidates; do not invent a top ten'
        team_map=tables['competition_team_player_mapping']
        team_map=team_map[team_map.comp_id.isin(comps.loc[comps.comp_name.eq('IPL 2026'),'comp_id'])]
        teams_2026=team_map.groupby('player_id').team_name.agg(lambda names:sorted(set(names.dropna()))).to_dict()
        for player in ranked:player['ipl_2026_teams']=teams_2026.get(player['id'],[])
        selected=ranked[:10]
        for p in selected:
            p['scenarios']={'Worst single-match removal':p['leave_one_out_worst']}
        for name,mask in [('Late-demand only',oos.late_demand_pressure & ((oos.innings==1)|(oos.need<=6*oos.remaining))),('IPL only',oos.is_ipl & oos[f'{role}_{CFG["tau"]}']),('Recent 2026',(oos.year==2026)&oos[f'{role}_{CFG["tau"]}']),('Broader pressure rule',((oos.innings==2)&(oos.remaining<=72)&(oos.rrr>=7))|((oos.innings==1)&(oos.remaining<=36)&(oos.lost>=2))),('Narrower pressure rule',((oos.innings==2)&(oos.remaining<=48)&(oos.rrr>=9))|((oos.innings==1)&(oos.remaining<=24)&(oos.lost>=4)))]:
            player_key='striker_id' if role=='batting' else 'bowler_id'
            scenario_rows=oos[oos[player_key].isin([p['id'] for p in selected])]
            alt={x['id']:x for x in summarize(scenario_rows,role,mask)}
            for p in selected:p['scenarios'][name]=({'score':alt[p['id']]['score'],'matches':alt[p['id']]['matches'],'balls':alt[p['id']]['balls']} if p['id'] in alt else None)
        for p in selected:
            p['supporting']=dossier(oos,p['id'],role,f'{role}_0.2')
            p['matchups']=matchups(oos,p['id'],role)
        result[label]=selected;result[label+'_all']=ranked;result[label+'_eligible_count']=len(ranked)
        result[label+'_raw_stars']=raw_stars(oos,role)
        result[label+'_selection_validation']=selection_validation(oos,role,f'{role}_0.2')
        result[label+'_comparisons']=[]
        for i,a in enumerate(selected):
            for bb in selected[i+1:]:
                for phase in [None,'Powerplay','Middle overs','Death']:
                    c=compare(oos,a['id'],bb['id'],role,f'{role}_0.2',phase)
                    if c:result[label+'_comparisons'].append(c)
    if not (ROOT/'artifacts/private/extras-recovery-review.json').exists():
        from recovery_review import review
        review()
    result['extras_recovery']=json.loads((ROOT/'artifacts/private/extras-recovery-review.json').read_text())
    result['roster']=json.loads((ROOT/'config/public_sources.json').read_text())
    # RR coverage and incumbent comparisons are IPL-only; T20I results do not
    # establish a current franchise role or roster gap.
    ipl_oos=oos[oos.is_ipl].copy()
    result['coverage']=[]
    for name in result['roster']['players']:
        row={'name':name,'status':'2026 squad page; 2027 status unknown','batting':[],'bowling':[]}
        for role in ['batting','bowling']:
            col='striker_name' if role=='batting' else 'bowler_name';matches=role_rows(ipl_oos[ipl_oos[col].str.casefold()==name.casefold()],role)
            if len(matches):
                for phase,g in matches.groupby('phase'):
                    if len(g)>=60 and g.match_id.nunique()>=5:row[role].append({'phase':phase,'balls':len(g),'matches':int(g.match_id.nunique()),'score':round(float(g[role+'_residual'].mean()*100),2)})
        result['coverage'].append(row)
    result['incumbent_comparisons']=[]
    for role,label in [('batting','batters'),('bowling','bowlers')]:
        col='striker_name' if role=='batting' else 'bowler_name';idcol='striker_id' if role=='batting' else 'bowler_id'
        for p in result[label]:
            cases=[]
            for incumbent in result['coverage']:
                g=ipl_oos[ipl_oos[col].str.casefold()==incumbent['name'].casefold()]
                if g.empty:continue
                iid=int(g[idcol].mode().iloc[0])
                if iid==p['id']:continue
                c=compare(ipl_oos,p['id'],iid,role,f'{role}_0.2')
                if c:
                    c.update({'incumbent':incumbent['name'],'role':role})
                    result['incumbent_comparisons'].append(c);cases.append(c)
            cases.sort(key=lambda c:-(c['a_events']+c['b_events']))
            alternative=cases[0] if cases else None
            p['rr_case']={'capability_demonstrated':', '.join(p['roles']) or 'insufficient role evidence','current_verified_rr_coverage':alternative['incumbent'] if alternative else 'Shared supported incumbent assignment unavailable','measured_gap_or_uncertainty':('Unresolved: '+alternative['verdict']+' under common assignments; difference '+str(alternative['difference'])+' runs / 100, interval '+str(alternative['interval'])) if alternative else 'No supported quality-gap conclusion','primary_alternative':alternative['incumbent'] if alternative else 'Insufficient overlap for an alternative','biggest_risk':p['objection'],'actionability':'Statistical evidence only; 2027 registration, retention, availability, price and squad need are unverified'}
    private_replay(oos,result,ROOT)
    out=ROOT/'results/public' ;out.mkdir(parents=True,exist_ok=True)
    (out/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'analysis_id':aid,'audit':result['audit'],'batters':[p['name'] for p in result['batters']],'bowlers':[p['name'] for p in result['bowlers']]},default=str))

if __name__=='__main__':main()
