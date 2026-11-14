"""Out-of-time sensitivity to event types in pressure scoring.

Run from the repository root:
    .venv\\Scripts\\python.exe analysis\\event_sensitivity.py

This research diagnostic rebuilds the rolling contextual run models from the
retained source deliveries, while reusing the pipeline's frozen pressure
labels. It tests whether non-batter events (wides) or non-bowler runs
(byes/leg-byes) materially affect the published role rankings. It does not
write or modify production results.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline import KEYS, context_x, reconstruct
from score_validation import estimate_lift


ROOT = Path(__file__).resolve().parents[1]
YEARS = (2023, 2024, 2025, 2026)
POOLING_EVENTS = 60
KEY = KEYS + ["innings_ball_num"]


def source_rows() -> pd.DataFrame:
    names = ("ball_by_ball", "matches", "competitions", "playing_eleven")
    tables = {
        name: pd.read_parquet(ROOT / "artifacts" / "private" / f"{name}.parquet")
        for name in names
    }
    balls, finals, _ = reconstruct(tables["ball_by_ball"], tables["matches"])
    competitions = tables["competitions"]
    balls = balls.merge(
        competitions[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id",
        validate="many_to_one",
    )
    balls["is_ipl"] = balls.comp_name.str.startswith("IPL ")
    balls["is_t20i"] = balls.match_format.str.upper().eq("T20I")
    balls = balls[balls.is_ipl | balls.is_t20i]
    balls = balls[balls.retained].copy()
    xi = tables["playing_eleven"].groupby(
        ["match_id", "team_id", "player_id"]
    ).batting_order.agg(lambda values: values.iloc[0] if values.nunique() == 1 else np.nan).reset_index()
    balls = balls.merge(
        xi.rename(
            columns={
                "team_id": "batting_team_id",
                "player_id": "striker_id",
                "batting_order": "xi_order",
            }
        ),
        on=["match_id", "batting_team_id", "striker_id"],
        how="left",
        validate="many_to_one",
    )
    # A consistency guard: pressure labels must refer to unique source rows.
    labels = pd.read_parquet(ROOT / "artifacts" / "private" / "evaluated.parquet")
    label_columns = KEY + ["batting_0.2", "bowling_0.2"]
    labels = labels[label_columns].drop_duplicates()
    if labels.duplicated(KEY).any():
        raise ValueError("Frozen pressure labels contain duplicate delivery keys.")
    return balls, labels


def predict_oos(
    balls: pd.DataFrame,
    labels: pd.DataFrame,
    role: str,
    excluded_extras: tuple[str, ...],
) -> pd.DataFrame:
    target = "runs" if role == "batting" else "bowler_runs"
    residual = "sensitivity_residual"
    pressure = f"{role}_0.2"
    scoring_rows = []
    for year in YEARS:
        train = balls[balls.year < year].copy()
        test = balls[balls.year == year].copy()
        train = train[~train.extra.isin(excluded_extras)]
        test = test[~test.extra.isin(excluded_extras)].copy()
        if train.match_id.nunique() < 30 or test.empty:
            raise ValueError(f"Insufficient rolling training data for {year}.")
        model = make_pipeline(StandardScaler(), Ridge(alpha=60))
        model.fit(context_x(train), train[target])
        expected = np.clip(model.predict(context_x(test)), 0, 6)
        if role == "batting":
            test[residual] = test[target] - expected
        else:
            test[residual] = expected - test[target]
        test = test.merge(labels, on=KEY, how="inner", validate="one_to_one")
        scoring_rows.append(test)
    result = pd.concat(scoring_rows, ignore_index=True)
    if result.duplicated(KEY).any() or result[pressure].isna().any():
        raise ValueError("OOS event sensitivity did not reconcile to labels.")
    return result


def player_estimates(
    rows: pd.DataFrame,
    role: str,
    *,
    training_sample: bool,
    residual_column: str = "sensitivity_residual",
) -> dict[int, dict]:
    player_column = "striker_id" if role == "batting" else "bowler_id"
    estimates = {}
    for player_id, group in rows.groupby(player_column):
        estimate = estimate_lift(
            group,
            f"{role}_0.2",
            residual_column,
            training_sample=training_sample,
        )
        if estimate is not None:
            estimates[int(player_id)] = estimate
    return estimates


def score(estimate: dict) -> float:
    n = estimate["pressure_events"]
    return float(estimate["lift"] * n / (n + POOLING_EVENTS))


def compare_fold(
    original: pd.DataFrame,
    alternative: pd.DataFrame,
    role: str,
    train_end: int,
    test_year: int,
    *,
    alternative_residual: str = "sensitivity_residual",
) -> dict:
    original_residual = f"{role}_residual"
    old_train = player_estimates(
        original[original.year <= train_end],
        role,
        training_sample=True,
        residual_column=original_residual,
    )
    old_test = player_estimates(
        original[original.year == test_year],
        role,
        training_sample=False,
        residual_column=original_residual,
    )
    alt_train = player_estimates(
        alternative[alternative.year <= train_end],
        role,
        training_sample=True,
        residual_column=alternative_residual,
    )
    alt_test = player_estimates(
        alternative[alternative.year == test_year],
        role,
        training_sample=False,
        residual_column=alternative_residual,
    )
    shared = sorted(old_train.keys() & old_test.keys() & alt_train.keys() & alt_test.keys())
    output = {
        "train_through": train_end,
        "test_year": test_year,
        "original_training_eligible": len(old_train),
        "alternative_training_eligible": len(alt_train),
        "matched_players": len(shared),
        "original": None,
        "alternative": None,
    }
    if not shared:
        return output
    for label, train, future in (
        ("original", old_train, old_test),
        ("alternative", alt_train, alt_test),
    ):
        predictions = np.array([score(train[player]) for player in shared])
        outcomes = np.array([future[player]["lift"] for player in shared])
        rho = (
            float(spearmanr(predictions, outcomes).statistic)
            if len(shared) > 2 and np.ptp(predictions) > 0 and np.ptp(outcomes) > 0
            else None
        )
        output[label] = {
            "spearman": rho,
            "rmse": float(np.sqrt(np.mean((predictions - outcomes) ** 2))),
            "mae": float(np.mean(np.abs(predictions - outcomes))),
        }
    return output


def role_result(
    original: pd.DataFrame,
    alternative: pd.DataFrame,
    role: str,
    names: dict[int, str],
    *,
    filtered: pd.DataFrame | None = None,
) -> dict:
    original_estimates = player_estimates(
        original,
        role,
        training_sample=True,
        residual_column=f"{role}_residual",
    )
    alternative_estimates = player_estimates(alternative, role, training_sample=True)
    original_ranking = sorted(
        ((score(value), player) for player, value in original_estimates.items()),
        reverse=True,
    )
    alternative_ranking = sorted(
        ((score(value), player) for player, value in alternative_estimates.items()),
        reverse=True,
    )
    original_top = {player for _, player in original_ranking[:10]}
    alternative_top = {player for _, player in alternative_ranking[:10]}
    folds = [
        compare_fold(original, alternative, role, end, year)
        for end, year in ((2023, 2024), (2024, 2025), (2025, 2026))
    ]
    result = {
        "original_eligible": len(original_ranking),
        "alternative_eligible": len(alternative_ranking),
        "top10_overlap": len(original_top & alternative_top),
        "original_top10": [
            {"name": names[player], "score": score_value}
            for score_value, player in original_ranking[:10]
        ],
        "alternative_top10": [
            {"name": names[player], "score": score_value}
            for score_value, player in alternative_ranking[:10]
        ],
        "folds": folds,
    }
    if filtered is not None:
        filtered_estimates = player_estimates(
            filtered,
            role,
            training_sample=True,
            residual_column=f"{role}_residual",
        )
        filtered_ranking = sorted(
            ((score(value), player) for player, value in filtered_estimates.items()),
            reverse=True,
        )
        filtered_top = {player for _, player in filtered_ranking[:10]}
        wide_pressure = (
            original.loc[
                original[f"{role}_0.2"] & original.extra.eq("wide")
            ].groupby("striker_id").size().to_dict()
        )
        alternative_scores = {
            player: value for value, player in alternative_ranking
        }
        filtered_scores = {player: value for value, player in filtered_ranking}
        result["filter_only"] = {
            "eligible": len(filtered_ranking),
            "top10_overlap_with_published": len(filtered_top & original_top),
            "top10": [
                {"name": names[player], "score": value}
                for value, player in filtered_ranking[:10]
            ],
            "published_top10_score_changes": [
                {
                    "name": names[player],
                    "pressure_wides_removed": int(wide_pressure.get(player, 0)),
                    "published_score": float(value),
                    "filter_only_score": float(filtered_scores[player])
                    if player in filtered_scores
                    else None,
                    "refit_legal_only_score": float(alternative_scores[player])
                    if player in alternative_scores
                    else None,
                }
                for value, player in original_ranking[:10]
            ],
            "folds": [
                compare_fold(
                    original,
                    filtered,
                    role,
                    end,
                    year,
                    alternative_residual=f"{role}_residual",
                )
                for end, year in ((2023, 2024), (2024, 2025), (2025, 2026))
            ],
        }
    return result


def run() -> dict:
    balls, labels = source_rows()
    evaluated = pd.read_parquet(ROOT / "artifacts" / "private" / "evaluated.parquet")
    results = {"analysis_id": json.loads((ROOT / "results" / "public" / "analysis.json").read_text())["analysis_id"]}
    batter_names = evaluated.groupby("striker_id").striker_name.agg(lambda s: s.mode().iloc[0])
    bowler_names = evaluated.groupby("bowler_id").bowler_name.agg(lambda s: s.mode().iloc[0])

    legal_batters = predict_oos(balls, labels, "batting", ("wide",))
    no_wide_scoring = evaluated[evaluated.extra.ne("wide")].copy()
    results["batter_wides"] = role_result(
        evaluated,
        legal_batters,
        "batting",
        batter_names.to_dict(),
        filtered=no_wide_scoring,
    )
    no_fielding_extras = predict_oos(balls, labels, "bowling", ("byes", "legbyes"))
    results["bowler_byes_legbyes"] = role_result(
        evaluated, no_fielding_extras, "bowling", bowler_names.to_dict()
    )
    return results


def main() -> None:
    result = run()
    print(f"Analysis: {result['analysis_id']}")
    for role_key in ("batter_wides", "bowler_byes_legbyes"):
        role = result[role_key]
        print(
            f"{role_key}: eligible {role['original_eligible']} -> "
            f"{role['alternative_eligible']}; top-10 overlap "
            f"{role['top10_overlap']}/10"
        )
        for fold in role["folds"]:
            print(
                f"  {fold['train_through']}->{fold['test_year']}: "
                f"matched={fold['matched_players']} "
                f"original={fold['original']} alternative={fold['alternative']}"
            )
        print(
            "  alternative top 10: "
            + ", ".join(p["name"] for p in role["alternative_top10"])
        )
        if "filter_only" in role:
            print(
                f"  filter-only eligible={role['filter_only']['eligible']}; "
                f"top-10 overlap={role['filter_only']['top10_overlap_with_published']}/10"
            )
            print(
                "  filter-only top 10: "
                + ", ".join(
                    player["name"] for player in role["filter_only"]["top10"]
                )
            )
            for filtered_fold in role["filter_only"]["folds"]:
                if filtered_fold["original"] is None or filtered_fold["alternative"] is None:
                    continue
                old = filtered_fold["original"]
                new = filtered_fold["alternative"]
                print(
                    f"    filter-only {filtered_fold['train_through']}->"
                    f"{filtered_fold['test_year']} matched={filtered_fold['matched_players']}: "
                    f"RMSE {old['rmse']:.1f}->{new['rmse']:.1f}; "
                    f"rho {old['spearman']}->{new['spearman']}"
                )
            for row in role["filter_only"]["published_top10_score_changes"]:
                print(
                    f"    {row['name']}: {row['pressure_wides_removed']} pressure wides; "
                    f"score {row['published_score']:.1f} -> "
                    f"{row['filter_only_score'] if row['filter_only_score'] is not None else 'ineligible'}; "
                    f"refit legal-only {row['refit_legal_only_score'] if row['refit_legal_only_score'] is not None else 'ineligible'}"
                )


if __name__ == "__main__":
    main()
