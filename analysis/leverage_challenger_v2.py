"""Exploratory actual-match win-probability leverage. Never overwrites rankings."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from scipy.stats import spearmanr
from event_sensitivity import source_rows, KEY
from score_validation import estimate_lift
ROOT=Path(__file__).resolve().parents[1]

def x(d):
    chase=d.innings.eq(2)
    need=np.where(chase,d.need,0)
    return np.column_stack([d.score,d.lost,d.remaining,need,np.where(chase,need/d.remaining.clip(lower=1),0),chase,d.is_ipl])

def wp(model,d):
    p=model.predict_proba(x(d))[:,1]
    chase=d.innings.eq(2)
    return np.where(chase & d.need.le(0),1,np.where(chase & (d.remaining.le(0)|d.lost.ge(10)),0,p))

def advance(d,total,legal,wicket):
    z=d.copy();z['score']=z.score+total;z['need']=z.need-total
    z['lost']=np.minimum(10,z.lost+wicket);z['remaining']=np.maximum(0,z.remaining-legal)
    # First-innings terminal states retain score/wickets and use zero resources.
    z.loc[z.lost.ge(10),'remaining']=0
    return z

def terminal_first(d):
    last=d[d.innings.eq(1)].sort_values(KEY).groupby('match_id').tail(1)
    z=last.copy();z['score']=last.score+last.total;z['lost']=last.lost+last.wicket;z['remaining']=0
    return z

def distributions(train):
    return {k:g.groupby(['total','legal','wicket']).size()/len(g) for k,g in train.groupby(['innings','phase','is_ipl'])}

def leverage(model,d,dist):
    before=wp(model,d);result=np.zeros(len(d))
    for k,index in d.groupby(['innings','phase','is_ipl']).indices.items():
        group=d.iloc[index]
        if k not in dist:raise ValueError('Unsupported outcome stratum')
        for (total,legal,wicket),prob in dist[k].items():
            result[index]+=float(prob)*np.abs(wp(model,advance(group,total,int(legal),int(wicket)))-before[index])
    return result

class CalibratedInningsModels:
    """Separate innings models; chronological match-disjoint Platt calibration."""
    def fit(self,train):
        self.models={};self.calibrators={};self.split_info={}
        matches=train[['match_id','match_date']].drop_duplicates().sort_values(['match_date','match_id'])
        split=max(1,int(len(matches)*.75));fit_ids=set(matches.iloc[:split].match_id);cal_ids=set(matches.iloc[split:].match_id)
        assert fit_ids.isdisjoint(cal_ids)
        for inn in [1,2]:
            fit=train[train.match_id.isin(fit_ids)&train.innings.eq(inn)].copy()
            cal=train[train.match_id.isin(cal_ids)&train.innings.eq(inn)].copy()
            if inn==1:fit=pd.concat([fit,terminal_first(fit)],ignore_index=True)
            y=fit.batting_team_id.eq(fit.win_team_id).astype(int)
            w=1/fit.groupby('match_id').match_id.transform('size')
            model=make_pipeline(PolynomialFeatures(2,include_bias=False),StandardScaler(),LogisticRegression(C=.1,max_iter=3000))
            model.fit(x(fit),y,logisticregression__sample_weight=w*len(fit)/fit.match_id.nunique())
            cy=cal.batting_team_id.eq(cal.win_team_id).astype(int);cw=1/cal.groupby('match_id').match_id.transform('size')
            calibrator=LogisticRegression(C=1,max_iter=1000)
            calibrator.fit(model.decision_function(x(cal)).reshape(-1,1),cy,sample_weight=cw*len(cal)/cal.match_id.nunique())
            self.models[inn]=model;self.calibrators[inn]=calibrator
            self.split_info[str(inn)]={'fit_matches':len(fit_ids),'calibration_matches':len(cal_ids),'calibration_slope':float(calibrator.coef_[0,0])}
        return self
    def predict_proba(self,features):
        p=np.zeros(len(features))
        for inn in [1,2]:
            mask=features[:,5]==(inn==2)
            if mask.any():
                logits=self.models[inn].decision_function(features[mask]).reshape(-1,1)
                p[mask]=self.calibrators[inn].predict_proba(logits)[:,1]
        return np.column_stack([1-p,p])

def run():
    b,_=source_rows();evaluated=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
    folds=[];out=[]
    for year in [2023,2024,2025,2026]:
        train=b[b.year<year].copy();test=b[b.year.eq(year)].copy()
        model=CalibratedInningsModels().fit(train)
        dist=distributions(train);raw_train=leverage(model,train.reset_index(drop=True),dist)
        norms={inn:float(raw_train[train.innings.to_numpy()==inn].mean()) for inn in [1,2]}
        if min(norms.values())<=0:raise ValueError('Nonpositive training leverage reference')
        test=test.reset_index(drop=True);test['win_probability']=wp(model,test)
        test['leverage_index']=leverage(model,test,dist)/test.innings.map(norms).to_numpy()
        test['high_leverage']=test.leverage_index.ge(2)
        record={'year':year,'train_matches':int(train.match_id.nunique()),'test_matches':int(test.match_id.nunique()),'training_leverage_reference_by_innings':norms,'chronological_calibration':model.split_info,'innings':{}}
        for inn,g in test.groupby('innings'):
            target=g.batting_team_id.eq(g.win_team_id).astype(int);w=1/g.groupby('match_id').match_id.transform('size')
            prior=float(train[train.innings.eq(inn)].groupby('match_id').first().batting_team_id.eq(train[train.innings.eq(inn)].groupby('match_id').first().win_team_id).mean())
            bins=[]
            for lo in [0,.2,.4,.6,.8]:
                q=g[(g.win_probability>=lo)&(g.win_probability<lo+.2)]
                if len(q):bins.append({'low':lo,'events':len(q),'predicted':float(q.win_probability.mean()),'observed':float(q.batting_team_id.eq(q.win_team_id).mean())})
            record['innings'][str(inn)]={'match_weighted_brier':float(brier_score_loss(target,g.win_probability,sample_weight=w)),'constant_prior_brier':float(brier_score_loss(target,np.full(len(g),prior),sample_weight=w)),'high_leverage_events':int(g.high_leverage.sum()),'calibration_bins_event_weighted':bins}
        # Explicitly probe a dead chase and a close final over; hypothetical checks are not accuracy evidence.
        probe=test[test.innings.eq(2)].head(1).copy();probe['remaining']=6;probe['lost']=6
        edge={}
        for name,needed in [('dead_chase',50),('close_finish',6),('target_reached',0)]:
            probe['need']=needed;probe['score']=probe.target-needed
            edge[name]={'wp':float(wp(model,probe)[0]),'li':float(leverage(model,probe.reset_index(drop=True),dist)[0]/norms[2])}
        record['hypothetical_edge_cases']=edge
        out.append(test);folds.append(record)
    oos=pd.concat(out,ignore_index=True).merge(evaluated[KEY+['batting_residual','bowling_residual','baseline_pressure']],on=KEY,validate='one_to_one')
    coverage={}
    for role,col in [('batting','striker_id'),('bowling','bowler_id')]:
        d=oos[oos.extra.ne('wide')] if role=='batting' else oos
        players=[]
        for pid,g in d.groupby(col):
            e=estimate_lift(g,'high_leverage',role+'_residual',training_sample=True)
            if e:players.append(int(pid))
        coverage[role]=len(players)
    policy_checks={}
    for threshold in [1.5,2.0]:
        oos['candidate_pressure']=oos.leverage_index.ge(threshold)
        policies={}
        for role,col in [('batting','striker_id'),('bowling','bowler_id')]:
            d=oos[oos.extra.ne('wide')] if role=='batting' else oos
            checks=[]
            for end,year in [(2024,2025),(2025,2026)]:
                for policy in ['baseline_pressure','candidate_pressure']:
                    tr={};fu={}
                    for pid,g in d[d.year.le(end)].groupby(col):
                        e=estimate_lift(g,policy,role+'_residual',training_sample=True)
                        if e:tr[int(pid)]=e
                    for pid,g in d[d.year.eq(year)].groupby(col):
                        e=estimate_lift(g,policy,role+'_residual',training_sample=False)
                        if e:fu[int(pid)]=e
                    ids=sorted(tr.keys()&fu.keys())
                    pred=np.array([tr[i]['lift']*tr[i]['pressure_events']/(tr[i]['pressure_events']+60) for i in ids]);actual=np.array([fu[i]['lift'] for i in ids])
                    checks.append({'train_through':end,'test_year':year,'policy':policy,'training_eligible':len(tr),'future_evaluable':len(ids),'rmse':float(np.sqrt(np.mean((pred-actual)**2))) if ids else None,'spearman':float(spearmanr(pred,actual).statistic) if len(ids)>=3 and np.ptp(pred)>0 else None})
            policies[role]=checks
        policy_checks[str(threshold)]=policies
    examples=[]
    for inn in [1,2]:
        part=oos[oos.innings.eq(inn)]
        for kind,g in [('highest_leverage',part.nlargest(3,'leverage_index')),('baseline_but_low_leverage',part[part.baseline_pressure].nsmallest(3,'leverage_index'))]:
            for r in g.itertuples():examples.append({'kind':kind,'match_id':int(r.match_id),'year':int(r.year),'innings':inn,'score_before':int(r.score),'wickets_lost':int(r.lost),'balls_remaining':int(r.remaining),'runs_needed_chase_only':int(r.need) if inn==2 else None,'wp':float(r.win_probability),'li':float(r.leverage_index)})
    output={'method':'Separate innings actual-match WP with chronological Platt calibration; empirical joint delivery outcomes by innings/phase/format; innings-specific training-only LI normalizers (relative intensity, not common absolute stakes); LI>=2 is a candidate cutoff, not an industry mandate','folds':folds,'eligible_players':coverage,'policy_checks':policy_checks,'private_real_state_examples':examples,'decision':'Do not replace published rule automatically. Requires calibration, monotonicity, richer state-conditional transitions, temporal stability and held-out player validation. First-innings terminal resource transitions and coarse outcome strata are modelling assumptions.'}
    path=ROOT/'artifacts/private/leverage_challenger_v2.json';path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))

if __name__=='__main__':run()
