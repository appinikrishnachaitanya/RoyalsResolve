"""Exploratory actual-match win-probability leverage. Never overwrites rankings."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
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

def run():
    b,_=source_rows();evaluated=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
    folds=[];out=[]
    for year in [2023,2024,2025,2026]:
        train=b[b.year<year].copy();test=b[b.year.eq(year)].copy()
        fit=pd.concat([train,terminal_first(train)],ignore_index=True)
        y=fit.batting_team_id.eq(fit.win_team_id).astype(int)
        weights=1/fit.groupby('match_id').match_id.transform('size')
        model=make_pipeline(PolynomialFeatures(2,include_bias=False),StandardScaler(),LogisticRegression(C=1,max_iter=2000))
        model.fit(x(fit),y,logisticregression__sample_weight=weights*len(fit)/fit.match_id.nunique())
        dist=distributions(train);raw_train=leverage(model,train.reset_index(drop=True),dist)
        norm=float(raw_train.mean())
        if norm<=0:raise ValueError('Nonpositive training leverage reference')
        test=test.reset_index(drop=True);test['win_probability']=wp(model,test);test['leverage_index']=leverage(model,test,dist)/norm
        test['high_leverage']=test.leverage_index.ge(2)
        record={'year':year,'train_matches':int(train.match_id.nunique()),'test_matches':int(test.match_id.nunique()),'training_leverage_reference':norm,'innings':{}}
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
            edge[name]={'wp':float(wp(model,probe)[0]),'li':float(leverage(model,probe.reset_index(drop=True),dist)[0]/norm)}
        record['hypothetical_edge_cases']=edge
        out.append(test);folds.append(record)
    oos=pd.concat(out,ignore_index=True).merge(evaluated[KEY+['batting_residual','bowling_residual']],on=KEY,validate='one_to_one')
    coverage={}
    for role,col in [('batting','striker_id'),('bowling','bowler_id')]:
        d=oos[oos.extra.ne('wide')] if role=='batting' else oos
        players=[]
        for pid,g in d.groupby(col):
            e=estimate_lift(g,'high_leverage',role+'_residual',training_sample=True)
            if e:players.append(int(pid))
        coverage[role]=len(players)
    output={'method':'Exploratory polynomial-logistic actual-match WP; empirical joint delivery outcomes by innings/phase/format; training-only LI normalizer; LI>=2 is a candidate cutoff, not an industry mandate','folds':folds,'eligible_players':coverage,'decision':'Do not replace published rule automatically. Requires calibration, monotonicity, richer state-conditional transitions, temporal stability and held-out player validation. First-innings terminal resource transitions and coarse outcome strata are modelling assumptions.'}
    path=ROOT/'artifacts/private/leverage_challenger.json';path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))

if __name__=='__main__':run()
