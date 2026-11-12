import { useState } from 'react';
import type { Analysis, Player, RawStar } from './types';
import { ComparisonEvidence } from './Evidence';

const fmt = (value: number) => value.toLocaleString('en-IN', { maximumFractionDigits: 1 });
const signed = (value: number) => `${value > 0 ? '+' : ''}${fmt(value)}`;

export function TopPicks({ d, open }: { d: Analysis; open: (p: Player, bowling: boolean) => void }) {
  const picks = [...d.batters.slice(0, 2).map((p) => ({ p, bowling: false })), ...d.bowlers.slice(0, 2).map((p) => ({ p, bowling: true }))];
  return <section className="top-picks"><div className="section-top"><div><small>QUICK SUMMARY</small><h2>Highest-ranked findings</h2></div></div>
    <div className="pick-grid">{picks.map(({ p, bowling }) => <button key={`${bowling ? 'b' : 'a'}-${p.id}`} className="pick-card" onClick={() => open(p, bowling)}><small>{bowling ? 'BOWLING' : 'BATTING'} / RANK {p.rank}</small><h3>{p.name}</h3><p>{p.roles.join(' / ') || 'Role sample insufficient'}</p><strong>{signed(p.score)}</strong><span>{bowling ? 'runs saved / 100 vs own usual' : 'runs scored / 100 vs own usual'}</span><p>{p.matches} pressure matches / {p.balls} pressure events ({p.ipl_balls} IPL, {p.t20i_balls} T20I)</p><p>{p.ipl_role_events} IPL role deliveries / {p.ipl_role_matches} matches in the evaluated window</p><p className="pick-risk">95% interval [{p.interval.map(fmt).join(', ')}]. Best-match removal: {signed(p.leave_best_out)}. Run-only estimate; uncertainty remains.</p><b>Open scorecard</b></button>)}</div>
  </section>;
}

export function RawComparison({ stars }: { stars: RawStar[] }) {
  return <details className="panel secondary-details"><summary>Why not rank by raw scoring rate or economy?</summary><div className="details-content"><p>These leaders were selected by ordinary rate or economy in retained out-of-time data, with at least 120 events across five matches. The pressure-lift score compares contextual output with each player's usual baseline; it is not proof the method predicts future performance better.</p>
    <div className="table-wrap"><table><thead><tr><th>Raw-stat leader</th><th>Ordinary rate</th><th>Events / matches</th><th>Pressure contribution vs model</th><th>Pressure coverage</th></tr></thead><tbody>{stars.map((p) => <tr key={p.id}><th>{p.name}</th><td>{fmt(p.rate)}{p.average !== null ? ` / average ${fmt(p.average)}` : ''}</td><td>{p.events} / {p.matches}</td><td>{p.eligible_pressure ? `${signed(p.pressure_contribution)} runs / 100` : 'Insufficient evidence'}</td><td>{p.pressure_events} events / {p.pressure_matches} matches</td></tr>)}</tbody></table></div>
    <p className="caption">Batting rate is runs per 100 non-wide events; average uses attributed striker dismissals. Bowling rate is charged runs per six legal balls. Selection uses the stated raw statistic, not player fame.</p>
  </div></details>;
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
    <p>Earlier-season lists are compared with what those players did later. Results vary; the 2026 check was not a sealed test.</p>
    <div className="table-wrap"><table><thead><tr><th>Year selected / method</th><th>Players seen later</th><th>Later deliveries</th><th>Pressure lift vs usual / 100</th></tr></thead><tbody>{rows.map((x) => <tr key={`${x.year}-${x.policy}`}><th>{x.year} / {policyLabel(x.policy)}</th><td>{x.observed_later} / {x.selected}</td><td>{x.future_events}</td><td>{x.future_contribution === null ? 'Unavailable' : fmt(x.future_contribution)}</td></tr>)}</tbody></table></div>
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
