# Royals' Resolve

**Find the nerve. Back the talent.** Independent SupeRR Selector research entry; not an official Rajasthan Royals product.

## Implemented

Local ZIP/CSVs -> audit/DuckDB/Parquet -> chronological Python models -> selected aggregate JSON/PDF -> static React/TypeScript dashboard. No cloud training, runtime AI, source-data upload or API backend.

Two ordered top-ten lists, four-pick landing panel, three core tabs, role filters, score audits, six coach metrics, supported matchup splits, raw-stat comparisons, later-season backtests, candidate/incumbent comparisons and fixed-fit sensitivity checks. Every pick has a six-part conditional RR case. A private replay of real passages stays outside publication.

Unsupported price, age, availability, replacement-win and squad-simulation features are omitted. The latest verified RR source is labelled **Squad 2026**, accessed 2026-11-12, not a 2027 retention list. No quality gap or purchase recommendation is invented.

## Actual findings

The supplied pack contains **200,999 deliveries / 883 matches**, dated **2022-01-22 to 2026-11-01**. All six CSVs and the bundled brief were read. Upstream provider (for example Cricsheet) is not established by these files.

Conservative reconstruction retains **80,902 events / 345 matches / 690 innings**, excluding **120,097 events / 538 matches / 1,034 observed innings**. Reasons overlap. Ambiguous Overstep/other extras affect 486 matches, causing major selection bias. Revised target timing, incomplete innings, super overs, ties and unreconciled results are quarantined. Impact substitutes retain separate IDs and actual exposures; XI rows are not forced into eleven unique players.

Strict margin tolerance leaves **one eligible batter and 58 bowlers**, failing two-list coverage. The provisional published lists use the explicit **phase/required-rate fallback for both roles**, yielding 116 eligible batters and 132 bowlers. Sample requirements were not lowered to fill the lists.

Fallback: chase with <=60 legal balls remaining and required rate >=8 runs/over, or first innings with <=30 balls remaining and >=3 wickets lost. Rank contextual run residuals; wickets stay separate. This is a coverage fallback, not a validated superior pressure measure.

2022 is warm-up. 63,226 events / 271 matches are evaluated using earlier-year models in 2023-2026. Logistic Brier scores are approximately 0.127, 0.148, 0.134, 0.135: task viability, not psychological-pressure accuracy. Later-player checks are mixed. In 2026 batting, contextual picks show +29.637 runs/100 versus +27.132 for ordinary-rate picks, with different participation (6/10 versus 5/10). All displayed 2026 bowling policies have negative future residuals. No uniform superiority or prospectively sealed holdout is claimed.

## Layout

| Path | Purpose |
| --- | --- |
| analysis/audit.py | Safe ZIP/directory input, hashes, schema, aliases, private DuckDB/Parquet |
| analysis/pipeline.py | Reconstruction, chronological models, pressure labels, scores/export |
| analysis/supporting.py | Coach metrics, common-assignment comparisons, selection checks |
| analysis/decision_views.py | Small decision aggregates, matchups, private replay |
| analysis/report.py | Matching PDF and frontend publication copies |
| analysis/tests/ | Synthetic contracts and real export consistency |
| config/ | Executable methodology and public-source provenance |
| docs/methodology.md | Equations, denominators, exclusions and limitations |
| results/public/ | Selected aggregate JSON and generated PDF only |
| frontend/ | React/TypeScript/Vite source and dependency lock |
| deploy/ | Non-root production server and HTTP checks |
| artifacts/private/ | Local-only audit, full tables, replay, PDF review images |

## Reproduce (PowerShell)

Use **Python 3.10 and Node 24**. Exact Python versions are in analysis/requirements.lock.txt; JavaScript versions in frontend/package-lock.json.

Place the supplied ZIP at data/incoming/pack.zip or pass the actual path. The current checkout already contains the operator-supplied ZIP, ignored by Git. Missing/invalid input raises an error; no silent synthetic fallback.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r analysis/requirements.lock.txt
.venv\Scripts\python analysis/audit.py --input-zip data/incoming/pack.zip
# Alternative: --input-dir C:\path\to\CSVs
.venv\Scripts\python analysis/pipeline.py
.venv\Scripts\python analysis/report.py
.venv\Scripts\python -m unittest discover -s analysis/tests -v
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python analysis/check_publication.py
npm --prefix frontend run preview
```

Without input arguments, audit checks pack.zip, then accepts a single ZIP in data/incoming/. Multiple candidates require an explicit path. Nested archives are capped at three levels and 512 MiB expanded members. Traversal, absolute paths, symlinks and ambiguous duplicate CSVs are rejected.

Private reconciliation: artifacts/private/exclusions.json. Real-passage review: artifacts/private/replay.html (do not publish). Public JSON contains selected aggregates, schema names, counts, hashes and diagnostics, never complete source records. Source maps are disabled.

Production server:

```powershell
$env:STATIC_ROOT = (Resolve-Path frontend/dist).Path
$env:PORT = '8080'
node deploy/server.mjs
# Separate terminal:
node deploy/check-static.mjs http://127.0.0.1:8080
```

## Score contract

Batting residual = bat runs minus earlier-year contextual expectation. Bowling residual = expected charged runs minus observed charged runs. Score = `100 * residual_sum / (pressure_events + 60)`. This is fixed-prior pseudo-exposure shrinkage, not an empirically fitted hierarchical posterior. Tie rules: pressure matches descending, player ID ascending. Minimum: 30 pressure events / five matches. Role support: 60 events / five matches.

Uncertainty resamples independent match clusters, 400 seeded replicates. Usual means **nonpressure** contextual contribution; all-situation overall stays separately labelled. The six dimensions are never summed. Role filters retain frozen ranks. Formal pairwise comparisons use equal weights across shared innings/phase/IPL strata, match-cluster intervals and excluded non-overlap counts. No causal replacement wins are estimated.

First-innings viability uses an earlier complete-innings median, not a validated venue-adjusted par. First/chase figures remain separate. Contextual wicket value, learned venue/opponent effects and prospective validation are not established. See the full methodology for remaining limitations.

## Verification and deployment

Tests cover pre-delivery state, terminal transitions, stress caps, episodes, wide/bye/run-out attribution, nested ZIP traversal, chronology, score/order, publication safety and PDF/list agreement. TypeScript strict and unused-local/parameter checks plus production build pass. Installed frontend dependency audit reports zero known vulnerabilities after patching Vite.

Production HTTP index, JSON, PDF, HEAD/POST behavior and denial of private paths were checked. PDF pages were rendered and inspected; version and list order match JSON.

**Unverified:** desktop/mobile interactive browser QA. In-app loopback failed; Windows computer-use stopped because it could not confidently determine the current URL. No successful UI check is claimed. **Container execution is unverified:** Docker engine is stopped. The user chose manual Cloud Run deployment; no live URL is claimed. See [manual deployment](docs/deployment.md).

The bundled brief requires two top-ten dropdown lists and methodology upload. Public Unstop listing was checked; numeric judging rubric and account dropdown IDs were unavailable. No submission was sent. This is reviewable research with real findings, not a final validated auction strategy.
