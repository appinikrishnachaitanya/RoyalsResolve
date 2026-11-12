import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Analysis, Comparison, Player } from './types';
import './style.css';
import { ComparisonEvidence, RRCase, ScoreBar, Supporting } from './Evidence';
import { Backtest, IncumbentComparison, RawComparison, TopPicks } from './DecisionPanels';

const fmt = (value: number, digits = 1) => value.toLocaleString('en-IN', { maximumFractionDigits: digits });
const signed = (value: number) => `${value > 0 ? '+' : ''}${fmt(value)}`;

function Drawer({ p, close, bowling }: { p: Player; close: () => void; bowling: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  return <dialog ref={ref} onCancel={close} aria-labelledby="player-title">
    <button className="close" onClick={close} aria-label="Close player details">x</button>
    <small>RANK {p.rank} / PLAYER EVIDENCE</small><h2 id="player-title">{p.name}</h2>
    <p>{p.roles.join(' / ') || 'Role evidence is insufficient'}</p>
    <div className="metric-grid"><div><strong>{signed(p.score)}</strong>{bowling ? 'runs saved vs expected / 100 pressure deliveries' : 'runs above expected / 100 pressure deliveries'}</div><div><strong>{p.matches}</strong>independent matches</div><div><strong>{p.episodes}</strong>pressure episodes</div></div>
    <h3>How this score is calculated</h3>
    <p>{fmt(p.balls, 0)} eligible deliveries. {bowling ? `Expected bowler-charged runs ${fmt(p.expected_runs, 2)} minus observed charged runs ${fmt(p.runs, 0)}` : `Observed batter runs ${fmt(p.runs, 0)} minus expected batter runs ${fmt(p.expected_runs, 2)}`} = <b>{signed(p.residual_sum)} runs relative to expectation</b>. Then 100 x residual / ({p.balls} deliveries + 60 sample-stabilising deliveries) = <b>{signed(p.score)}</b> {bowling ? 'runs saved vs expected' : 'runs above expected'} per 100 pressure deliveries.</p>
    <p>95% match-bootstrap interval: [{p.interval.map((x) => fmt(x)).join(', ')}]. Non-pressure baseline: {signed(p.usual)} {bowling ? 'runs saved vs expected' : 'runs above expected'} per 100. The unpooled pressure-minus-usual difference is {signed(p.difference)}; it is not the ranked score minus usual.</p>
    <h3>Role and phase evidence</h3><div className="table-wrap"><table><thead><tr><th>Phase</th><th>Events / matches</th><th>Runs / 100</th></tr></thead><tbody>{p.phases.map((x) => <tr key={x.role}><td>{x.role}</td><td>{x.balls} / {x.matches}</td><td>{signed(x.contribution)}</td></tr>)}</tbody></table></div>
    <p>First innings: {p.first_innings_balls} events, {p.first_innings_score === null ? 'not available' : `${signed(p.first_innings_score)} ${bowling ? 'runs saved' : 'runs above expectation'} per 100`}. Chase: {p.chase_balls} events, {p.chase_score === null ? 'not available' : `${signed(p.chase_score)} ${bowling ? 'runs saved' : 'runs above expectation'} per 100`}.</p>
    <RRCase p={p} /><Supporting p={p} />
    <h3>Additional observed statistics</h3><p>{p.balls} pressure events; {p.legal_balls} legal balls ({p.overs} overs). {bowling ? 'Economy (charged runs per 6 legal balls)' : 'Strike rate (batter runs per 100 non-wide events)'}: {fmt(p.rate)}. {bowling ? 'Wickets credited to bowler' : 'Striker dismissals'}: {p.dismissals}. Expected striker dismissals: {fmt(p.expected_dismissals)}. Dot rate: {fmt(p.dot_rate)}%. Boundary rate: {fmt(p.boundary_rate)}%. Extras: {p.extras} runs.</p>
    <h3>Limitations for this player</h3><p>{p.objection}</p><h3>Season breakdown</h3>{p.seasons.map((s) => <p key={s.year}>{s.year}: {s.balls} events, {signed(s.score)} unpooled runs per 100.</p>)}
    <p className="notice">Statistical ranking only. Auction availability, 2027 registration, price and eligibility have not been verified. IPL pressure sample: {p.ipl_balls} deliveries.</p>
  </dialog>;
}

function CandidateComparison({ pool, comparisons, bowling, rankLimit, onRankLimit }: { pool: Player[]; comparisons: Comparison[]; bowling: boolean; rankLimit: number; onRankLimit: (limit: number) => void }) {
  const candidates = rankLimit === 0 ? pool : pool.slice(0, rankLimit);
  const [period, setPeriod] = useState('All seasons');
  const [aId, setAId] = useState(candidates[0]?.id);
  const [bId, setBId] = useState(candidates[1]?.id);
  useEffect(() => {
    if (!candidates.some((p) => p.id === aId)) setAId(candidates[0]?.id);
    if (!candidates.some((p) => p.id === bId)) setBId(candidates[1]?.id);
  }, [rankLimit, pool]);
  const a = candidates.find((p) => p.id === aId);
  const b = candidates.find((p) => p.id === bId);
  if (!a || !b) return <section className="panel"><h2>Player scorecard</h2><p>Two eligible players are needed.</p></section>;
  const scoreFor = (p: Player) => period === 'All seasons' ? p.score : p.seasons.find((s) => String(s.year) === period)?.score ?? null;
  const scoreA = scoreFor(a); const scoreB = scoreFor(b);
  const comparison = period === 'All seasons' ? comparisons.find((c) => ((c.a === aId && c.b === bId) || (c.a === bId && c.b === aId)) && c.phase === 'Shared assignments') : undefined;
  const reverse = comparison ? comparison.a !== aId : false;
  const interval = comparison ? (reverse ? [-comparison.interval[1], -comparison.interval[0]] : comparison.interval) : null;
  const difference = comparison ? comparison.difference * (reverse ? -1 : 1) : null;
  const maxScore = Math.max(1, Math.abs(scoreA || 0), Math.abs(scoreB || 0));
  const metricsFor = (p: Player) => period === 'All seasons' ? p : p.seasons.find((s) => String(s.year) === period) || null;
  const aM = metricsFor(a); const bM = metricsFor(b);
  const show = (value: number | null | undefined, render: (n: number) => string = fmt) => value === null || value === undefined ? 'No data' : render(value);
  const runPair = (m: NonNullable<typeof aM>) => `${fmt(m.runs, 0)} / ${fmt(m.expected_runs)}`;
  const metricRows: string[][] = [
    ['Pressure score', scoreA === null ? 'No pressure data' : `${signed(scoreA)} runs / 100${period === 'All seasons' ? `; range ${signed(a.interval[0])} to ${signed(a.interval[1])}` : '; season range unavailable'}`, scoreB === null ? 'No pressure data' : `${signed(scoreB)} runs / 100${period === 'All seasons' ? `; range ${signed(b.interval[0])} to ${signed(b.interval[1])}` : '; season range unavailable'}`, 'Runs above expectation (batting) or saved (bowling)'],
    ['Sample', aM ? `${aM.matches} matches; ${aM.episodes} spells; ${aM.balls} deliveries` : 'No pressure sample', bM ? `${bM.matches} matches; ${bM.episodes} spells; ${bM.balls} deliveries` : 'No pressure sample', 'Independent matches and eligible pressure deliveries'],
    ['Observed role evidence', a.roles.join(', ') || 'Not enough evidence', b.roles.join(', ') || 'Not enough evidence', bowling ? 'Observed bowling phases; phase tags can overlap' : 'Batting-position and phase evidence across the full dataset'],
    ['Runs / model expected', aM ? runPair(aM) : 'No data', bM ? runPair(bM) : 'No data', bowling ? 'Charged runs conceded / expected charged runs' : 'Batter runs scored / model-expected batter runs'],
    ['Usual play outside pressure', aM ? `${show(aM.usual, signed)} / 100; ${aM.nonpressure_balls} deliveries` : 'No data', bM ? `${show(bM.usual, signed)} / 100; ${bM.nonpressure_balls} deliveries` : 'No data', 'Contextual run contribution on non-pressure deliveries'],
    ['Pressure change vs usual', aM ? show(aM.difference, (n) => `${signed(n)} / 100`) : 'No data', bM ? show(bM.difference, (n) => `${signed(n)} / 100`) : 'No data', 'Unpooled pressure score minus usual-play score'],
    [bowling ? 'Economy' : 'Strike rate', aM ? fmt(aM.rate) : 'No data', bM ? fmt(bM.rate) : 'No data', bowling ? 'Charged runs per 6 legal balls; lower is better' : 'Batter runs per 100 non-wide deliveries; higher is better'],
    ['Legal balls / overs', aM ? `${aM.legal_balls} / ${aM.overs}` : 'No data', bM ? `${bM.legal_balls} / ${bM.overs}` : 'No data', 'Legal deliveries faced (batting) or bowled (bowling)'],
    [bowling ? 'Wickets credited' : 'Striker dismissals', aM ? String(aM.dismissals) : 'No data', bM ? String(bM.dismissals) : 'No data', 'Observed dismissals; not converted into runs in this score'],
    ...(!bowling ? [['Expected striker dismissals', aM ? fmt(aM.expected_dismissals, 2) : 'No data', bM ? fmt(bM.expected_dismissals, 2) : 'No data', 'Model estimate shown separately; not included in score']] : []),
    ['Dot deliveries', aM ? `${fmt(aM.dot_rate)}%` : 'No data', bM ? `${fmt(bM.dot_rate)}%` : 'No data', 'Share of pressure deliveries with no batter runs'],
    ['Boundary deliveries', aM ? `${fmt(aM.boundary_rate)}%` : 'No data', bM ? `${fmt(bM.boundary_rate)}%` : 'No data', 'Share of pressure deliveries that were fours or sixes'],
    ['Extras', aM ? fmt(aM.extras, 0) : 'No data', bM ? fmt(bM.extras, 0) : 'No data', 'Extras recorded on these deliveries; not batter runs'],
    ['First innings / chase score', aM ? `${aM.first_innings_score === null ? '—' : signed(aM.first_innings_score)} / ${aM.chase_score === null ? '—' : signed(aM.chase_score)}` : 'No data', bM ? `${bM.first_innings_score === null ? '—' : signed(bM.first_innings_score)} / ${bM.chase_score === null ? '—' : signed(bM.chase_score)}` : 'No data', 'Run contribution per 100 in each innings setting'],
  ];
  const directVerdict = period !== 'All seasons' ? 'Direct matched comparison is published for all seasons only.' : interval ? interval[0] > 0 ? `Similar situations favor ${a.name}.` : interval[1] < 0 ? `Similar situations favor ${b.name}.` : 'No clear winner in similar situations.' : 'No direct matched comparison is published for this pair.';
  return <section className="panel"><div className="section-top"><div><small>PLAYER COMPARISON</small><h2>Side-by-side scorecard</h2></div><p>Choose any two ranked players. All figures come from the saved match analysis.</p></div>
    <div className="filters rank-size-filter" role="group" aria-label="Number of ranked players to compare">{[{ label: 'Top 10', value: 10 }, { label: 'Top 20', value: 20 }, { label: 'All eligible', value: 0 }].map((item) => <button key={item.label} className={rankLimit === item.value ? 'active' : ''} onClick={() => onRankLimit(item.value)}>{item.label}</button>)}</div>
    <div className="controls comparison-controls"><label>Player A<select value={aId} onChange={(e) => setAId(Number(e.target.value))}>{candidates.map((p) => <option key={p.id} value={p.id}>{p.rank}. {p.name}</option>)}</select></label><label>Player B<select value={bId} onChange={(e) => setBId(Number(e.target.value))}>{candidates.map((p) => <option key={p.id} value={p.id}>{p.rank}. {p.name}</option>)}</select></label><label>Season<select value={period} onChange={(e) => setPeriod(e.target.value)}><option>All seasons</option>{[...new Set([...a.seasons, ...b.seasons].map((s) => s.year))].sort((x, y) => x - y).map((year) => <option key={year}>{year}</option>)}</select></label></div>
    {aId === bId ? <p className="notice">Choose two different players.</p> : <>
      <div className="side-score-bars">{[{ label: 'A', player: a, value: scoreA, color: 'head-a' }, { label: 'B', player: b, value: scoreB, color: 'head-b' }].map(({ label, player, value, color }) => <div className="side-score-row" key={label}><div><small>PLAYER {label}</small><b>{player.name}</b></div>{value === null ? <span className="no-season-data">No eligible pressure data in {period}</span> : <ScoreBar value={value} scale={maxScore} label={`${player.name}: ${signed(value)} per 100`} tone={color} />}<strong>{value === null ? '—' : signed(value)}</strong></div>)}</div>
      <div className="bar-axis"><span>{bowling ? 'More conceded' : 'Below expected'}</span><b>0</b><span>{bowling ? 'More saved' : 'Above expected'}</span></div>
      <p className="chart-subtitle">Both scores use the same scale. The scorecard covers the selected season; role evidence uses the full dataset.</p>
      <div className="table-wrap scorecard-table"><table><thead><tr><th>Measure</th><th>{a.name}</th><th>{b.name}</th><th>What it means</th></tr></thead><tbody>{metricRows.map(([label, av, bv, meaning]) => <tr key={label}><th>{label}</th><td>{av}</td><td>{bv}</td><td>{meaning}</td></tr>)}</tbody></table></div>
      {period === 'All seasons' ? <div className={`match-result ${comparison ? 'supported' : 'unsupported'}`}><b>{directVerdict}</b>{comparison && interval && difference !== null && <p>A minus B: {signed(difference)} runs per 100 similar deliveries; likely range {fmt(interval[0])} to {fmt(interval[1])}.</p>}</div> : <p className="caption">Season scores use the same 60-delivery adjustment. Year-specific uncertainty ranges and matched comparisons are unavailable.</p>}
      {comparison && <details className="formula-details"><summary>Show how much data backs this direct comparison</summary><div className="formula-content"><ComparisonEvidence comparison={comparison} reverse={reverse} /></div></details>}
      {period === 'All seasons' && !comparison && <p className="caption">The bars and scorecard compare the two players' own results. They do not prove one would replace the other.</p>}
    </>}
    <details className="formula-details"><summary>How pressure and the score are calculated</summary><div className="formula-content"><p><b>Pressure situations:</b> a chase with 60 or fewer balls left and at least 8 runs needed per over; or a first innings with 30 or fewer balls left and at least 3 wickets lost.</p><p><b>Delivery result:</b> batter runs minus expected runs. For bowlers, expected runs conceded minus actual runs conceded. Expected runs are estimated from earlier seasons with similar match situations.</p><p><b>Score per 100:</b> 100 x total delivery results / (pressure deliveries + 60). The extra 60 keeps small samples from dominating. At least 30 pressure deliveries across 5 matches are required. This is not a win probability.</p></div></details>
  </section>;
}

function Methodology({ d }: { d: Analysis }) {
  const strictRuleUsed = d.margin_eligible_counts.batting >= 10 && d.margin_eligible_counts.bowling >= 10;
  return <div className="methodology-page">
    <section className="panel methodology-intro"><small>PRESSURE CALCULATION</small><h2>How the scores are made</h2><p>See which deliveries count as pressure, how we estimate expected runs, and how each player's score is calculated.</p><a className="download" href="./results/methodology.pdf" download>Download the calculation report</a><div className="method-steps"><article><b>01 / Check</b><p>Keep complete matches with deliveries that can be compared fairly.</p></article><article><b>02 / Set the scene</b><p>Record score, wickets, balls left and whether the team is chasing.</p></article><article><b>03 / Estimate runs</b><p>Compare each player's runs with what earlier matches predict.</p></article><article><b>04 / Rank</b><p>Adjust small samples toward zero, then order highest score first.</p></article></div></section>
    <section className="panel"><h3>Dataset and audit</h3><p>The supplied data covers {fmt(d.audit.deliveries, 0)} deliveries across {fmt(d.audit.matches, 0)} matches and {fmt(d.audit.competitions, 0)} competitions, dated {d.audit.date_range[0]} to {d.audit.date_range[1]}.</p><div className="stat-callouts"><div><b>{fmt(d.audit.retained_deliveries, 0)}</b><span>deliveries retained / {d.audit.retained_matches} matches</span></div><div><b>{fmt(d.audit.excluded_deliveries, 0)}</b><span>deliveries excluded / {d.audit.excluded_matches} matches</span></div><div><b>{fmt(d.audit.oos_deliveries, 0)}</b><span>out-of-time deliveries / {d.audit.oos_matches} matches</span></div><div><b>{fmt(d.audit.warmup_deliveries, 0)}</b><span>warm-up deliveries</span></div></div><p className="caption">Exclusion reasons can overlap, so their match counts should not be added together.</p><div className="table-wrap"><table><thead><tr><th>Exclusion reason</th><th>Matches affected</th></tr></thead><tbody>{Object.entries(d.audit.exclusion_reasons_overlapping).map(([reason, count]) => <tr key={reason}><td>{reason}</td><td>{count}</td></tr>)}</tbody></table></div></section>
    <section className="panel"><h3>Pressure definition and coverage fallback</h3><p>The strict margin definition needs at least ten eligible players in each role. It identifies {d.margin_eligible_counts.batting} batter(s) and {d.margin_eligible_counts.bowling} bowlers in this dataset{strictRuleUsed ? ', so it is used for the published ranking.' : ', so it cannot support both top-ten lists. The displayed ranking uses the declared phase and required-rate fallback instead.'}</p><div className="formula-grid"><article><b>Chase fallback</b><p>60 or fewer legal balls remain, and the required run rate is at least 8 runs per over.</p></article><article><b>First-innings fallback</b><p>30 or fewer legal balls remain, and at least 3 wickets have been lost.</p></article><article><b>Minimum player sample</b><p>At least 30 pressure deliveries across 5 independent matches. A role label needs at least 60 events across 5 matches.</p></article></div><p>The proposed strict hypothesis defines mistake tolerance as the largest number of consecutive legal dot balls (batting) or boundary-conceding deliveries (bowling) that can be absorbed before task viability falls below 0.20. A tight margin requires viability between 0.20 and 0.80 and tolerance of at most one event. The data coverage above is why this rule is not used for the current ranking.</p></section>
    <section className="panel"><h3>Expected runs and player score</h3><p>A contextual Ridge model estimates runs for each eligible delivery using the pre-delivery innings state: score, wickets lost, legal balls remaining, required rate where relevant, innings, phase and competition indicator. For the first innings, the target reference is the median of earlier complete retained first innings. Each evaluation year is predicted from earlier years only.</p><div className="formula-grid"><article><b>Batting residual</b><p>Observed batter runs minus expected batter runs.</p></article><article><b>Bowling residual</b><p>Expected bowler-charged runs minus observed bowler-charged runs.</p></article><article><b>Shrunk player score</b><p>100 x sum of residuals / (pressure deliveries + 60).</p></article></div><p>The score is run-only. Wickets are shown separately because no validated run value is assigned to them here. Batting and bowling scores are not interchangeable. Ranks sort from highest score to lowest, then by pressure-match count, then player ID for ties.</p></section>
    <section className="panel"><h3>Chronological validation</h3><p>Each season is evaluated out of time using only earlier matches for training. Brier score is average squared probability error; log loss penalises confident mistakes. Lower is better for both. These scores describe the side-task outcome model; they do not measure psychological pressure. Deliveries within one match are not independent.</p><div className="table-wrap"><table><thead><tr><th>Test year</th><th>Train matches</th><th>Test matches</th><th>Model</th><th>Brier</th><th>Log loss</th></tr></thead><tbody>{d.validation.flatMap((v) => Object.entries(v.models).map(([name, stats]) => <tr key={`${v.year}-${name}`}><td>{v.year}{v.year === 2026 ? ' (later holdout)' : ''}</td><td>{v.train_matches}</td><td>{v.test_matches}</td><td>{name.replaceAll('_', ' ')}</td><td>{fmt(stats.brier, 3)}</td><td>{fmt(stats.log_loss, 3)}</td></tr>))}</tbody></table></div><p>Later-player selection outcomes are shown below as a retrospective check. The 2026 results were available during this analysis and are not a prospectively sealed trial.</p><Backtest d={d} /></section>
    <details className="panel secondary-details"><summary>Audit tables and remaining limitations</summary><div className="details-content"><h3>Validated input tables</h3><div className="table-wrap"><table><thead><tr><th>Table</th><th>Rows</th><th>Fields</th></tr></thead><tbody>{Object.entries(d.audit.schema).map(([name, schema]) => <tr key={name}><th>{name}</th><td>{fmt(schema.rows, 0)}</td><td>{schema.columns.length}</td></tr>)}</tbody></table></div><h3>Analysis limitations</h3><ul>{d.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div></details>
  </div>;
}

function Roster({ d }: { d: Analysis }) {
  return <section className="panel"><small>VERIFIED SQUAD COVERAGE</small><h2>What the official 2026 source supports</h2><p>{d.roster.decision_memo}</p><p>Source cutoff: {d.roster.cutoff}. This page verifies 2026 squad coverage only. It does not establish 2027 retention, registration, auction status or availability.</p><details className="secondary-details"><summary>View player-by-player coverage</summary><div className="details-content table-wrap"><table><thead><tr><th>Official 2026 squad member</th><th>Batting phase evidence</th><th>Bowling phase evidence</th></tr></thead><tbody>{d.coverage.map((player) => <tr key={player.name}><th>{player.name}</th>{(['batting', 'bowling'] as const).map((role) => <td key={role}>{player[role].length ? player[role].map((x) => <div key={x.phase}>{x.phase}: {signed(x.score)} runs / 100; {x.balls} events / {x.matches} matches</div>) : 'Not assessed'}</td>)}</tr>)}</tbody></table></div></details>{d.roster.sources.map((source) => <p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.publisher} (source)</a>; accessed {source.accessed}. {source.claim}</p>)}</section>;
}

function App() {
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('BATTERS');
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('Overall');
  const [rankLimit, setRankLimit] = useState(10);
  const [selected, setSelected] = useState<{ player: Player; bowling: boolean } | null>(null);
  useEffect(() => { fetch('./results/analysis.json').then((response) => { if (!response.ok) throw new Error('Saved analysis could not be loaded. Run the export pipeline.'); return response.json(); }).then(setData).catch((e) => setError(String(e))); }, []);
  if (error) return <main><h1>Analysis unavailable</h1><p role="alert">{error}</p></main>;
  if (!data) return <main aria-busy="true"><h1>Loading the analysis...</h1></main>;

  const bowling = tab === 'BOWLERS';
  const pool = bowling ? (data.bowlers_all || data.bowlers) : (data.batters_all || data.batters);
  const rankedPlayers = rankLimit === 0 ? pool : pool.slice(0, rankLimit);
  const roles = bowling ? ['Powerplay', 'Middle overs', 'Death'] : ['Opener', 'Middle order', 'Death overs'];
  const filtered = rankedPlayers.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) && (role === 'Overall' || p.roles.includes(role)));
  const chartPlayers = filtered;
  const plot = { left: 92, right: 966, top: 28, bottom: 410, width: 1000, height: 480 };
  const chartExtent = Math.max(5, ...chartPlayers.flatMap((p) => [Math.abs(p.interval[0]), Math.abs(p.interval[1]), Math.abs(p.score)]));
  const maxBalls = Math.max(50, ...chartPlayers.map((p) => p.balls));
  const xMax = Math.ceil(maxBalls / 50) * 50;
  const xPos = (balls: number) => plot.left + (balls / xMax) * (plot.right - plot.left);
  const yPos = (score: number) => plot.bottom - ((score + chartExtent) / (chartExtent * 2)) * (plot.bottom - plot.top);
  const yTicks = Array.from({ length: 5 }, (_, i) => -chartExtent + (chartExtent * 2 * i) / 4);
  const xTicks = Array.from({ length: 5 }, (_, i) => (xMax * i) / 4);
  const pick = (p: Player, isBowling: boolean) => { setTab(isBowling ? 'BOWLERS' : 'BATTERS'); setRole('Overall'); setSearch(''); setSelected({ player: p, bowling: isBowling }); };

  return <><header><a className="brand" href="#home">RR<span> / RESOLVE</span></a><span>INDEPENDENT CRICKET ANALYSIS</span><a href="./results/methodology.pdf">Pressure calculation</a></header><main id="home">
    <TopPicks d={data} open={pick} />
    <nav aria-label="Analysis sections">{['BATTERS', 'BOWLERS', 'PRESSURE CALCULATION'].map((item) => <button key={item} aria-current={tab === item ? 'page' : undefined} onClick={() => { setTab(item); setRole('Overall'); setSearch(''); }}>{item}</button>)}</nav>
    {tab === 'PRESSURE CALCULATION' ? <Methodology d={data} /> : <>
      <section className="panel"><div className="section-top"><div><small>{bowling ? 'BOWLING CONTRIBUTION' : 'BATTING CONTRIBUTION'}</small><h2>{rankLimit === 0 ? `All eligible ${bowling ? 'bowlers' : 'batters'}` : `Top ${rankLimit} ${bowling ? 'bowlers' : 'batters'}`}</h2></div><p>Rank 1 has the highest score.<br />Every player shown meets the minimum sample.</p></div>
        <div className="filters rank-size-filter" role="group" aria-label="Number of players shown">{[{ label: 'Top 10', value: 10 }, { label: 'Top 20', value: 20 }, { label: `All ${pool.length}`, value: 0 }].map((item) => <button key={item.label} className={rankLimit === item.value ? 'active' : ''} onClick={() => setRankLimit(item.value)}>{item.label}</button>)}</div>
        <div className="filters"><div role="group" aria-label="Role evidence filter">{['Overall', ...roles].map((item) => <button className={role === item ? 'active' : ''} key={item} onClick={() => setRole(item)}>{item}</button>)}</div><label><span className="sr-only">Search players</span><input placeholder="Search these ranked players" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div>
        <p className="caption">Scores are sorted high to low; ranges show uncertainty. Batting tags describe batting roles/phases and do not mean all-rounder status.</p>
        <div className="ranking-side-by-side"><div className="table-wrap ranking-table"><table><thead><tr><th>Rank / player / role</th><th>Score / 100</th><th>Matches / sample</th><th>95% range</th></tr></thead><tbody>{filtered.map((p) => <tr key={p.id}><th><span className="rank-inline">{String(p.rank).padStart(2, '0')}</span><button className="player" onClick={() => setSelected({ player: p, bowling })}>{p.name}</button><span className="role">{p.roles.join(' / ') || 'Role not established'}</span></th><td className="contribution">{signed(p.score)}<span className="role">per 100</span></td><td>{p.matches}<span className="role">matches</span><span className="role">{p.balls} deliveries / {p.episodes} spells</span></td><td className="interval">[{p.interval.map((x) => signed(x)).join(', ')}]<span className="role">{p.interval[0] <= 0 && p.interval[1] >= 0 ? 'Crosses zero' : '95% estimate'}</span></td></tr>)}</tbody></table>{!filtered.length && <p className="empty">No ranked players match this filter.</p>}</div>
        {chartPlayers.length > 0 && <section className="ranking-visual" aria-label="Pressure score and sample size chart"><div className="ranking-visual-head"><div><small>{bowling ? 'BOWLING' : 'BATTING'} / {rankLimit === 0 ? 'ALL ELIGIBLE' : `TOP ${rankLimit}`}</small><h3>Score vs pressure deliveries</h3></div><span>Dot = player · line = 95% range · dashed = zero baseline</span></div><div className="rank-chart-scroll"><svg className="rank-scatter" viewBox={`0 0 ${plot.width} ${plot.height}`} role="img" aria-label={`Two-dimensional plot of ${bowling ? 'runs saved' : 'runs above expected'} per 100 pressure deliveries against sample size`}>
          {yTicks.map((tick) => <g key={`y-${tick}`}><line x1={plot.left} x2={plot.right} y1={yPos(tick)} y2={yPos(tick)} className={Math.abs(tick) < 0.001 ? 'scatter-baseline' : 'scatter-grid'} /><text x={plot.left - 12} y={yPos(tick) + 4} textAnchor="end" className="scatter-label">{tick.toFixed(0)}</text></g>)}
          {xTicks.map((tick) => <g key={`x-${tick}`}><line x1={xPos(tick)} x2={xPos(tick)} y1={plot.top} y2={plot.bottom} className="scatter-grid" /><text x={xPos(tick)} y={plot.bottom + 22} textAnchor="middle" className="scatter-label">{Math.round(tick)}</text></g>)}
          {chartPlayers.map((p) => { const x = xPos(p.balls); const y = yPos(p.score); const top = yPos(Math.min(chartExtent, p.interval[1])); const bottom = yPos(Math.max(-chartExtent, p.interval[0])); return <g key={p.id} className="scatter-player" onClick={() => setSelected({ player: p, bowling })} role="button" tabIndex={0} aria-label={`Rank ${p.rank}: ${p.name}, ${p.balls} pressure deliveries, score ${signed(p.score)}, 95% range ${signed(p.interval[0])} to ${signed(p.interval[1])}`} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelected({ player: p, bowling }); }}><title>{`${p.rank}. ${p.name} · ${p.roles.join(', ') || 'role not established'} · ${p.balls} deliveries in ${p.matches} matches · score ${signed(p.score)} · 95% range ${signed(p.interval[0])} to ${signed(p.interval[1])}`}</title><line x1={x} x2={x} y1={top} y2={bottom} className="scatter-interval" /><line x1={x - 5} x2={x + 5} y1={top} y2={top} className="scatter-cap" /><line x1={x - 5} x2={x + 5} y1={bottom} y2={bottom} className="scatter-cap" /><circle cx={x} cy={y} r={p.rank <= 10 ? 5.5 : 4} className={`scatter-point ${p.score < 0 ? 'scatter-negative' : ''}`} />{p.rank <= 10 && <text x={x + 8} y={y - 7} className="scatter-rank">{p.rank}</text>}</g>; })}
          <text x={(plot.left + plot.right) / 2} y={plot.height - 8} textAnchor="middle" className="scatter-axis-title">Pressure deliveries (sample size)</text><text transform={`translate(18 ${(plot.top + plot.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="scatter-axis-title">{bowling ? 'Runs saved per 100' : 'Runs above expected per 100'}</text>
        </svg></div><p className="chart-subtitle">Further right means a larger sample. Higher means a better run contribution for this role. A range crossing the dashed zero line means the estimate is uncertain. Select a dot for player details.</p></section>}</div>
        <p className="caption">Dismissals and wickets are separate from this run-only score. Non-striker run-outs are not assigned to striker exposure.</p>
      </section>
      <RawComparison stars={bowling ? data.bowlers_raw_stars : data.batters_raw_stars} />
      <CandidateComparison key={`candidate-${tab}`} pool={pool} rankLimit={rankLimit} onRankLimit={setRankLimit} comparisons={bowling ? data.bowlers_comparisons : data.batters_comparisons} bowling={bowling} />
      <IncumbentComparison key={`incumbent-${tab}`} d={data} players={bowling ? data.bowlers : data.batters} bowling={bowling} />
      <details className="panel secondary-details"><summary>Other saved scenario checks</summary><div className="details-content"><p>These saved scenarios test different sample windows and pressure cutoffs.</p><CandidateStressTest players={pool.slice(0, 10)} comparisons={bowling ? data.bowlers_comparisons : data.batters_comparisons} /></div></details>
      <Roster d={data} />
    </>}
    {selected && <Drawer p={selected.player} bowling={selected.bowling} close={() => setSelected(null)} />}
    <footer><b>Royals' Resolve</b><p>Independent research. Not an official Rajasthan Royals product.</p><code>Version {data.version} | Analysis {data.analysis_id}</code><p>Generated {new Date(data.generated).toISOString().slice(0, 10)}. Raw input files remain local.</p></footer>
  </main></>;
}

function CandidateStressTest({ players, comparisons }: { players: Player[]; comparisons: Comparison[] }) {
  const [aId, setAId] = useState(players[0]?.id);
  const [bId, setBId] = useState(players[1]?.id);
  const [scenario, setScenario] = useState('Published');
  const [phase, setPhase] = useState('Shared phases');
  const a = players.find((p) => p.id === aId);
  const b = players.find((p) => p.id === bId);
  if (!a || !b) return <p>Insufficient eligible players for a robustness comparison.</p>;
  const scenarioScore = (p: Player) => { if (scenario === 'Published') return p.score; const value = p.scenarios?.[scenario]; return typeof value === 'number' ? value : value?.score; };
  const scoreA = scenarioScore(a); const scoreB = scenarioScore(b);
  const formal = comparisons.find((c) => ((c.a === aId && c.b === bId) || (c.a === bId && c.b === aId)) && c.phase === (phase === 'Shared phases' ? 'Shared assignments' : phase));
  return <section className="stress"><div className="section-top"><div><small>ROBUSTNESS CHECK</small><h2>Does the ordering change?</h2></div><p>Saved analysis scenarios only. No browser refitting.</p></div>
    <div className="controls"><label>Player A<select value={aId} onChange={(e) => setAId(Number(e.target.value))}>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Player B<select value={bId} onChange={(e) => setBId(Number(e.target.value))}>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Saved scenario<select value={scenario} onChange={(e) => setScenario(e.target.value)}>{['Published', 'Leave best match out', 'IPL only', 'Recent 2026', 'Tau 0.15', 'Tau 0.25'].map((x) => <option key={x}>{x}</option>)}</select></label><label>Assignment<select value={phase} onChange={(e) => setPhase(e.target.value)}>{['Shared phases', 'Powerplay', 'Middle overs', 'Death'].map((x) => <option key={x}>{x}</option>)}</select></label></div>
    <div className="comparison"><article><small>A / {a.matches} MATCHES</small><h3>{a.name}</h3><strong>{scoreA === undefined ? 'Unavailable' : signed(scoreA)}</strong><p>runs / 100 pressure deliveries</p><p>{a.roles.join(', ') || 'Role evidence not established'} / {a.balls} pressure events.</p></article><article><small>B / {b.matches} MATCHES</small><h3>{b.name}</h3><strong>{scoreB === undefined ? 'Unavailable' : signed(scoreB)}</strong><p>runs / 100 pressure deliveries</p><p>{b.roles.join(', ') || 'Role evidence not established'} / {b.balls} pressure events.</p></article></div>
    <p className="notice">{aId === bId ? 'Choose distinct players.' : scoreA === undefined || scoreB === undefined ? 'A saved estimate is unavailable for this scenario.' : scenario === 'Published' ? 'These overall estimates may reflect different assignments and do not establish a head-to-head advantage.' : `In this fixed-fit check, the published ordering ${((scoreA > scoreB) === (a.score > b.score)) ? 'persists' : 'reverses'}. This does not adjust for uncertainty.`}</p>
    <h3>Matched assignment evidence</h3>{formal ? <ComparisonEvidence comparison={formal} reverse={formal.a !== aId} /> : <p>Insufficient shared-assignment support for a formal comparison.</p>}
  </section>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
