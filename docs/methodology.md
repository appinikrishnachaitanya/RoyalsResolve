# Measurement and selection contract v2

## Data and reconstruction
Use supplied IPL and T20I data from 2022 onward. Other T20 competitions stay outside model training and ranking. Each scored season uses earlier seasons only; 2022 provides the initial training sample.

Team runs are batter runs + extras1 + extras2. Wides and source no-ball codes Overstep/other do not count as legal balls. Both no-ball codes always carry a one-run penalty. Every complete over containing them reconciles to six legal balls (489 Overstep overs and 216 other overs), and their dismissals are compatible with no-ball rules. On no-balls, charge the bowler for bat runs plus the no-ball penalty; secondary byes/leg-byes contribute only to team runs. This is an inferred, audited source mapping rather than a provider-confirmed dictionary.

Check complete-over lengths, regulation innings termination, winner, numeric run/wicket result margins, no-ball signatures and dismissal types. Exclude unresolved penalties, rain revisions with unknown target timing, incomplete records, super overs and contradictions. `analysis/recovery_review.py` reconstructs both the former blanket filter and the reconciled policy, including format-season coverage.

## Pressure situations
Use pre-delivery state only. A delivery qualifies if a chase has <=60 balls remaining and required rate >=8; a first innings has <=30 balls remaining and >=3 wickets lost; or at least two wickets fell in the preceding 12 legal balls. In chases, omit states requiring more than six runs per remaining legal ball. This no-extras plausibility filter does not mean winning is mathematically impossible.

Broader/narrower late-demand and late-demand-only scenarios are saved separately. They are sensitivity checks, not claims of a universal pressure standard.

## Contextual output and improvement
Ridge(alpha=60) with standardised pre-delivery features estimates batter or bowler-charged runs from earlier seasons. Features are balls used, wickets lost, score/(balls used+6), chase required rate, innings, powerplay/death indicators and IPL format. Batter residual = actual minus expected batter runs; bowling residual = expected minus actual charged runs. Batting excludes wides throughout.

IPL and T20I deliveries receive equal weight. Pressure output per 100 = 100 x weighted_mean(pressure residuals) x N/(N+60), where N is the actual number of pressure deliveries.

Improvement per 100 = 100 x weighted_mean[pressure residual - own ordinary mean residual in that format] x N/(N+60).

The usual level uses non-pressure deliveries within format; the combined baseline uses the same source weights and pressure exposure mix. For a single-format player, the source weight cancels, so T20I-only players use T20I alone. Weights do not create extra balls or matches. Alternative source weights were tested but not adopted; the submitted policy uses equal weights. Fixed +60 shrinkage is not a fitted optimal prior. Whole-player-match bootstrap uses 400 replicates; improvement replicates re-estimate the usual baseline. Pressure output gets a separate interval. Positive-pressure-match counts and the match median describe historical consistency, not a calibrated probability of future success.

## Research pool versus RR decision pool
The broad research pool requires >=30 pressure events/5 matches, >=60 ordinary events/5 matches, and >=30 ordinary events/3 matches within each pressure format. It includes T20I-only and emerging players.

The decision pool requires a supported role, but does not impose prior IPL participation. A role tag requires >=60 observed role events/5 matches. T20I-only players stay eligible. All players remain in the statistical list pending verification against Unstop dropdown eligibility; research nationality or participation is not a claim of legal IPL auction eligibility.

## Published selection order
First prioritise candidates whose pressure-output lower 95% bound is above zero; retain the others as a lower-support group. Within each group, batters sort by descending lower 95% pressure-output bound, then pressure-output estimate, match count and player ID. This is a conservative decision preference rather than a learned optimum. Improvement remains a separate diagnostic: low improvement does not rule out a consistently strong player.

For bowling, a separate earlier-season logistic model predicts credited-wicket probability. Run-outs are not credited to the bowler. Wicket contribution per 100 = 100 x weighted_mean(credited wicket - expected credited wicket) x N/(N+60). Resample whole matches for its interval.

Within each output-support group, form Pareto tiers using the lower confidence bounds of run control and wicket contribution: another candidate dominates a player only if it is at least as strong on both dimensions and stronger on one. Remove the first non-dominated tier and repeat. Within each tier, order by run-control lower bound, output, matches and ID. Thus wickets affect selection without inventing a runs-per-wicket exchange rate. Tiers are trade-off groups, not probabilities or claims of clear superiority.

## Evidence and checks
Keep observed runs, wickets, pressure format split, both score intervals, positive matches and single-match-removal improvement. Head-to-head comparisons use shared innings/phase/IPL strata and joint match-cluster resampling; they do not prove an auction upgrade. `analysis/coach_backtest.py` compares the decision policy, improvement and raw rate on identical future IPL cohorts. Later seasons were already inspected, so these are exploratory checks rather than sealed forecasts.

## RR strategy
Use the decision lists for role-first scouting, compare competing options within the same role, and review existing RR players as retention/role cases rather than new purchases. Verify 2027 registration, availability, roster need, price and overseas constraints before bidding. No purse, price band or verified squad gap is invented. The report contains a named high-level strategy with the evidence behind each option.


## Decision-objective audit and recruitment status

`analysis/decision_audit.py` independently reproduces the published ranks and sorting bounds, then recomputes the actual policy under pressure alternatives, IPL-only scoring, shrinkage 30/120, three extra seeds and 2,000 resamples. Model expectations remain fixed. Combined versus IPL-only top-ten overlap is 7/10 batting and 3/10 bowling; seed and threshold changes move close positions and some tiers. These results do not establish reliable future auction selection.

The PDF exposes both bowling lower-bound inputs and support group/tier, includes a numeric dominance example, and reports batting dismissals against contextual expectation without adding an arbitrary penalty.

`config/auction_evidence_2027.json` records dated cross-franchise release/retention evidence. Primary franchise statements override conflicting reporting; secondary-source statuses are marked. `analysis/recruitment.py` blocks retained, unavailable, unknown or conflicting cases from confirmed acquisition, and requires documented auction registration plus availability before admitting an actionable candidate. A release or Unstop dropdown entry alone does not satisfy that check. With no verified auction-entry list in this evidence file, the report provides released-player due diligence rather than fabricated confirmed purchases.
