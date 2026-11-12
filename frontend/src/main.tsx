import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Analysis, Comparison, Player } from './types';
import './style.css';
import { ComparisonEvidence, RRCase, Supporting, UsualChart } from './Evidence';
import { Backtest, IncumbentComparison, RawComparison, TopPicks } from './DecisionPanels';

const fmt = (value: number, digits = 1) => value.toLocaleString('en-IN', { maximumFractionDigits: digits });
const signed = (value: number) => `${value > 0 ? '+' : ''}${fmt(value)}`;

function IntervalChart({ players, bowling }: { players: Player[]; bowling: boolean }) {
  const width = 700;
  const labelWidth = 190;
  const chartWidth = width - labelWidth - 24;
  const low = Math.min(-20, ...players.map((p) => p.interval[0]));
  const high = Math.max(20, ...players.map((p) => p.interval[1]));
  const x = (value: number) => labelWidth + ((value - low) / (high - low)) * chartWidth;
  const height = Math.max(100, players.length * 38 + 46);

  return (
    <figure className="chart-card">
      <figcaption>{bowling ? 'Runs saved vs expected' : 'Runs above expected'}</figcaption>
      <p className="chart-subtitle">Per 100 pressure deliveries. Bars show 95% match-bootstrap intervals.</p>
      {players.length ? <div className="chart-scroll"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Player pressure contribution estimates and 95 percent intervals">
        <line x1={x(0)} x2={x(0)} y1="8" y2={height - 34} className="zero-line" />
        {players.map((p, i) => {
          const y = i * 38 + 20;
          return <g key={p.id}>
            <text x="4" y={y + 4} className="chart-label">{String(p.rank).padStart(2, '0')}  {p.name}</text>
            <line x1={x(p.interval[0])} x2={x(p.interval[1])} y1={y} y2={y} className="interval-line" />
            <circle cx={x(p.score)} cy={y} r="5" className="estimate-dot" />
            <title>{p.name}: {signed(p.score)} {bowling ? 'runs saved vs expected' : 'runs above expected'} per 100 pressure deliveries; 95% interval {p.interval.map((v) => fmt(v)).join(' to ')}; {p.matches} matches and {p.balls} events.</title>
          </g>;
        })}
        {[low, 0, high].map((v) => <text key={v} x={x(v)} y={height - 10} textAnchor="middle" className="axis-label">{fmt(v)}</text>)}
      </svg></div> : <p className="empty">Choose another role or clear the search to see players.</p>}
    </figure>
  );
}

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

function CandidateComparison({ players, comparisons, bowling }: { players: Player[]; comparisons: Comparison[]; bowling: boolean }) {
  const [aId, setAId] = useState(players[0]?.id);
  const [bId, setBId] = useState(players[1]?.id);
  const [phase, setPhase] = useState('Shared assignments');
  const a = players.find((p) => p.id === aId);
  const b = players.find((p) => p.id === bId);
  if (!a || !b) return <section className="panel"><h2>Candidate comparison</h2><p>At least two eligible players are needed for a comparison.</p></section>;
  const compare = comparisons.find((c) => ((c.a === aId && c.b === bId) || (c.a === bId && c.b === aId)) && c.phase === phase);
  const shared = a.phases.filter((x) => b.phases.some((y) => y.role === x.role) && (phase === 'Shared assignments' || x.role === phase));
  return <section className="panel"><div className="section-top"><div><small>COMPARE THE EVIDENCE</small><h2>Candidate head-to-head</h2></div><p>Compare like assignments where the dataset supports it. Not an auction verdict.</p></div>
    <div className="controls comparison-controls"><label>Candidate A<select value={aId} onChange={(e) => setAId(Number(e.target.value))}>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Candidate B<select value={bId} onChange={(e) => setBId(Number(e.target.value))}>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Assignment<select value={phase} onChange={(e) => setPhase(e.target.value)}>{['Shared assignments', 'Powerplay', 'Middle overs', 'Death'].map((x) => <option key={x}>{x}</option>)}</select></label></div>
    <div className="comparison"><article><small>A / {a.matches} MATCHES</small><h3>{a.name}</h3><strong>{signed(a.score)}</strong><p>{bowling ? 'runs saved vs expected' : 'runs above expected'} per 100 pressure deliveries</p><p>{a.roles.join(', ') || 'Role evidence insufficient'} / {a.balls} pressure events / 95% interval [{a.interval.map((x) => fmt(x)).join(', ')}]</p></article><article><small>B / {b.matches} MATCHES</small><h3>{b.name}</h3><strong>{signed(b.score)}</strong><p>{bowling ? 'runs saved vs expected' : 'runs above expected'} per 100 pressure deliveries</p><p>{b.roles.join(', ') || 'Role evidence insufficient'} / {b.balls} pressure events / 95% interval [{b.interval.map((x) => fmt(x)).join(', ')}]</p></article></div>
    {aId === bId ? <p className="notice">Choose two different players.</p> : compare ? <ComparisonEvidence comparison={compare} reverse={compare.a !== aId} /> : <p className="notice">The available data does not support a formal matched comparison for this pair and assignment.</p>}
    {shared.length > 0 && <div className="table-wrap"><table><thead><tr><th>Shared phase</th><th>A: events / matches / runs per 100</th><th>B: events / matches / runs per 100</th></tr></thead><tbody>{shared.map((x) => { const y = b.phases.find((v) => v.role === x.role)!; return <tr key={x.role}><td>{x.role}</td><td>{x.balls} / {x.matches} / {signed(x.contribution)}</td><td>{y.balls} / {y.matches} / {signed(y.contribution)}</td></tr>; })}</tbody></table></div>}
    <p className="caption">Formal differences use shared innings, phase and IPL strata with match-cluster uncertainty. Descriptive phase rows are not adjusted comparisons. Venue and opposition effects are not controlled.</p>
  </section>;
}

function Methodology({ d }: { d: Analysis }) {
  const strictRuleUsed = d.margin_eligible_counts.batting >= 10 && d.margin_eligible_counts.bowling >= 10;
  return <div className="methodology-page">
    <section className="panel methodology-intro"><small>DATA AND METHOD</small><h2>How delivery data becomes a ranking</h2><p>This page documents the analysis that produced the rankings shown here, including where coverage is too weak for the original pressure definition.</p><a className="download" href="./results/methodology.pdf" download>Download the full methodology report</a><div className="method-steps"><article><b>01 / Audit</b><p>Check match completeness and delivery rules; exclude records that cannot be compared reliably.</p></article><article><b>02 / Reconstruct</b><p>Calculate the batting state before each delivery from runs, wickets and legal balls remaining.</p></article><article><b>03 / Estimate</b><p>Fit expectations on earlier seasons, then compare observed runs with those expectations.</p></article><article><b>04 / Rank</b><p>Shrink small samples and order eligible players by contextual run contribution.</p></article></div></section>
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
  const [selected, setSelected] = useState<{ player: Player; bowling: boolean } | null>(null);
  useEffect(() => { fetch('./results/analysis.json').then((response) => { if (!response.ok) throw new Error('Saved analysis could not be loaded. Run the export pipeline.'); return response.json(); }).then(setData).catch((e) => setError(String(e))); }, []);
  if (error) return <main><h1>Analysis unavailable</h1><p role="alert">{error}</p></main>;
  if (!data) return <main aria-busy="true"><h1>Loading the analysis...</h1></main>;

  const bowling = tab === 'BOWLERS';
  const players = bowling ? data.bowlers : data.batters;
  const roles = bowling ? ['Powerplay', 'Middle overs', 'Death'] : ['Opener', 'Middle order', 'Finisher'];
  const filtered = players.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) && (role === 'Overall' || p.roles.includes(role)));
  const pick = (p: Player, isBowling: boolean) => { setTab(isBowling ? 'BOWLERS' : 'BATTERS'); setRole('Overall'); setSearch(''); setSelected({ player: p, bowling: isBowling }); };

  return <><header><a className="brand" href="#home">RR<span> / RESOLVE</span></a><span>INDEPENDENT CRICKET ANALYSIS</span><a href="./results/methodology.pdf">Methodology report</a></header><main id="home">
    <section className="hero"><div><small>ROYALS' RESOLVE / CRICKET PRESSURE ANALYSIS</small><h1>Find the evidence.<br /><em>Understand the risk.</em></h1><p>Contextual run-contribution rankings from the supplied ball-by-ball data, with uncertainty and limitations shown alongside each result.</p></div><div className="hero-note"><span>WHAT THIS IS</span><p>A statistical research baseline for comparing pressure assignments.</p><small>NOT A PURCHASE RECOMMENDATION</small></div></section>
    <div className="status"><b>HOW TO READ THE LIST</b><span>Each list contains the 10 highest scores for that role; rank 1 is the strongest score. Because the strict margin rule identifies only 1 eligible batter, both lists use the documented phase and required-rate fallback. The score measures runs above (batting) or below (bowling) expectation in those situations; it is not a measure of overall player quality. 2027 availability and auction prices are not in the verified data, so the ranking does not label players as auction targets.</span></div>
    <TopPicks d={data} open={pick} />
    <section className="stats"><div><strong>{fmt(data.audit.deliveries, 0)}</strong><span>source deliveries audited</span></div><div><strong>{data.audit.retained_matches} / {data.audit.matches}</strong><span>matches retained</span></div><div><strong>{data.audit.oos_matches}</strong><span>out-of-time matches</span></div><div><strong>{data.batters_eligible_count + data.bowlers_eligible_count}</strong><span>eligible statistical findings</span></div></section>
    <div className="provenance-strip">Data dates: {data.audit.date_range.join(' to ')} | {data.audit.excluded_innings} innings excluded | {data.batters_eligible_count} eligible batters / {data.bowlers_eligible_count} eligible bowlers | analysis {data.version}<br />Ranking policy: {data.pressure_policy.replaceAll('_', ' ')}. Strict-margin coverage: {data.margin_eligible_counts.batting} batter(s) / {data.margin_eligible_counts.bowling} bowlers.</div>
    <nav aria-label="Analysis sections">{['BATTERS', 'BOWLERS', 'DATA & METHOD'].map((item) => <button key={item} aria-current={tab === item ? 'page' : undefined} onClick={() => { setTab(item); setRole('Overall'); setSearch(''); }}>{item}</button>)}</nav>
    {tab === 'DATA & METHOD' ? <Methodology d={data} /> : <>
      <section className="panel"><div className="section-top"><div><small>{bowling ? 'BOWLING CONTRIBUTION' : 'BATTING CONTRIBUTION'}</small><h2>Top ten {bowling ? 'bowlers' : 'batters'}</h2></div><p>Ranked highest to lowest by the published score.<br />Minimum sample: 30 events across 5 matches.</p></div>
        <div className="filters"><div role="group" aria-label="Role evidence filter">{['Overall', ...roles].map((item) => <button className={role === item ? 'active' : ''} key={item} onClick={() => setRole(item)}>{item}</button>)}</div><label><span className="sr-only">Search players</span><input placeholder="Search these ranked players" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div>
        <p className="caption">Ranks stay in overall order when filtered by role. Pressure events include illegal deliveries; legal balls are reported separately. Select a player to inspect the score calculation and its uncertainty.</p>
        <div className="table-wrap"><table><thead><tr><th>Rank</th><th>Player / demonstrated role</th><th>{bowling ? 'Runs saved vs expected' : 'Runs above expected'}</th><th>Pressure matches</th><th>95% interval</th><th>Evidence</th></tr></thead><tbody>{filtered.map((p) => <tr key={p.id}><td className="rank">{String(p.rank).padStart(2, '0')}</td><th><button className="player" onClick={() => setSelected({ player: p, bowling })}>{p.name}</button><span className="role">{p.roles.join(' / ') || 'Role evidence insufficient'}</span></th><td className="contribution">{signed(p.score)}<span className="role">per 100 pressure deliveries</span></td><td>{p.matches}<span className="role">{p.episodes} episodes / {p.balls} events</span></td><td className="interval">[{p.interval.map((x) => signed(x)).join(', ')}]<span className="role">{p.interval[0] <= 0 && p.interval[1] >= 0 ? 'Interval includes zero' : '95% match bootstrap'}</span></td><td><button className="case-button" onClick={() => setSelected({ player: p, bowling })}>Open scorecard</button></td></tr>)}</tbody></table>{!filtered.length && <p className="empty">No ranked players match this filter.</p>}</div>
        <p className="caption">Dismissals and wickets are separate from this run-only score. Non-striker run-outs are not assigned to striker exposure.</p>
      </section>
      <RawComparison stars={bowling ? data.bowlers_raw_stars : data.batters_raw_stars} />
      <section className="chart-grid"><IntervalChart players={filtered} bowling={bowling} /><UsualChart players={filtered} bowling={bowling} /></section>
      <CandidateComparison key={`candidate-${tab}`} players={players} comparisons={bowling ? data.bowlers_comparisons : data.batters_comparisons} bowling={bowling} />
      <IncumbentComparison key={`incumbent-${tab}`} d={data} players={players} bowling={bowling} />
      <details className="panel secondary-details"><summary>Robustness checks and scenario controls</summary><div className="details-content"><p>These saved scenarios test sensitivity to a different sample window, competition scope and pressure threshold. They do not refit the model in your browser.</p><CandidateStressTest players={players} comparisons={bowling ? data.bowlers_comparisons : data.batters_comparisons} /></div></details>
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
  const scenarioScore = (p: Player) => { if (scenario === 'Published') return p.score; const value = p.scenarios[scenario]; return typeof value === 'number' ? value : value?.score; };
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
