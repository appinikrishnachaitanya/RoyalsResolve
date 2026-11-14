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
