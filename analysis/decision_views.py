"""Small publication-safe decision aggregates and a strictly private replay."""
from pathlib import Path
from html import escape
import numpy as np

def raw_stars(d,role):
    col='striker_id' if role=='batting' else 'bowler_id';name='striker_name' if role=='batting' else 'bowler_name';rows=[]
    for pid,g in d.groupby(col):
        if len(g)<120 or g.match_id.nunique()<5:continue
        legal=int(g.legal.sum());dismissed=int(((g.dismissed_player_id==pid)&g.is_wicket).sum()) if role=='batting' else int(g.credit_wicket.sum())
        rate=float(100*g.runs.sum()/max(1,len(g[g.extra!='wide']))) if role=='batting' else float(6*g.bowler_runs.sum()/max(1,legal))
        pressure=g[g[f'{role}_0.2']]
        score=100*pressure[role+'_residual'].sum()/(len(pressure)+60)
        rows.append({'id':int(pid),'name':str(g[name].mode().iloc[0]),'rate':round(rate,2),'events':len(g),'matches':int(g.match_id.nunique()),'pressure_events':len(pressure),'pressure_matches':int(pressure.match_id.nunique()),'pressure_contribution':round(float(score),2),'eligible_pressure':len(pressure)>=30 and pressure.match_id.nunique()>=5,'average':round(float(g.runs.sum()/dismissed),2) if role=='batting' and dismissed else None})
    rows.sort(key=lambda x:((-x['rate'] if role=='batting' else x['rate']),x['id']))
    return rows[:3]

def matchups(d,pid,role):
    col='striker_id' if role=='batting' else 'bowler_id';g=d[(d[col]==pid)&d[f'{role}_0.2']];out=[]
    for dimension in ['pace_or_spin','batting_type']:
        for value,sg in g.groupby(dimension):
            if len(sg)<30 or sg.match_id.nunique()<5:continue
            bymatch=sg.groupby('match_id')[role+'_residual'].agg(['sum','count']);arr=bymatch.to_numpy();rng=np.random.default_rng(2718);ix=rng.integers(0,len(arr),(400,len(arr)));s=arr[ix].sum(axis=1);boot=100*s[:,0]/s[:,1]
            out.append({'dimension':dimension,'value':str(value),'events':len(sg),'matches':int(sg.match_id.nunique()),'runs_per_100':round(float(100*sg[role+'_residual'].mean()),2),'interval':np.quantile(boot,[.025,.975]).round(2).tolist()})
    return out

def private_replay(d,result,root):
    """Never copied into results/public, frontend or Docker context."""
    html=['<!doctype html><meta charset="utf-8"><title>Private pressure replay</title><style>body{max-width:1000px;margin:40px auto;font:16px/1.7 system-ui;color:#14204b}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ddd}</style><h1>Royals Resolve - private pressure passages</h1><p>Local review only. Do not publish this file. No causal or psychological claim.</p>']
    for role,label in [('batting','batters'),('bowling','bowlers')]:
        col='striker_id' if role=='batting' else 'bowler_id'
        for p in result[label]:
            g=d[(d[col]==p['id'])&d[f'{role}_0.2']]
            candidates=[]
            for (mid,inn,over),sg in g.groupby(['match_id','innings','overid']):
                state=sg.iloc[0];candidates.append((float(sg[role+'_residual'].sum()),mid,inn,over,sg,state))
            candidates.sort(key=lambda x:(x[0],x[1],x[2],x[3]),reverse=True)
            # Include one downside passage; avoid only showing highlights.
            chosen=candidates[:4]
            if len(candidates)>4:chosen.append(candidates[-1])
            html.append('<h2>'+escape(p['name'])+' / '+label+'</h2><table><tr><th>Match / innings / over</th><th>Pre-passage state</th><th>Observed pressure exposure</th></tr>')
            for residual,mid,inn,over,sg,state in chosen:
                html.append(f'<tr><td>{mid} / {inn} / {over}<br>{state.match_date}</td><td>{int(state.score)}/{int(state.lost)}, {int(state.remaining)} legal balls left<br>margin {int(state[role+"_margin"])}</td><td>{len(sg)} events, {int(sg.runs.sum() if role=="batting" else sg.bowler_runs.sum())} runs, {residual:+.2f} contextual residual</td></tr>')
            html.append('</table>')
    (root/'artifacts/private/replay.html').write_text('\n'.join(html),encoding='utf-8')
