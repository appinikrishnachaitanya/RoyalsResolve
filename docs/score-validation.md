# Pressure score validation and recommendation

Reviewed 14 November 2026 against published analysis `80843dd8cd70f131`.

## Recommendation

Retain the fixed 60-event shrinkage as a provisional descriptive baseline. It is a transparent regularizer, not an estimated optimum. Neither fixed alternatives nor match-level empirical Bayes alternatives consistently improved out-of-time ordering. Do not describe the score as a validated prediction of future player performance or winning probability.

The revised production batting rankings now exclude wides from batter exposure and refit batting expectations on faced deliveries. This follows the meaning of a batter run contribution; predictive superiority is unproven. Keep bowling extras treatment under review rather than excluding byes and leg-byes merely because a sensitivity changes names.

## Formula

For each delivery, batting residual is bat runs minus contextual expected bat runs. Bowling residual is contextual expected charged runs minus charged runs. Expectations use StandardScaler and Ridge(alpha=60), fitted on earlier seasons only.

Within IPL and T20I separately, subtract the player's mean ordinary-situation residual from their pressure residuals. Let U be the sum of these differences and N the pressure event count:

`score = 100 * U / (N + 60)`

Equivalently, multiply the unshrunk pressure-versus-usual lift per 100 events by `N / (N + 60)`. More observations reduce shrinkage; this estimates a rate rather than cumulative career value. The Ridge penalty and the score's 60-event prior are separate choices.

## Rolling evidence

Models and player scores use earlier seasons; outcomes are next-season unshrunk pressure-versus-usual lifts. The comparisons are exploratory: these seasons have already been inspected during development.

| Train through / test | Role | Measurable players | Fixed-60 RMSE | Fixed-120 RMSE | Fixed-60 rank correlation |
|---|---|---:|---:|---:|---:|
| 2024 / 2025 | Batting | 7 | 44.7 | 44.9 | 0.29 |
| 2024 / 2025 | Bowling | 27 | 38.1 | 36.4 | 0.16 |
| 2025 / 2026 | Batting | 15 | 44.2 | 41.8 | 0.00 |
| 2025 / 2026 | Bowling | 33 | 43.4 | 42.6 | 0.11 |

All useful held-out match-bootstrap rank intervals include zero. Fixed-120 reduces error in three of these four comparisons, but its paired improvement over fixed-60 is clear in only the 2024/2025 bowling check. A zero predictor also competes with these scores on error, so lower error from stronger shrinkage does not establish useful player ordering.

Training-player match bootstrap standard errors were used for method-of-moments, REML, and zero-centered REML shrinkage candidates. None established consistent superiority. Future match resampling uses common match draws across players and reapplies future-label support rules; these intervals condition on trained predictions and frozen pressure labels.

## Coverage and limitations

Training eligibility requires 30 pressure events in 5 matches, 60 ordinary events in 5 matches, and ordinary support of 30 events in 3 matches within every pressure format. Future labels require 10 pressure events in 2 matches and ordinary support of 10 events in 2 matches per pressure format.

| 2026 follow-up of training cohort | Batting | Bowling |
|---|---:|---:|
| Training eligible | 43 | 93 |
| No future role rows | 6 | 25 |
| Future pressure sample too small | 20 | 33 |
| Ordinary baseline unsupported | 2 | 2 |
| Measurable future performance | 15 | 33 |

These performance tests describe a selected returning-player cohort. Missing role exposure is not zero skill. Availability and opportunity need separate evidence. IPL-only and T20I-only future results vary substantially with small cohorts; reliable cross-format transfer is unproven. Equal-season weighting also produced mixed results.

## Robustness checks

- All 20 published top-ten scores reproduce the documented formula.
- In 100 season-stratified training-match bootstraps, refitted Ridge expectations reproduced the baseline to approximately 3e-14. With pressure labels frozen, fixed-60 retained an average 94.8% of published batting top-ten names and 94.1% of bowling names. These are shortlist stability frequencies, not prediction accuracy or full uncertainty intervals.
- Fixed-120 retained 96.3% for batting and 90.5% for bowling in that check. No shrinkage retained 70.3% and 79.9% respectively.
- Wides comprise 752 of 15,200 pressure batting event rows. Excluding them from scoring and refitting expectations preserves 9 of 10 batting names but changes ordering. Matched-player holdout results improve in 2026 and worsen in 2025.
- Excluding byes and leg-byes from bowling model fitting and scoring worsens both later holdouts; this does not support that exclusion.
- Rankings measure runs only. Wicket value, opponent/venue adjustments, pressure-policy uncertainty, and prospective validation remain unresolved. The strict margin policy lacked coverage, so the published fallback definition must remain explicit.

## Reproduce

From the repository root:

```powershell
.venv\Scripts\python.exe analysis\score_validation.py --json-output tmp\score-validation.json
.venv\Scripts\python.exe analysis\event_sensitivity.py
.venv\Scripts\python.exe analysis\context_model_bootstrap.py
.venv\Scripts\python.exe -m unittest discover -s analysis\tests -v
```

The scripts read private supplied-data artifacts and do not overwrite production rankings. Public reports should expose findings and coverage, not the underlying private delivery files.

## Next implementation steps

1. Completed: batter-wide exposure correction across model fitting, score samples, supporting metrics and methodology; pipeline and report regenerated together.
2. Retain the transparent fixed-60 score provisionally and show match-based uncertainty, sample support, and sensitivity beside ordering.
3. State that future predictive superiority is unproven. Keep participation coverage visible in validation reporting.
4. Obtain a genuinely untouched future season before claiming forecasting improvement or selecting another prior from these experiments.
