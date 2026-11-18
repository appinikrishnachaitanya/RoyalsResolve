"""Transparent recruitment evidence policy, separate from pressure-improvement arithmetic.

IPL and T20I receive equal delivery weights; T20I-only players stay eligible.
Bowling uses Pareto tiers so no arbitrary runs-per-wicket exchange rate is needed.
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd


@lru_cache(maxsize=1)
def submission_excluded_ids():
    mapping = pd.read_parquet(
        Path(__file__).resolve().parents[1]/'artifacts/private/competition_team_player_mapping.parquet',
        columns=['team_name', 'player_id'],
    )
    pakistan = mapping.team_name.str.strip().str.casefold().isin({'pakistan', 'pakistan a'})
    return frozenset(mapping.loc[pakistan, 'player_id'].dropna().astype(int))


def order_candidates(rows, role, excluded_ids=frozenset()):
    pool=[dict(p) for p in rows if p['roles'] and p['id'] not in excluded_ids]
    for p in pool:
        p['improvement_rank']=p.get('improvement_rank',p['rank'])
        p['evidence_group']=0 if p['pressure_interval'][0]>0 else 1
        p['selection_tier']=1
    if role=='bowling':
        remaining=pool[:];tier=1
        while remaining:
            frontier=[]
            for p in remaining:
                a=(p['pressure_interval'][0],p['wicket_interval'][0])
                dominated=any(q['id']!=p['id'] and q['evidence_group']==p['evidence_group'] and q['pressure_interval'][0]>=a[0] and q['wicket_interval'][0]>=a[1] and (q['pressure_interval'][0]>a[0] or q['wicket_interval'][0]>a[1]) for q in remaining)
                if not dominated:frontier.append(p)
            for p in frontier:p['selection_tier']=tier
            selected={p['id'] for p in frontier}
            remaining=[p for p in remaining if p['id'] not in selected];tier+=1
    pool.sort(key=lambda p:(p['evidence_group'],p['selection_tier'],-p['pressure_interval'][0],-p['pressure_score'],-p['matches'],p['id']))
    for i,p in enumerate(pool):p['rank']=i+1
    return pool
