import { useState } from 'react';
import type { Analysis, Player, RawStar, SelectionCheck } from './types';
import { ComparisonEvidence } from './Evidence';

const fmt = (value: number) => value.toLocaleString('en-IN', { maximumFractionDigits: 1 });
const signed = (value: number) => `${value > 0 ? '+' : ''}${fmt(value)}`;

export function TopPicks({ d, open }: { d: Analysis; open: (p: Player, bowling: boolean) => void }) {
  const picks = [...d.batters.slice(0, 2).map((p) => ({ p, bowling: false })), ...d.bowlers.slice(0, 2).map((p) => ({ p, bowling: true }))];
  return <section className="top-picks"><div className="section-top"><div><small>QUICK SUMMARY / HIGHEST-RANKED FINDINGS</small><h2>Start with four players</h2></div><p>Two highest-ranked batters and two highest-ranked bowlers.<br />Sorted by contextual run contribution, highest to lowest.</p></div>
    <div className="pick-grid">{picks.map(({ p, bowling }) => <button key={`${bowling ? 'b' : 'a'}-${p.id}`} className="pick-card" onClick={() => open(p, bowling)}><small>{bowling ? 'BOWLING' : 'BATTING'} / RANK {p.rank}</small><h3>{p.name}</h3><p>{p.roles.join(' / ') || 'Role sample insufficient'}</p><strong>{signed(p.score)}</strong><span>{bowling ? 'runs saved vs expected' : 'runs above expected'} per 100 pressure deliveries</span><p>{p.matches} matches / {p.episodes} episodes / {p.balls} events</p><p className="pick-risk">95% interval [{p.interval.map(fmt).join(', ')}]. Best-match removal: {signed(p.leave_best_out)}. Run-only estimate; uncertainty remains.</p><b>Open scorecard</b></button>)}</div>
    <p className="caption">These are statistical findings, not auction targets. No current auction availability or price is verified.</p>
  </section>;
}

export function RawComparison({ stars }: { stars: RawStar[] }) {
  return <details className="panel secondary-details"><summary>Why not rank by raw scoring rate or economy?</summary><div className="details-content"><p>These leaders were selected by ordinary rate or economy in retained out-of-time data, with at least 120 events across five matches. The pressure score is a separate view, not proof that this method is better.</p>
    <div className="table-wrap"><table><thead><tr><th>Raw-stat leader</th><th>Ordinary rate</th><th>Events / matches</th><th>Pressure contribution</th><th>Pressure coverage</th></tr></thead><tbody>{stars.map((p) => <tr key={p.id}><th>{p.name}</th><td>{fmt(p.rate)}{p.average !== null ? ` / average ${fmt(p.average)}` : ''}</td><td>{p.events} / {p.matches}</td><td>{p.eligible_pressure ? `${signed(p.pressure_contribution)} runs / 100` : 'Insufficient evidence'}</td><td>{p.pressure_events} events / {p.pressure_matches} matches</td></tr>)}</tbody></table></div>
    <p className="caption">Batting rate is runs per 100 non-wide events; average uses attributed striker dismissals. Bowling rate is charged runs per six legal balls. Selection uses the stated raw statistic, not player fame.</p>
  </div></details>;
}

function HoldoutChart({ rows }: { rows: SelectionCheck[] }) {
  const years = [...new Set(rows.filter((x) => x.future_contribution !== null).map((x) => x.year))].sort();
  const policies = [...new Set(rows.filter((x) => x.future_contribution !== null).map((x) => x.policy))];
  const values = rows.flatMap((x) => x.future_contribution === null ? [] : [x.future_contribution]);
  if (!values.length) return <p>No comparable future-segment selection results are available.</p>;
  const lo = Math.min(-10, ...values); const hi = Math.max(10, ...values);
  const top = 25; const bottom = 230; const left = 54; const right = 700;
  const y = (v: number) => bottom - ((v - lo) / (hi - lo)) * (bottom - top);
  const groupWidth = (right - left) / Math.max(1, years.length);
  const colors = ['#c21868', '#263967', '#a57937', '#287565', '#78519a'];
  return <figure className="chart-card holdout-card"><figcaption>Later contribution by selection policy</figcaption><p className="chart-subtitle">Observed later-season contextual runs per 100 pressure events. Dots are separate year estimates; no line implies a continuous trend.</p>
    <div className="chart-scroll"><svg viewBox="0 0 760 320" role="img" aria-label="Grouped dot chart of later-season run contribution by selection policy">
      {[lo, 0, hi].map((v) => <g key={v}><line x1={left} x2={right} y1={y(v)} y2={y(v)} className={v === 0 ? 'zero-line' : 'grid-line'} /><text x={left - 8} y={y(v) + 4} textAnchor="end" className="axis-label">{fmt(v)}</text></g>)}
      {years.map((year, yi) => <g key={year}><text x={left + groupWidth * (yi + 0.5)} y="258" textAnchor="middle" className="axis-label">{year}{year === 2026 ? ' *' : ''}</text>{policies.map((policy, pi) => {
        const row = rows.find((r) => r.year === year && r.policy === policy && r.future_contribution !== null);
        if (!row) return null;
        const slot = groupWidth / (policies.length + 1);
        const cx = left + groupWidth * yi + slot * (pi + 0.7);
        return <g key={policy}><circle cx={cx} cy={y(row.future_contribution!)} r="5" fill={colors[pi % colors.length]}><title>{policy.replaceAll('_', ' ')}, {year}: {fmt(row.future_contribution!)} runs per 100; {row.observed_later} of {row.selected} selected players later observed; {row.future_events} events.</title></circle></g>;
      })}</g>)}
      <text x={(left + right) / 2} y="293" textAnchor="middle" className="axis-title">Test season (* 2026 was not prospectively sealed)</text>
      <text transform="rotate(-90 14 145)" x="14" y="145" textAnchor="middle" className="axis-title">Runs / 100 events</text>
    </svg></div>
    <div className="chart-legend">{policies.map((policy, i) => <span key={policy}><i className="legend-dot" style={{ backgroundColor: colors[i % colors.length] }} />{policyLabel(policy)}</span>)}</div>
  </figure>;
}

function policyLabel(policy: string) {
  const labels: Record<string, string> = { contextual: 'Contextual score', ordinary: 'Ordinary rate / economy', ordinary_average: 'Batting average', conservative: 'Conservative policy', phase_rate_baseline: 'Phase-rate baseline' };
  return labels[policy] || policy.replaceAll('_', ' ');
}

export function Backtest({ d }: { d: Analysis }) {
  const [role, setRole] = useState('batting');
  const rows = role === 'batting' ? d.batters_selection_validation : d.bowlers_selection_validation;
  return <div className="backtest" id="backtest"><small>RETROSPECTIVE SELECTION CHECK</small><h3>Did the selected players contribute later?</h3>
    <div className="filters"><div><button className={role === 'batting' ? 'active' : ''} onClick={() => setRole('batting')}>Batters</button><button className={role === 'bowling' ? 'active' : ''} onClick={() => setRole('bowling')}>Bowlers</button></div></div>
    <HoldoutChart rows={rows} />
    <p>Earlier-season lists are compared with those players' later observed pressure deliveries. Results vary, and later participation differs between lists. These are retrospective outcomes, not evidence of causal improvement. The 2026 holdout was available during this build.</p>
    <details className="secondary-details"><summary>View the underlying selection results</summary><div className="details-content table-wrap"><table><thead><tr><th>Selection year / policy</th><th>Observed / selected players</th><th>Later pressure events</th><th>Later runs / 100</th></tr></thead><tbody>{rows.map((x) => <tr key={`${x.year}-${x.policy}`}><th>{x.year} / {policyLabel(x.policy)}</th><td>{x.observed_later} / {x.selected}</td><td>{x.future_events}</td><td>{x.future_contribution === null ? 'Unavailable' : fmt(x.future_contribution)}</td></tr>)}</tbody></table></div></details>
  </div>;
}

export function IncumbentComparison({ d, players, bowling }: { d: Analysis; players: Player[]; bowling: boolean }) {
  const [candidate, setCandidate] = useState(players[0]?.id);
  const [incumbent, setIncumbent] = useState('');
  const cases = d.incumbent_comparisons.filter((c) => c.a === candidate && c.role === (bowling ? 'bowling' : 'batting'));
  const chosen = cases.find((c) => c.incumbent === incumbent) || cases[0];
  const player = players.find((p) => p.id === candidate);
  return <details className="panel secondary-details"><summary>Compare with a player in the verified 2026 RR squad</summary><div className="details-content"><p>This is a shared-evidence comparison only. Squad membership comes from the official 2026 source; 2027 retention and auction status are unknown.</p>
    <div className="controls comparison-controls"><label>Candidate<select value={candidate} onChange={(e) => { setCandidate(Number(e.target.value)); setIncumbent(''); }}>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Supported squad comparison<select value={chosen?.incumbent || ''} onChange={(e) => setIncumbent(e.target.value)}>{cases.length ? cases.map((c) => <option key={c.b}>{c.incumbent}</option>) : <option>No supported comparison</option>}</select></label></div>
    {chosen ? <><h3>{player?.name} compared with {chosen.incumbent}</h3><ComparisonEvidence comparison={chosen} /><p>Demonstrated role: {player?.roles.join(', ') || 'Insufficient role evidence'}. A shared assignment does not by itself prove a roster gap or auction upgrade.</p></> : <p>No shared pressure exposure meets the minimum evidence rule. No replacement verdict is shown.</p>}
  </div></details>;
}
