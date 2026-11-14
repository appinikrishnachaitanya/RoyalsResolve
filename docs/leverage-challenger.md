# Leverage challenger: evaluation decision

14 November 2026. Published pressure rankings remain unchanged.

The challenger predicts actual match wins from pre-delivery score, wickets, resources, chase requirement and format. A polynomial logistic model is fitted on earlier years only, with equal aggregate fitting weight per match. First-innings terminal states are included without revealing the future chase target. Joint next-event run/legal-ball/wicket probabilities come from earlier deliveries grouped by innings, phase and format.

Leverage is the probability-weighted absolute change in predicted win probability across possible next events, divided by mean leverage in training data. A candidate LI >= 2 cutoff is exploratory, not an established cricket threshold. No actual next-ball result enters the pre-ball leverage calculation.

| Holdout year | First-innings Brier | Chase Brier | First-innings high-LI events | Chase high-LI events |
|---|---:|---:|---:|---:|
| 2023 | .214 | .128 | 0 | 943 |
| 2024 | .242 | .153 | 47 | 1508 |
| 2025 | .215 | .119 | 27 | 982 |
| 2026 | .242 | .084 | 3 | 283 |

Across all years only 14 batters and 18 bowlers meet the existing sample rules under this challenger. This pooled coverage hides the severe innings imbalance.

The hypothetical 50-from-6 chase has near-zero predicted probability and leverage. A target already achieved has probability one and zero leverage. However, the six-from-six probe varies from .91 to .99 predicted win probability across models, and its LI varies from .97 to 4.57. This does not establish calibrated close-finish behaviour. Held-out probability bins show sizeable calibration errors; for example, in the 2026 chase .4-.6 band the mean prediction is .49 versus observed wins of .82 (event-weighted).

Decision: do not promote this model into production rankings. Beating a constant win prior on Brier score does not validate pressure constructs, calibration or player ordering. First-innings/chase normalization, resource terminal transitions, monotonicity, state-conditional outcome probabilities, calibration fitted only on historical data and independent player backtests require further work. The current operational rule also has limitations; retaining it is not proof of superiority.

Reproduce with `.venv\Scripts\python.exe analysis\leverage_challenger.py`. Detailed diagnostics are written to `artifacts/private/leverage_challenger.json`; private source events are not published. This research script does not overwrite the dashboard JSON or methodology PDF.


## Version 2: separate innings and chronological calibration

Implemented `analysis/leverage_challenger_v2.py`. For each holdout year, the oldest 75% of historical matches fit separate innings models and the latest 25% calibrate them with Platt scaling. Fit, calibration and test matches are disjoint. The fitted model is not retrained on calibration matches. First-innings terminal states predict the actual batting team's match result, without using the eventual chase target. Leverage references are calculated separately for each innings using historical data; these represent relative intensity within innings, not equal absolute match stakes.

| Holdout | First-innings Brier | Chase Brier | First-innings LI >=2 events | Chase LI >=2 events |
|---|---:|---:|---:|---:|
| 2023 | .235 | .157 | 0 | 714 |
| 2024 | .241 | .136 | 12 | 387 |
| 2025 | .227 | .117 | 11 | 554 |
| 2026 | .252 | .101 | 7 | 171 |

This version fails the promotion gate. First-innings estimates remain weak and high-leverage coverage is sparse. Lowering the cutoff to 1.5 yields six measurable batters and seven bowlers in the 2026 player follow-up, with rank correlations of -.20 and -.21 respectively. Cohorts and outcome definitions differ from the operational rule, so these are diagnostic results rather than a matched-player superiority test. At cutoff 2, almost no training-eligible players have a supported future label. Positive aggregate match prediction skill has not established useful pressure labels or player ordering.

Private diagnostics contain real held-out match-state examples. These expose an operational-rule weakness: very high required rates in effectively decided chases still satisfy the current definition. For example, a recorded 2026 chase state needing 50 from one remaining ball is labelled by the operational rule while model leverage is negligible. These examples are construct checks, not independently adjudicated psychological-pressure labels. No claim is made that pressure must cause performance degradation.

Decision: retain the published operational rankings with their stated limitations; do not advertise either version as an approved pressure index. Further progress requires a coherent innings resource/outcome model, historical-only calibration with more independent matches, monotonicity validation, and prespecified pressure-label evaluation. This experiment does not modify the public JSON, ranking formula, or PDF.

Run `.venv\Scripts\python.exe analysis\leverage_challenger_v2.py`. Private output: `artifacts/private/leverage_challenger_v2.json`. Four added contracts cover chase completion, exhausted chases, first-innings terminal treatment, and probability-weighted absolute leverage. All 16 repository tests pass.
