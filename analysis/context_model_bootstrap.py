"""Assess how training-match uncertainty affects contextual-score rankings.

Run from the repository root:
    .venv\\Scripts\\python.exe analysis\\context_model_bootstrap.py

Pressure labels and eligibility are held fixed. For each rolling OOS season,
the run-expectation Ridge models are refit after a season-stratified bootstrap
of training matches. This isolates uncertainty in fitted context expectations
from uncertainty in pressure labels and future event sampling.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from event_sensitivity import KEY, YEARS, source_rows
from pipeline import context_x


ROOT = Path(__file__).resolve().parents[1]
REPLICATES = 100
SEED = 4182
PRIORS = (0, 60, 120)


def fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: str,
    match_weights: pd.Series,
) -> np.ndarray:
    if target == "runs":
        keep=train.extra.ne("wide")
        train=train.loc[keep]
        match_weights=match_weights.loc[keep]
    scaler = StandardScaler()
    x_train = scaler.fit_transform(
        context_x(train), sample_weight=match_weights.to_numpy(dtype=float)
    )
    x_test = scaler.transform(context_x(test))
    model = Ridge(alpha=60)
    model.fit(
        x_train,
        train[target].to_numpy(dtype=float),
        sample_weight=match_weights.to_numpy(dtype=float),
    )
    return np.clip(model.predict(x_test), 0, 6)


def bootstrap_match_weights(
    train: pd.DataFrame, rng: np.random.Generator
) -> pd.Series:
    match_years = train[["match_id", "year"]].drop_duplicates()
    if match_years.match_id.duplicated().any():
        raise ValueError("A match is associated with more than one season year.")
    sampled: dict[int, int] = {}
    for _, season in match_years.groupby("year"):
        ids = season.match_id.to_numpy()
        draws = rng.choice(ids, size=len(ids), replace=True)
        values, counts = np.unique(draws, return_counts=True)
        sampled.update({int(mid): int(count) for mid, count in zip(values, counts)})
    return train.match_id.map(sampled).fillna(0).astype(float)


def player_lifts(rows: pd.DataFrame, role: str) -> list[tuple[float, int, int]]:
    if role == "batting":
        rows=rows.loc[rows.extra.ne("wide")]
    player_column = "striker_id" if role == "batting" else "bowler_id"
    pressure_column = f"{role}_0.2"
    residual_column = f"{role}_residual"
    grouped = rows.groupby(
        [player_column, "is_ipl", pressure_column], observed=True
    ).agg(
        residual_sum=(residual_column, "sum"),
        events=(residual_column, "size"),
        matches=("match_id", "nunique"),
    )
    lifts = []
    for player_id, player in grouped.groupby(level=0, sort=False):
        player = player.droplevel(0)
        pressure = player.xs(True, level=1) if True in player.index.get_level_values(1) else pd.DataFrame()
        usual = player.xs(False, level=1) if False in player.index.get_level_values(1) else pd.DataFrame()
        p_events = int(pressure.events.sum()) if len(pressure) else 0
        p_matches = int(pressure.matches.sum()) if len(pressure) else 0
        u_events = int(usual.events.sum()) if len(usual) else 0
        u_matches = int(usual.matches.sum()) if len(usual) else 0
        if p_events < 30 or p_matches < 5 or u_events < 60 or u_matches < 5:
            continue
        delta = 0.0
        supported = True
        for fmt, p in pressure.iterrows():
            if fmt not in usual.index:
                supported = False
                break
            u = usual.loc[fmt]
            if int(u.events) < 30 or int(u.matches) < 3:
                supported = False
                break
            delta += int(p.events) * (
                float(p.residual_sum / p.events) - float(u.residual_sum / u.events)
            )
        if supported:
            lifts.append((100.0 * delta / p_events, int(player_id), p_events))
    return lifts


def ranking_from_lifts(
    lifts: list[tuple[float, int, int]], prior: int
) -> list[tuple[float, int]]:
    ranked = [
        (
            lift * events / (events + prior) if prior else lift,
            player_id,
        )
        for lift, player_id, events in lifts
    ]
    return sorted(ranked, reverse=True)


def run() -> dict:
    balls, labels = source_rows()
    evaluated = pd.read_parquet(ROOT / "artifacts" / "private" / "evaluated.parquet")
    published = json.loads((ROOT / "results" / "public" / "analysis.json").read_text())
    expected_columns = KEY + ["batting_expected", "bowling_expected"]
    saved_expectations = evaluated[expected_columns].drop_duplicates()
    names = {
        "batting": evaluated.groupby("striker_id").striker_name.agg(lambda s: s.mode().iloc[0]).to_dict(),
        "bowling": evaluated.groupby("bowler_id").bowler_name.agg(lambda s: s.mode().iloc[0]).to_dict(),
    }
    published_top = {
        "batting": [int(player["id"]) for player in published["batters"]],
        "bowling": [int(player["id"]) for player in published["bowlers"]],
    }
    baseline_differences = {role: {} for role in ("batting", "bowling")}
    for year in YEARS:
        train = balls[balls.year < year].copy()
        test = balls[balls.year == year].copy()
        for role, target in (("batting", "runs"), ("bowling", "bowler_runs")):
            expected = fit_predict(train, test, target, pd.Series(1.0, index=train.index))
            test_keyed = test[KEY].copy()
            test_keyed[f"{role}_expected"] = expected
            saved = test_keyed.merge(
                saved_expectations[KEY + [f"{role}_expected"]],
                on=KEY,
                suffixes=("_refit", "_saved"),
                validate="one_to_one",
            )
            delta = float(
                np.max(
                    np.abs(
                        saved[f"{role}_expected_refit"].to_numpy()
                        - saved[f"{role}_expected_saved"].to_numpy()
                    )
                )
            )
            baseline_differences[role][str(year)] = delta
    rng = np.random.default_rng(SEED)
    selections = {
        role: {prior: {player: 0 for player in published_top[role]} for prior in PRIORS}
        for role in ("batting", "bowling")
    }
    rank_records = {
        role: {
            prior: {player: [] for player in published_top[role]}
            for prior in PRIORS
        }
        for role in ("batting", "bowling")
    }
    for replicate in range(REPLICATES):
        boot_by_year = {year: [] for year in YEARS}
        for year in YEARS:
            train = balls[balls.year < year].copy()
            test = balls[balls.year == year].copy()
            weights = bootstrap_match_weights(train, rng)
            for role, target in (("batting", "runs"), ("bowling", "bowler_runs")):
                expected = fit_predict(train, test, target, weights)
                test[f"{role}_expected"] = expected
                test[f"{role}_residual"] = (
                    test[target] - expected
                    if role == "batting"
                    else expected - test[target]
                )
            boot_by_year[year].append(test)

        # Each role's pressure labels are joined once per replicate after all
        # season-specific OOS expectation models have been refit.
        boot_rows = pd.concat(
            [frame for year in YEARS for frame in boot_by_year[year]],
            ignore_index=True,
        ).merge(labels, on=KEY, how="inner", validate="one_to_one")
        for role in ("batting", "bowling"):
            lifts = player_lifts(boot_rows, role)
            for prior in PRIORS:
                ranking = ranking_from_lifts(lifts, prior)
                for rank, (_, player_id) in enumerate(ranking, start=1):
                    if player_id in selections[role][prior]:
                        if rank <= 10:
                            selections[role][prior][player_id] += 1
                        rank_records[role][prior][player_id].append(rank)
        if (replicate + 1) % 10 == 0:
            print(f"Completed bootstrap {replicate + 1}/{REPLICATES}", flush=True)

    output = {
        "analysis_id": published["analysis_id"],
        "replicates": REPLICATES,
        "seed": SEED,
        "expectation_model_baseline_max_abs_difference": baseline_differences,
        "method": "season-stratified match bootstrap; refit StandardScaler + Ridge(alpha=60) separately for each rolling OOS year; frozen pressure labels",
        "roles": {},
    }
    for role in ("batting", "bowling"):
        output["roles"][role] = {}
        for prior in PRIORS:
            output["roles"][role][str(prior)] = {
                "published_top10_membership": [
                    {
                        "id": player,
                        "name": names[role].get(player, str(player)),
                        "top10_replicates": selections[role][prior][player],
                        "frequency": selections[role][prior][player] / REPLICATES,
                        "mean_rank": float(np.mean(rank_records[role][prior][player])),
                        "rank_90_interval": [
                            int(value)
                            for value in np.quantile(
                                rank_records[role][prior][player], [0.05, 0.95]
                            )
                        ],
                    }
                    for player in published_top[role]
                ],
                "average_published_top10_retained": float(
                    sum(selections[role][prior].values()) / (10 * REPLICATES)
                ),
            }
    return output


def main() -> None:
    output = run()
    print(f"Analysis: {output['analysis_id']}; replicates={output['replicates']}")
    print("Max absolute reproduction difference in saved expectations:")
    for role, values in output["expectation_model_baseline_max_abs_difference"].items():
        print(f"  {role}: {values}")
    for role, prior_results in output["roles"].items():
        print(f"\n{role} average published top-10 retention by prior")
        for prior, result in prior_results.items():
            members = result["published_top10_membership"]
            print(
                f"  prior={prior}: {result['average_published_top10_retained']:.3f}; "
                + ", ".join(
                    f"{player['name']} {player['frequency']:.0%}"
                    for player in members
                )
            )


if __name__ == "__main__":
    main()
