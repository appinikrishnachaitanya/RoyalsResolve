"""Research diagnostics for pressure-score shrinkage.

Run from the repository root:
    .venv\\Scripts\\python.exe analysis\\score_validation.py

This script is deliberately separate from the production ranking pipeline. It
reads the saved rolling out-of-time event estimates and compares shrinkage
rules by how well a prior-season score orders a player's next-season pressure
lift. It does not change published results.
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "artifacts" / "private" / "evaluated.parquet"
RESULT_PATH = ROOT / "results" / "public" / "analysis.json"
SEED = 2718
BOOTSTRAPS = 1_000
FUTURE_MATCH_BOOTSTRAPS = 500
FOLDS = [(2023, 2024), (2024, 2025), (2025, 2026)]
DELIVERY_PRIORS = (0, 30, 60, 120, 240)
MATCH_PRIORS = (0, 1, 2, 3, 5, 10)


def estimate_lift(
    rows: pd.DataFrame,
    pressure_column: str,
    residual_column: str,
    *,
    training_sample: bool,
) -> dict | None:
    """Return format-matched pressure lift per 100 events and exposure counts."""
    if pressure_column.startswith("batting"):
        rows=rows.loc[rows.extra.ne("wide")]
    pressure = rows[rows[pressure_column].astype(bool)]
    usual = rows[~rows[pressure_column].astype(bool)]
    formats = pressure.is_ipl.unique()

    if training_sample:
        if (len(pressure) < 30 or pressure.match_id.nunique() < 5
                or len(usual) < 60 or usual.match_id.nunique() < 5):
            return None
        min_usual_events, min_usual_matches = 30, 3
    else:
        # Future outcomes are noisy labels, so retain only players with at
        # least a small pressure sample and a supported same-format baseline.
        if len(pressure) < 10 or pressure.match_id.nunique() < 2:
            return None
        min_usual_events, min_usual_matches = 10, 2

    for fmt in formats:
        usual_fmt = usual[usual.is_ipl == fmt]
        if (len(usual_fmt) < min_usual_events
                or usual_fmt.match_id.nunique() < min_usual_matches):
            return None

    n_pressure = len(pressure)
    delta_sum = 0.0
    for fmt in formats:
        pressure_fmt = pressure[pressure.is_ipl == fmt]
        usual_fmt = usual[usual.is_ipl == fmt]
        delta_sum += len(pressure_fmt) * (
            pressure_fmt[residual_column].mean()
            - usual_fmt[residual_column].mean()
        )

    return {
        "lift": 100.0 * delta_sum / n_pressure,
        "pressure_events": n_pressure,
        "pressure_matches": int(pressure.match_id.nunique()),
    }


def future_eligibility_coverage(
    train_ids: set[int],
    test_rows: pd.DataFrame,
    player_column: str,
    pressure_column: str,
    residual_column: str,
) -> dict:
    """Account for every training-eligible player in a future season.

    Absence of role exposure is reported as an availability/participation
    outcome. It is never inserted as a zero performance estimate.
    """
    future_groups = {
        int(player_id): group
        for player_id, group in test_rows.groupby(player_column)
    }
    counts = {
        "no_future_role_rows": 0,
        "future_rows_below_pressure_minimum": 0,
        "pressure_ok_baseline_unsupported": 0,
        "future_performance_evaluable": 0,
    }
    future_event_rows = 0
    for player_id in train_ids:
        group = future_groups.get(player_id)
        if group is None or group.empty:
            counts["no_future_role_rows"] += 1
            continue
        future_event_rows += len(group)
        estimate = estimate_lift(
            group, pressure_column, residual_column, training_sample=False
        )
        if estimate is not None:
            counts["future_performance_evaluable"] += 1
            continue
        pressure = group[group[pressure_column].astype(bool)]
        if len(pressure) < 10 or pressure.match_id.nunique() < 2:
            counts["future_rows_below_pressure_minimum"] += 1
        else:
            counts["pressure_ok_baseline_unsupported"] += 1
    counts["training_eligible_cohort"] = len(train_ids)
    counts["future_role_rows_in_cohort"] = int(future_event_rows)
    category_total = sum(
        counts[name]
        for name in (
            "no_future_role_rows",
            "future_rows_below_pressure_minimum",
            "pressure_ok_baseline_unsupported",
            "future_performance_evaluable",
        )
    )
    if category_total != len(train_ids):
        raise AssertionError("Future eligibility categories do not cover the cohort.")
    return counts


def match_cluster_se(
    rows: pd.DataFrame,
    pressure_column: str,
    residual_column: str,
    *,
    replicates: int,
    rng: np.random.Generator,
) -> float:
    """Bootstrap the format-matched lift by resampling whole player matches."""
    if pressure_column.startswith("batting"):
        rows=rows.loc[rows.extra.ne("wide")]
    pressure = rows[rows[pressure_column].astype(bool)]
    usual = rows[~rows[pressure_column].astype(bool)]
    formats = pressure.is_ipl.unique()
    match_ids = rows.match_id.unique()
    draw_indexes = rng.integers(
        0, len(match_ids), size=(replicates, len(match_ids))
    )
    lift_numerators = np.zeros(replicates)
    pressure_denominators = np.zeros(replicates)
    valid = np.ones(replicates, dtype=bool)

    for fmt in formats:
        p_by_match = (
            pressure[pressure.is_ipl == fmt]
            .groupby("match_id")[residual_column]
            .agg(["sum", "count"])
            .reindex(match_ids, fill_value=0)
            .to_numpy()
        )
        u_by_match = (
            usual[usual.is_ipl == fmt]
            .groupby("match_id")[residual_column]
            .agg(["sum", "count"])
            .reindex(match_ids, fill_value=0)
            .to_numpy()
        )
        p_sum = p_by_match[draw_indexes, 0].sum(axis=1)
        p_count = p_by_match[draw_indexes, 1].sum(axis=1)
        u_sum = u_by_match[draw_indexes, 0].sum(axis=1)
        u_count = u_by_match[draw_indexes, 1].sum(axis=1)
        usual_mean = np.divide(
            u_sum,
            u_count,
            out=np.zeros_like(u_sum),
            where=u_count > 0,
        )
        valid &= u_count > 0
        lift_numerators += p_sum - p_count * usual_mean
        pressure_denominators += p_count

    valid &= pressure_denominators > 0
    samples = 100.0 * lift_numerators[valid] / pressure_denominators[valid]
    if len(samples) < 100:
        return float("nan")
    return float(np.std(samples, ddof=1))


def future_match_bootstrap_outcomes(
    rows: pd.DataFrame,
    player_ids: list[int],
    pressure_column: str,
    residual_column: str,
    *,
    replicates: int,
    rng: np.random.Generator,
) -> dict[int, np.ndarray]:
    """Resample held-out matches jointly and recompute player pressure lifts.

    Every draw resamples the same match IDs for all players, preserving
    within-match dependence. Repeated draws of a match count as repeated
    bootstrap clusters. Each replicate reapplies the future-label exposure
    minimums; ineligible player estimates are NaN.
    """
    match_ids = rows.match_id.unique()
    if len(match_ids) == 0:
        return {player_id: np.full(replicates, np.nan) for player_id in player_ids}
    draw_indexes = rng.integers(0, len(match_ids), size=(replicates, len(match_ids)))
    multiplicities = np.zeros((replicates, len(match_ids)), dtype=np.int16)
    row_indexes = np.arange(replicates)[:, None]
    np.add.at(multiplicities, (row_indexes, draw_indexes), 1)
    fmt_values = rows.is_ipl.unique()
    player_arrays = {}
    for player_id in player_ids:
        group = rows[rows.striker_id == player_id] if pressure_column.startswith("batting") else rows[rows.bowler_id == player_id]
        pressure = group[pressure_column].astype(bool)
        arrays = {}
        for fmt in fmt_values:
            for label, selected in (("p", pressure), ("u", ~pressure)):
                parts = group[selected & (group.is_ipl == fmt)].groupby("match_id")[residual_column].agg(["sum", "count"])
                parts = parts.reindex(match_ids, fill_value=0)
                values = parts.to_numpy()
                arrays[(fmt, label, "sum")] = values[:, 0]
                arrays[(fmt, label, "count")] = values[:, 1]
        player_arrays[player_id] = arrays

    outcomes = {player_id: np.full(replicates, np.nan) for player_id in player_ids}
    for player_id, arrays in player_arrays.items():
        for replicate, weights in enumerate(multiplicities):
            pressure_total = 0
            pressure_matches = 0
            delta_total = 0.0
            eligible = True
            for fmt in fmt_values:
                p_counts = arrays[(fmt, "p", "count")]
                u_counts = arrays[(fmt, "u", "count")]
                p_count = int(p_counts @ weights)
                if p_count == 0:
                    continue
                u_count = int(u_counts @ weights)
                u_matches = int(((u_counts > 0) @ weights))
                if u_count < 10 or u_matches < 2:
                    eligible = False
                    break
                p_matches = int(((p_counts > 0) @ weights))
                pressure_matches += p_matches
                pressure_total += p_count
                p_sum = float(arrays[(fmt, "p", "sum")] @ weights)
                u_sum = float(arrays[(fmt, "u", "sum")] @ weights)
                delta_total += p_sum - p_count * u_sum / u_count
            if eligible and pressure_total >= 10 and pressure_matches >= 2:
                outcomes[player_id][replicate] = 100.0 * delta_total / pressure_total
    return outcomes


def summarize_future_match_bootstrap(
    predictions: np.ndarray,
    player_ids: list[int],
    bootstrapped_outcomes: dict[int, np.ndarray],
) -> dict:
    """Summarize score error and rank association over held-out match draws."""
    rmse_samples, mae_samples, rho_samples = future_match_metric_samples(
        predictions, player_ids, bootstrapped_outcomes
    )

    def interval(values: list[float]) -> list[float] | None:
        if not values:
            return None
        return [float(x) for x in np.quantile(values, [0.025, 0.975])]

    return {
        "valid_replicates": len(rmse_samples),
        "rmse_95": interval(rmse_samples),
        "mae_95": interval(mae_samples),
        "spearman_95": interval(rho_samples),
    }


def future_match_metric_samples(
    predictions: np.ndarray,
    player_ids: list[int],
    bootstrapped_outcomes: dict[int, np.ndarray],
) -> tuple[list[float], list[float], list[float]]:
    """Return paired match-bootstrap errors and rank correlations."""
    replicates = len(next(iter(bootstrapped_outcomes.values()))) if bootstrapped_outcomes else 0
    rmses, maes, rhos = [], [], []
    for replicate in range(replicates):
        valid = np.array([
            np.isfinite(bootstrapped_outcomes[player_id][replicate])
            for player_id in player_ids
        ])
        if not valid.any():
            continue
        prediction = predictions[valid]
        outcome = np.array([
            bootstrapped_outcomes[player_id][replicate]
            for player_id, keep in zip(player_ids, valid)
            if keep
        ])
        rmses.append(float(np.sqrt(np.mean((prediction - outcome) ** 2))))
        maes.append(float(np.mean(np.abs(prediction - outcome))))
        if len(outcome) >= 3 and np.ptp(prediction) > 0 and np.ptp(outcome) > 0:
            rhos.append(float(spearmanr(prediction, outcome).statistic))

    return rmses, maes, rhos


def rank_interval(
    predictions: np.ndarray,
    outcomes: np.ndarray,
    *,
    rng: np.random.Generator,
    replicates: int = 500,
) -> tuple[float | None, float | None, float | None]:
    """Return Spearman rho and a player-resampling interval for descriptive use."""
    if len(outcomes) < 3 or np.ptp(predictions) == 0 or np.ptp(outcomes) == 0:
        return None, None, None
    rho = float(spearmanr(predictions, outcomes).statistic)
    indexes = rng.integers(0, len(outcomes), size=(replicates, len(outcomes)))
    estimates = []
    for index in indexes:
        x, y = predictions[index], outcomes[index]
        if np.ptp(x) > 0 and np.ptp(y) > 0:
            estimates.append(float(spearmanr(x, y).statistic))
    if not estimates:
        return rho, float("nan"), float("nan")
    low, high = np.quantile(estimates, [0.025, 0.975])
    return rho, float(low), float(high)


def summarize_pair(
    predictions: np.ndarray,
    outcomes: np.ndarray,
    *,
    rng: np.random.Generator,
    interval: bool = False,
) -> dict:
    result = {
        "rmse": float(np.sqrt(np.mean((predictions - outcomes) ** 2))),
        "mae": float(np.mean(np.abs(predictions - outcomes))),
    }
    if len(outcomes) >= 3 and np.ptp(predictions) > 0 and np.ptp(outcomes) > 0:
        result["spearman"] = float(spearmanr(predictions, outcomes).statistic)
    else:
        result["spearman"] = None
    if interval:
        rho, low, high = rank_interval(predictions, outcomes, rng=rng)
        result["spearman_player_bootstrap_95"] = [low, high]
    return result


def format_transfer_check(
    rows: pd.DataFrame,
    train_estimates: dict[int, dict],
    role: str,
    pressure_column: str,
    player_column: str,
    *,
    rng: np.random.Generator,
) -> dict:
    """Score pooled history against next-season IPL-only and T20I-only lifts."""
    output = {}
    for is_ipl, label in ((True, "IPL"), (False, "T20I")):
        future = {}
        format_rows = rows[rows.is_ipl == is_ipl]
        for player_id, group in format_rows.groupby(player_column):
            estimate = estimate_lift(
                group,
                pressure_column,
                f"{role}_residual",
                training_sample=False,
            )
            if estimate is not None:
                future[int(player_id)] = estimate
        shared = sorted(set(train_estimates) & set(future))
        result = {"future_eligible": len(future), "matched_players": len(shared), "comparisons": {}}
        if shared:
            outcomes = np.array([future[player_id]["lift"] for player_id in shared])
            for prior in (0, 60, 120):
                predictions = np.array([
                    estimate["lift"] * estimate["pressure_events"]
                    / (estimate["pressure_events"] + prior)
                    if prior else estimate["lift"]
                    for estimate in (train_estimates[player_id] for player_id in shared)
                ])
                result["comparisons"][f"delivery_prior_{prior}"] = summarize_pair(
                    predictions,
                    outcomes,
                    rng=rng,
                    interval=prior in (0, 60),
                )
        output[label] = result
    return output


def equal_season_weight_check(
    train_groups: dict[int, pd.DataFrame],
    train_estimates: dict[int, dict],
    future_estimates: dict[int, dict],
    role: str,
    pressure_column: str,
    *,
    pooling_events: int,
    rng: np.random.Generator,
) -> dict:
    """Compare pooled event weights with a mean of supported season lifts.

    Season lifts need at least 10 pressure events across 2 matches and
    same-format usual support of 10 events across 2 matches. Players need two
    supported historical seasons; both predictions use the same total-event
    shrinkage factor and are evaluated on the same next-season cohort.
    """
    predictions = {}
    season_counts = {}
    for player_id, group in train_groups.items():
        seasonal = []
        for _, season in group.groupby("year"):
            estimate = estimate_lift(
                season,
                pressure_column,
                f"{role}_residual",
                training_sample=False,
            )
            if estimate is not None:
                seasonal.append(estimate["lift"])
        if len(seasonal) < 2:
            continue
        exposure = train_estimates[player_id]["pressure_events"]
        shrink = exposure / (exposure + pooling_events)
        predictions[player_id] = {
            "pooled": train_estimates[player_id]["lift"] * shrink,
            "equal_season": float(np.mean(seasonal)) * shrink,
            "supported_seasons": len(seasonal),
        }
        season_counts[player_id] = len(seasonal)

    shared = sorted(set(predictions) & set(future_estimates))
    output = {"training_players_with_two_supported_seasons": len(predictions), "matched_players": len(shared)}
    if not shared:
        output["comparisons"] = {}
        return output
    outcomes = np.array([future_estimates[player_id]["lift"] for player_id in shared])
    output["comparisons"] = {}
    for method in ("pooled", "equal_season"):
        values = np.array([predictions[player_id][method] for player_id in shared])
        output["comparisons"][method] = summarize_pair(
            values, outcomes, rng=rng, interval=True
        )
    output["mean_supported_seasons_per_matched_player"] = float(
        np.mean([season_counts[player_id] for player_id in shared])
    )
    return output


def fit_random_effects_prior(estimates: list[dict]) -> dict:
    """Fit a normal-normal random-effects prior using restricted likelihood."""
    lifts = np.array([x["lift"] for x in estimates], dtype=float)
    sampling_variances = np.array(
        [x["cluster_se"] ** 2 for x in estimates], dtype=float
    )
    if len(lifts) < 2:
        return {
            "mean": float(lifts.mean()) if len(lifts) else 0.0,
            "variance": 0.0,
            "observed_variance": None,
            "mean_sampling_variance": None,
            "method": "REML unavailable with fewer than two training players",
        }

    def restricted_log_likelihood(prior_variance: float) -> float:
        total_variance = sampling_variances + prior_variance
        weights = 1.0 / total_variance
        mean = float(np.sum(weights * lifts) / np.sum(weights))
        residual_sum = float(np.sum(weights * (lifts - mean) ** 2))
        return -0.5 * float(
            np.log(total_variance).sum()
            + np.log(weights.sum())
            + residual_sum
            + (len(lifts) - 1) * np.log(2 * np.pi)
        )

    upper = max(float(lifts.var(ddof=1) + sampling_variances.mean()) * 10, 1.0)
    optimum = minimize_scalar(
        lambda value: -restricted_log_likelihood(value),
        bounds=(0.0, upper),
        method="bounded",
        options={"xatol": 1e-6},
    )
    candidates = [0.0, float(optimum.x), upper]
    variance = max(candidates, key=restricted_log_likelihood)
    total_variance = sampling_variances + variance
    weights = 1.0 / total_variance
    mean = float(np.sum(weights * lifts) / np.sum(weights))
    return {
        "mean": mean,
        "variance": float(variance),
        "observed_variance": float(lifts.var(ddof=1)),
        "mean_sampling_variance": float(sampling_variances.mean()),
        "method": "normal-normal REML prior from all training-eligible players",
    }


def run() -> dict:
    if not DATA_PATH.is_file() or not RESULT_PATH.is_file():
        raise FileNotFoundError(
            "Run analysis/pipeline.py first; validation needs the private "
            "evaluated parquet and its public analysis manifest."
        )

    rows = pd.read_parquet(DATA_PATH)
    published = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if not (rows.is_ipl | rows.is_t20i).all():
        raise ValueError("Evaluated data contains a competition outside IPL/T20I.")
    if rows.duplicated(["match_id", "innings", "innings_ball_num"]).any():
        raise ValueError("Evaluated data contains duplicate deliveries.")

    output = {
        "analysis_id": published["analysis_id"],
        "purpose": "Exploratory next-season prediction; not a confirmatory test.",
        "published_score_check": {"formula": "100 * uplift_sum / (pressure_events + pooling_balls)", "pooling_balls": published["config"]["pooling_balls"], "checked": 0},
        "eligibility": {
            "training": "30 pressure events/5 matches; 60 usual events/5 matches; per-pressure-format usual baseline >=30 events/3 matches.",
            "future_label": "10 pressure events/2 matches; per-pressure-format usual baseline >=10 events/2 matches.",
            "limitation": "Future performance labels condition on a usable next-season sample; no role exposure is reported separately and is not assigned zero skill.",
        },
        "folds": [],
    }
    player_columns = {
        "batting": ("batting_0.2", "striker_id"),
        "bowling": ("bowling_0.2", "bowler_id"),
    }

    for role_name in ("batters", "bowlers"):
        for player in published[role_name]:
            reproduced = 100.0 * player["uplift_sum"] / (
                player["balls"] + published["config"]["pooling_balls"]
            )
            if not np.isclose(reproduced, player["score"], atol=0.001):
                raise AssertionError(f"Published score formula mismatch: {player['name']}")
            output["published_score_check"]["checked"] += 1

    for train_end, test_year in FOLDS:
        train_rows = rows[rows.year <= train_end]
        test_rows = rows[rows.year == test_year]
        fold = {"train_through": train_end, "test_year": test_year, "roles": {}}
        for role, (pressure_column, player_column) in player_columns.items():
            residual_column = f"{role}_residual"
            train_estimates: dict[int, dict] = {}
            train_groups: dict[int, pd.DataFrame] = {}
            for player_id, group in train_rows.groupby(player_column):
                estimate = estimate_lift(
                    group, pressure_column, residual_column, training_sample=True
                )
                if estimate is not None:
                    train_estimates[int(player_id)] = estimate
                    train_groups[int(player_id)] = group

            future_estimates = {}
            for player_id, group in test_rows.groupby(player_column):
                estimate = estimate_lift(
                    group, pressure_column, residual_column, training_sample=False
                )
                if estimate is not None:
                    future_estimates[int(player_id)] = estimate

            shared_ids = sorted(set(train_estimates) & set(future_estimates))
            coverage = future_eligibility_coverage(
                set(train_estimates),
                test_rows,
                player_column,
                pressure_column,
                residual_column,
            )
            if not shared_ids:
                fold["roles"][role] = {
                    "training_eligible": len(train_estimates),
                    "future_evaluable": 0,
                    "future_eligibility_coverage": coverage,
                    "comparisons": {},
                }
                continue

            # Estimate the empirical prior from the full training-eligible set,
            # not only the players who happen to qualify in the future season.
            rng = np.random.default_rng(SEED + train_end + (role == "bowling"))
            for player_id, group in train_groups.items():
                train_estimates[player_id]["cluster_se"] = match_cluster_se(
                    group,
                    pressure_column,
                    residual_column,
                    replicates=BOOTSTRAPS,
                    rng=rng,
                )

            all_training = [
                estimate
                for estimate in train_estimates.values()
                if np.isfinite(estimate["cluster_se"])
            ]
            train_lifts = np.array([x["lift"] for x in all_training])
            train_variances = np.array([x["cluster_se"] ** 2 for x in all_training])
            if len(train_lifts) > 1:
                prior_mean = float(train_lifts.mean())
                observed_variance = float(train_lifts.var(ddof=1))
                mean_sampling_variance = float(train_variances.mean())
                moment_variance = max(
                    0.0, observed_variance - mean_sampling_variance
                )
            else:
                prior_mean = float(train_lifts.mean()) if len(train_lifts) else 0.0
                observed_variance = None
                mean_sampling_variance = None
                moment_variance = 0.0
            reml_prior = fit_random_effects_prior(all_training)

            outcomes = np.array([future_estimates[i]["lift"] for i in shared_ids])
            training = [train_estimates[i] for i in shared_ids]
            future_cluster_outcomes = future_match_bootstrap_outcomes(
                test_rows,
                shared_ids,
                pressure_column,
                residual_column,
                replicates=FUTURE_MATCH_BOOTSTRAPS,
                rng=rng,
            )

            def compare_prediction(prediction: np.ndarray, *, interval: bool = False) -> dict:
                summary = summarize_pair(
                    prediction, outcomes, rng=rng, interval=interval
                )
                summary["future_match_cluster_bootstrap_95"] = (
                    summarize_future_match_bootstrap(
                        prediction, shared_ids, future_cluster_outcomes
                    )
                )
                return summary

            comparisons = {}
            predictions_by_method: dict[str, np.ndarray] = {}
            for prior in DELIVERY_PRIORS:
                prediction = np.array([
                    x["lift"] * x["pressure_events"]
                    / (x["pressure_events"] + prior)
                    for x in training
                ])
                comparisons[f"delivery_prior_{prior}"] = compare_prediction(
                    prediction, interval=prior in (0, 60)
                )
                predictions_by_method[f"delivery_prior_{prior}"] = prediction
            for prior in MATCH_PRIORS:
                prediction = np.array([
                    x["lift"] * x["pressure_matches"]
                    / (x["pressure_matches"] + prior)
                    for x in training
                ])
                comparisons[f"match_prior_{prior}"] = compare_prediction(prediction)
                predictions_by_method[f"match_prior_{prior}"] = prediction
            empirical_bayes_mom = np.array([
                prior_mean
                + moment_variance / (moment_variance + x["cluster_se"] ** 2)
                * (x["lift"] - prior_mean)
                if moment_variance > 0
                else prior_mean
                for x in training
            ])
            comparisons["match_cluster_empirical_bayes"] = compare_prediction(
                empirical_bayes_mom, interval=True
            )
            predictions_by_method["match_cluster_empirical_bayes"] = empirical_bayes_mom
            empirical_bayes_reml = np.array([
                reml_prior["mean"]
                + reml_prior["variance"]
                / (reml_prior["variance"] + x["cluster_se"] ** 2)
                * (x["lift"] - reml_prior["mean"])
                if reml_prior["variance"] > 0
                else reml_prior["mean"]
                for x in training
            ])
            empirical_bayes_reml_zero = np.array([
                reml_prior["variance"]
                / (reml_prior["variance"] + x["cluster_se"] ** 2)
                * x["lift"]
                if reml_prior["variance"] > 0
                else 0.0
                for x in training
            ])
            comparisons["match_cluster_reml"] = compare_prediction(
                empirical_bayes_reml, interval=True
            )
            predictions_by_method["match_cluster_reml"] = empirical_bayes_reml
            comparisons["match_cluster_reml_zero_centered"] = compare_prediction(
                empirical_bayes_reml_zero, interval=True
            )
            predictions_by_method["match_cluster_reml_zero_centered"] = (
                empirical_bayes_reml_zero
            )
            zero_prediction = np.zeros_like(outcomes)
            comparisons["zero_prediction"] = compare_prediction(zero_prediction)
            predictions_by_method["zero_prediction"] = zero_prediction
            baseline_rmse, baseline_mae, _ = future_match_metric_samples(
                predictions_by_method["delivery_prior_60"],
                shared_ids,
                future_cluster_outcomes,
            )
            for method, prediction in predictions_by_method.items():
                method_rmse, method_mae, _ = future_match_metric_samples(
                    prediction, shared_ids, future_cluster_outcomes
                )
                comparisons[method]["paired_error_difference_vs_delivery_prior_60_95"] = {
                    "rmse": [
                        float(value)
                        for value in np.quantile(
                            np.asarray(method_rmse) - np.asarray(baseline_rmse),
                            [0.025, 0.975],
                        )
                    ],
                    "mae": [
                        float(value)
                        for value in np.quantile(
                            np.asarray(method_mae) - np.asarray(baseline_mae),
                            [0.025, 0.975],
                        )
                    ],
                    "interpretation": "negative values favor the candidate over fixed 60-event shrinkage",
                }
            format_sensitivity = format_transfer_check(
                test_rows,
                train_estimates,
                role,
                pressure_column,
                player_column,
                rng=rng,
            )
            season_sensitivity = equal_season_weight_check(
                train_groups,
                train_estimates,
                future_estimates,
                role,
                pressure_column,
                pooling_events=published["config"]["pooling_balls"],
                rng=rng,
            )
            fold["roles"][role] = {
                "training_eligible": len(train_estimates),
                "future_evaluable": len(shared_ids),
                "future_eligibility_coverage": coverage,
                "format_transfer": format_sensitivity,
                "season_weight_sensitivity": season_sensitivity,
                "prior_estimation": {
                    "method_of_moments_mean_lift": prior_mean,
                    "observed_training_lift_variance": observed_variance,
                    "mean_match_bootstrap_variance": mean_sampling_variance,
                    "method_of_moments_between_player_variance": moment_variance,
                    "reml": reml_prior,
                },
                "comparisons": comparisons,
            }
        output["folds"].append(fold)

    output["full_window_ranking_sensitivity"] = {}
    for role, (pressure_column, player_column) in player_columns.items():
        residual_column = f"{role}_residual"
        name_column = "striker_name" if role == "batting" else "bowler_name"
        estimates = {}
        for player_id, group in rows.groupby(player_column):
            estimate = estimate_lift(
                group, pressure_column, residual_column, training_sample=True
            )
            if estimate is not None:
                estimate["name"] = str(group[name_column].mode().iloc[0])
                estimates[int(player_id)] = estimate
        published_ids = {int(player["id"]) for player in published["batters" if role == "batting" else "bowlers"]}
        sensitivity = {}
        for prior in DELIVERY_PRIORS:
            ranking = sorted(
                (
                    (
                        estimate["lift"] * estimate["pressure_events"]
                        / (estimate["pressure_events"] + prior)
                        if prior
                        else estimate["lift"],
                        player_id,
                    )
                    for player_id, estimate in estimates.items()
                ),
                reverse=True,
            )
            top_ten = ranking[:10]
            sensitivity[str(prior)] = {
                "top10_overlap_with_published": sum(
                    player_id in published_ids for _, player_id in top_ten
                ),
                "top10": [
                    {
                        "id": player_id,
                        "name": estimates[player_id]["name"],
                        "score": float(score),
                        "pressure_events": int(estimates[player_id]["pressure_events"]),
                    }
                    for score, player_id in top_ten
                ],
            }
        output["full_window_ranking_sensitivity"][role] = sensitivity
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for the full machine-readable diagnostics.",
    )
    args = parser.parse_args()
    result = run()
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
        )
    print(f"Analysis: {result['analysis_id']}")
    print(f"Published formula reconciled: {result['published_score_check']['checked']} top-ten scores")
    print("Metric: next-season lift; intervals resample players and held-out matches separately.")
    for fold in result["folds"]:
        for role, item in fold["roles"].items():
            print(
                f"\n{role.title()} {fold['train_through']} -> {fold['test_year']}: "
                f"training eligible={item['training_eligible']}, "
                f"future evaluable={item['future_evaluable']}"
            )
            coverage = item.get("future_eligibility_coverage")
            if coverage:
                print(
                    "  future cohort: "
                    f"no role rows={coverage['no_future_role_rows']}, "
                    f"below pressure minimum={coverage['future_rows_below_pressure_minimum']}, "
                    f"baseline unsupported={coverage['pressure_ok_baseline_unsupported']}, "
                    f"measurable={coverage['future_performance_evaluable']}"
                )
            for name in (
                "delivery_prior_0",
                "delivery_prior_60",
                "delivery_prior_120",
                "delivery_prior_240",
                "match_prior_5",
                "match_cluster_empirical_bayes",
                "match_cluster_reml",
                "match_cluster_reml_zero_centered",
                "zero_prediction",
            ):
                metric = item["comparisons"].get(name)
                if metric is None:
                    continue
                rho = metric["spearman"]
                interval = metric.get("spearman_player_bootstrap_95")
                player_interval_text = (
                    f"player95=[{interval[0]:.2f},{interval[1]:.2f}]"
                    if interval and interval[0] is not None
                    else ""
                )
                match_interval = metric["future_match_cluster_bootstrap_95"]
                match_rho = match_interval["spearman_95"]
                match_rho_text = (
                    f"match95=[{match_rho[0]:.2f},{match_rho[1]:.2f}]"
                    if match_rho
                    else "match95=NA"
                )
                match_rmse = match_interval["rmse_95"]
                match_rmse_text = (
                    f"RMSE95=[{match_rmse[0]:.1f},{match_rmse[1]:.1f}]"
                    if match_rmse
                    else "RMSE95=NA"
                )
                rho_text = f"rho={rho:.2f}" if rho is not None else "rho=NA"
                print(
                    f"  {name:31} RMSE={metric['rmse']:.1f} "
                    f"MAE={metric['mae']:.1f} {rho_text} "
                    f"{player_interval_text} {match_rho_text} {match_rmse_text}"
                )
            prior = item.get("prior_estimation")
            if prior:
                print(
                    "  prior variance: "
                    f"MoM={prior['method_of_moments_between_player_variance']:.1f}; "
                    f"REML={prior['reml']['variance']:.1f}; "
                    f"mean match-bootstrap variance={prior['mean_match_bootstrap_variance']:.1f}"
                )
            season_check = item.get("season_weight_sensitivity", {})
            season_comparisons = season_check.get("comparisons", {})
            if "pooled" in season_comparisons and "equal_season" in season_comparisons:
                print(
                    f"  equal-season check n={season_check['matched_players']}: "
                    f"RMSE pooled={season_comparisons['pooled']['rmse']:.1f}, "
                    f"equal={season_comparisons['equal_season']['rmse']:.1f}; "
                    f"mean supported seasons={season_check['mean_supported_seasons_per_matched_player']:.1f}"
                )
            for fmt, check in item.get("format_transfer", {}).items():
                k60 = check["comparisons"].get("delivery_prior_60")
                if k60 is not None:
                    print(
                        f"  {fmt} transfer n={check['matched_players']}: "
                        f"K60 RMSE={k60['rmse']:.1f}, rho={k60['spearman']}"
                    )
    if args.json_output:
        print(f"Full diagnostics: {args.json_output}")
    for role, prior_results in result["full_window_ranking_sensitivity"].items():
        print(f"\nFull-window {role} top-10 sensitivity")
        for prior, item in prior_results.items():
            print(
                f"  prior={prior:>3}: overlap with published="
                f"{item['top10_overlap_with_published']}/10; "
                + ", ".join(player["name"] for player in item["top10"])
            )


if __name__ == "__main__":
    main()
