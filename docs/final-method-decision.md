# Final method decision for Monday submission

14 November 2026. Submission planned for Monday, 16 November 2026.

## Selected submission method

Retain the documented operational late-demand pressure definition and fixed-60 pressure-versus-usual run-lift ranking. Show pressure-only output, wickets/dismissals, sample support and uncertainty alongside it. This is a submission choice based on interpretability, the brief's requested comparison with usual performance, and lack of demonstrated superiority of tested replacements. It is not a claim of a scientifically validated or universally best pressure index.

Do not insert an arbitrary RRR cap, a fixed 12-run wicket bonus, or a 70/30 ranking blend solely to obtain familiar players. All methods contain assumptions; evidence must distinguish what was tested from what remains unverified.

## Common-cohort objective test

`analysis/ranking_objective_check.py` compares earlier-season scores on identical future-player cohorts and identical future outcomes. Absolute output is the shrunk pressure residual rate; lift subtracts the ordinary baseline. The proposed blend is 70% absolute plus 30% lift. Future outcome rates are unshrunk. These years were already inspected: this is exploratory sensitivity, not prospective confirmation.

| Holdout / role | Common players | Lift ranking vs future lift | Absolute ranking vs future lift | Blend ranking vs future lift |
|---|---:|---:|---:|---:|
| 2025 batting | 6 | .429 | .429 | .600 |
| 2025 bowling | 27 | .158 | .111 | .145 |
| 2026 batting | 15 | .150 | -.229 | -.007 |
| 2026 bowling | 33 | .112 | -.019 | .035 |

All displayed rank-correlation player-bootstrap intervals include zero. The blend's small 2025 batting advantage does not persist. Alternative objectives also show inconsistent results against future absolute output. No candidate earns a claim of predictive superiority. Player bootstrap bands condition on saved contextual models and do not capture all match dependence or model uncertainty; separate match-bootstrap/model-refit experiments are documented elsewhere. Wicket/dismissal rates are diagnostic targets only, not a validated runs-equivalent wicket metric.

## Pressure construct audit

Of 7,864 operationally labelled chase deliveries, 376 (4.8%) require more than six runs per remaining legal ball. This is a no-extras resource diagnostic, not strict mathematical impossibility. It demonstrates that the rule includes effectively decided or extremely unlikely chases. The method must be described as operational late-demand selection rather than a validated measure of leverage or mental pressure.

Actual-match leverage challengers with and without chronological calibration failed innings coverage, calibration and/or player-follow-up checks. A weaker candidate should not replace the baseline merely because leverage is conceptually attractive. Human-labelled review sheets remain unfilled; no independent construct validation is claimed. A genuinely new season is required for prospective player validation.

## What was not established

No universal pressure threshold, fitted optimal 60-event prior, causal effect of pressure, arbitrary constant wicket value, validated win-impact ranking, or 2027 auction eligibility has been established. The run-only omission of wicket value remains a limitation. Contextual performance still lacks full venue/opposition adjustment.

## Reproduce

Run `.venv\Scripts\python.exe analysis\ranking_objective_check.py`. Detailed outputs stay at `artifacts/private/ranking_objective_check.json`. The script does not overwrite public rankings. Existing validation, leverage and review commands are documented in their respective reports.


## Simple-stat baseline and paired comparison

The common-cohort check also ranks historical full-sample batting strike rate and bowling economy (negative economy so higher is better). It uses the same role-eligible players and future targets as the contextual candidates. The baseline uses only data through the training cutoff, and the future sample is not used to fit the historical ranking.

| Holdout / role | Current lift vs future lift | Simple rate vs future lift |
|---|---:|---:|
| 2025 batting (6) | .429 | -.086 |
| 2025 bowling (27) | .158 | -.072 |
| 2026 batting (15) | .150 | -.361 |
| 2026 bowling (33) | .112 | -.244 |

Paired player-bootstrap differences between simple rate and lift span zero in three cohorts. In 2026 bowling the difference interval is [-.695, -.042], favouring lift in that one exploratory cohort. This is not consistent confirmatory proof across roles, seasons or unseen data, especially after multiple comparisons. Absolute-output and blend alternatives likewise fail to show a strictly positive paired advantage consistently. The 2025 batting blend interval touches zero and contains only six players; it cannot justify new weights.

Audit scope: the score comparison uses saved rolling out-of-time residuals and common future outcomes. It does not introduce opponent/venue adjustment, fit a wicket valuation model, validate a pressure psychology construct, or remove survivorship from future sample requirements. The six-runs-per-ball edge audit flags a known construct weakness rather than fixing it with an invented cap. Production rankings remain unchanged. No claim is made that every source of uncertainty has been resolved.
