# Pressure-definition review protocol

## Status and interpretation

108 real pre-delivery situations have been sampled: 56 development and 52 evaluation cases. Match IDs are disjoint between partitions and each match contributes at most one case. Sampling deliberately covers different situations; these are diagnostic panels, not estimates of pressure prevalence. These historical seasons have previously been inspected. No prospective holdout claim is made.

The current operational ranking rule is a hypothesis. Leverage versions 1 and 2 have not earned promotion. Human review supplies independent construct evidence; it does not measure actual emotions or establish causal choking.

## Independent review

Private sheets are in `artifacts/private/pressure_review/`. Give reviewer A and reviewer B their respective development sheets. Keep the private key, model results and evaluation sheets from reviewers during development. Two different cricket-informed people should review independently before discussing disagreements. No final match result or player reputation should influence labels.

For every case, fill `reviewer_id`, both labels and a brief reason:

- Difficulty 0: routine task; 1: demanding but manageable; 2: severely constrained task. First innings has no chase target: assess resource constraints and avoid inventing a venue par score.
- Stakes 0: the next delivery is unlikely to materially affect the result, including effectively decided chases; 1: meaningful but not critical; 2: the next delivery plausibly has substantial consequence for a live contest.
- A 50-from-one-ball chase may be difficulty 2 and stakes 0. A close final-over contest may score highly on both. Early 50-50 win probability alone does not establish high stakes.
- If context is inadequate, record that in `reason` and request adjudication; do not fabricate certainty. Incomplete labels intentionally block evaluation.

Do not score playoff status, dead-rubber status, surface or opposition strength from these sheets: those facts are not supplied. Stroke outcomes and what happened on this delivery are also excluded.

Run `python analysis/pressure_review.py --evaluate development` after both reviewers finish. The evaluator rejects incomplete labels, duplicate cases, different case sets or shared reviewer IDs, and reports separate axis agreement and weighted kappa. Operational-rule accuracy is computed only on consensus cases and is exploratory; preserve disagreement counts rather than hiding them.

## Proposed acceptance gates for subsequent candidates

These are project decision criteria, not an industry standard. They are recorded after prior experiments and must not be presented as preregistered historical research.

1. Data integrity: disjoint fit/calibration/test matches, pre-delivery features only, fixed source hashes, terminal outcomes handled correctly, and no performance labels filled with zero for missing opportunity.
2. Review quality: aim for weighted kappa >=0.60 on each axis. Below this, clarify the construct and repeat development review before model selection. Evaluation labels remain unopened until the candidate and cutoff are frozen.
3. Construct agreement: compare operational and candidate labels on exactly the same consensus cases. Require balanced accuracy >=0.70 on the intended axis, with match-level uncertainty reported. An improvement needs a paired interval excluding zero; small panels may not support this claim.
4. Match-probability models: report match-weighted Brier, calibration bands and sampling uncertainty separately by innings and format; require no material degradation against the historical constant-prior benchmark. Require sensible terminal and monotonicity checks on supported states. Brier improvement alone does not validate pressure labels.
5. Coverage: support ten eligible batters and ten bowlers under existing sample rules. Publish coverage by innings, format, season and phase. A pooled count concealing almost no first-innings coverage fails the gate.
6. Player evaluation: compare candidates on common players and common future outcomes as well as their own selected pressure samples. Report cohort attrition. Do not infer superiority by comparing errors on different player populations or differently defined targets.
7. Freeze after development: record code/config hashes and thresholds before opening evaluation labels. Use evaluation once for the frozen choice. Any changes after inspection require a new evaluation panel; a truly new season is needed for prospective forecasting validation.

## Remaining implementation work after review

Development labels guide whether we are targeting difficulty, stakes or a documented combination. A first-innings resource model needs separate evaluation; normalizing innings independently does not make their absolute stakes equivalent. The calibrated leverage prototype still fails coverage and player follow-up checks. Do not publish a new player ordering until the chosen definition passes the relevant gates and JSON, report and dashboard are regenerated together.

## Commands

`python analysis/pressure_review.py` builds private sheets and refuses to overwrite sheets containing reviewer IDs.

`python analysis/pressure_review.py --evaluate development` evaluates completed independent development reviews.

`python analysis/pressure_review.py --evaluate evaluation` is reserved for the frozen candidate review stage.

Private sheets and keys stay outside Git and public build artifacts. No reviewer labels have been generated automatically.
