"""Reproduce source-code reconciliation and before/after coverage; source rows stay private."""
import json
from pathlib import Path
import pandas as pd
from pipeline import reconstruct, ROOT


def review():
    b = pd.read_parquet(ROOT/'artifacts/private/ball_by_ball.parquet')
    m = pd.read_parquet(ROOT/'artifacts/private/matches.parquet')
    c = pd.read_parquet(ROOT/'artifacts/private/competitions.parquet')
    _, _, legacy_reasons = reconstruct(b, m, legacy=True)
    b, _, reasons = reconstruct(b, m)
    meta = m.merge(c, on='comp_id')
    scope = meta[(meta.comp_name.str.startswith('IPL ') | meta.match_format.str.upper().eq('T20I')) & meta.match_id.isin(b.match_id)] .copy()
    scope['format'] = scope.comp_name.str.startswith('IPL ').map({True:'IPL',False:'T20I'})
    scope['year'] = pd.to_datetime(scope.match_date).dt.year
    old = {str(k):v for k,v in legacy_reasons.items()}
    scope['previously_retained'] = ~scope.match_id.astype(str).isin(old)
    scope['retained'] = ~scope.match_id.isin(reasons)
    out = {'groups': [], 'no_ball_codes': {}}
    for (fmt, year), g in scope.groupby(['format','year']):
        out['groups'].append({'format':fmt,'year':int(year),'matches':len(g),'previously_retained':int(g.previously_retained.sum()),'retained':int(g.retained.sum())})
    last = b.groupby(['match_id','innings']).overid.max()
    overs = b[b.innings.le(2)].groupby(['match_id','innings','overid'])
    for code in ['Overstep','other']:
        x = b[b.extra.eq(code)]
        containing = [(k,g) for k,g in overs if g.extra.eq(code).any() and k[2]<last.loc[k[:2]]]
        out['no_ball_codes'][code] = {'events':len(x),'one_run_penalty':int(x.extras1_runs.eq(1).sum()),'complete_overs':len(containing),'complete_overs_with_six_legal':sum(int(g.legal.sum())==6 for _,g in containing),'incompatible_dismissals':int((x.is_wicket & ~x.dismissal_type.isin(['RunOut','Obstructing the Field','Hit Ball Twice'])).sum())}
    out['basis'] = 'Inferred source-code interpretation checked against complete overs, one-run penalties, compatible dismissals, innings termination, winner and stated numeric margins. Not a provider-confirmed data dictionary.'
    out['law_reference'] = 'https://www.icc-cricket.com/news/mens-odi-match-clause-21-no-ball'
    out['byes_reference'] = 'https://www.icc-cricket.com/news/mens-t20i-match-clause-18-scoring-runs'
    out['recovered_matches'] = int((~scope.previously_retained & scope.retained).sum())
    out['newly_rejected_matches'] = int((scope.previously_retained & ~scope.retained).sum())
    path=ROOT/'artifacts/private/extras-recovery-review.json'
    path.write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
    return out


if __name__ == '__main__':
    review()
