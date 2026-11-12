import type { Comparison, Player } from './types';

const fmt = (value: number) => value.toLocaleString('en-IN', { maximumFractionDigits: 2 });

export function Supporting({ p }: { p: Player }) {
  const s = p.supporting;
  if (!s) return <section className="supporting-evidence"><h3>Extra match details</h3><p>These extra matchup and coaching details were not included for this player. The scorecard above still shows the available player, role, sample and season measures.</p></section>;
  return <section className="supporting-evidence"><h3>Additional observed evidence</h3>
    <p>These metrics describe observed assignments. They do not add weight to the published ranking. Cells without five independent matches are not shown.</p>
    {(p.matchups?.length || 0) > 0 && <><h4>Pressure matchup splits</h4><div className="table-wrap"><table><thead><tr><th>Context</th><th>Events / matches</th><th>Runs / 100 (95% interval)</th></tr></thead><tbody>{p.matchups?.map((x) => <tr key={x.dimension + x.value}><td>{x.dimension}: {x.value}</td><td>{x.events} / {x.matches}</td><td>{fmt(x.runs_per_100)} [{x.interval.map(fmt).join(', ')}]</td></tr>)}</tbody></table></div><p>Descriptive splits, not causal matchup effects. Batter handedness is the batter's own; bowler handedness is the opposing striker's.</p></>}
    {s.scoring_without_boundaries && <><h4>Scoring without boundaries</h4><p>{fmt(s.scoring_without_boundaries.nonboundary_runs_per_100_legal)} non-boundary runs per 100 legal balls; {fmt(s.scoring_without_boundaries.nonboundary_scoring_percent)}% non-boundary scoring events; {fmt(s.scoring_without_boundaries.boundary_share_bat_runs_percent)}% of batter runs from boundaries. Sample: {s.scoring_without_boundaries.legal_balls} legal balls across {s.scoring_without_boundaries.innings} innings.</p></>}
    {s.entry_readiness && <><h4>First six legal balls after entry</h4><div className="table-wrap"><table><thead><tr><th>Entry / prior collapse</th><th>Innings / legal balls</th><th>Runs / 100 legal</th><th>Dismissal probability</th></tr></thead><tbody>{s.entry_readiness.map((x, i) => <tr key={i}><td>{x.entry_phase} / {x.collapse_entry ? 'after collapse' : 'stable entry'}</td><td>{x.innings} / {x.legal_balls}</td><td>{fmt(x.runs_per_100_legal)}</td><td>{fmt(x.dismissal_probability_per_innings)}</td></tr>)}</tbody></table></div><p>Includes innings ending before six legal balls. A collapse means at least two wickets in the 12 legal balls before entry.</p></>}
    {s.recovery_assignments && <><h4>Observed recovery assignments</h4>{s.recovery_assignments.length ? <div className="table-wrap"><table><thead><tr><th>Entry / prior collapse</th><th>Events / matches</th><th>Contextual runs / 100</th></tr></thead><tbody>{s.recovery_assignments.map((x, i) => <tr key={i}><td>{x.entry_phase} / {x.collapse_entry ? 'after collapse' : 'stable entry'}</td><td>{x.events} / {x.matches}</td><td>{fmt(x.contextual_runs_per_100)}</td></tr>)}</tbody></table></div> : <p>Insufficient evidence.</p>}</>}
    {s.costly_delivery_exposure && <><h4>Observed costly-delivery exposure</h4><p>{s.costly_delivery_exposure.verified_wides} verified wides across {s.costly_delivery_exposure.events} events ({fmt(s.costly_delivery_exposure.wides_per_100_events)} per 100); {fmt(s.costly_delivery_exposure.boundaries_per_100_legal)} boundaries per 100 legal balls. {s.costly_delivery_exposure.no_balls} No-ball attribution is not sufficiently verified to score delivery quality.</p><h4>Follow-up after a boundary in the same over</h4>{s.boundary_damage_control ? <p>{s.boundary_damage_control.events} follow-up events in {s.boundary_damage_control.matches} matches. Observed boundaries: {fmt(s.boundary_damage_control.boundary_percent)}%, against {fmt(s.boundary_damage_control.expected_boundary_percent)}% expected. Charged runs: {s.boundary_damage_control.runs_conceded}; total runs prevented against context: {fmt(s.boundary_damage_control.runs_prevented)}. Opportunities count once after consecutive boundaries; terminal overs have fewer follow-ups. Selection bias remains.</p> : <p>Insufficient independent-match evidence.</p>}</>}
    {s.downside && <><h4>Variation across pressure matches</h4><p>Lower quartile: {fmt(s.downside.lower_quartile)}; median: {fmt(s.downside.median)} unpooled runs per 100. {s.downside.unfavourable_matches} unfavourable matches out of {s.downside.matches}. This describes match-to-match variation; the score interval describes uncertainty in the mean.</p></>}
  </section>;
}

const caseLabels: Record<string, string> = {
  capability_demonstrated: 'Demonstrated capability',
  current_verified_rr_coverage: 'Verified 2026 squad overlap',
  measured_gap_or_uncertainty: 'Measured difference and uncertainty',
  primary_alternative: 'Supported comparison',
  biggest_risk: 'Main limitation',
  actionability: 'Auction status',
};

export function RRCase({ p }: { p: Player }) {
  if (!p.rr_case) return <section><h3>RR roster comparison</h3><p>A verified RR role comparison is not available for this player.</p></section>;
  const entries = Object.entries(p.rr_case).filter(([key]) => key !== 'actionability');
  return <section><h3>What the RR data can support</h3><dl>{entries.map(([key, value]) => <div key={key}><dt>{caseLabels[key] || key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl><p className="caption">RR comparison uses official 2026 squad coverage. It does not verify 2027 retention or a roster gap.</p></section>;
}

export function ComparisonEvidence({ comparison, reverse = false }: { comparison: Comparison; reverse?: boolean }) {
  const c = comparison;
  const interval: [number, number] = reverse ? [-c.interval[1], -c.interval[0]] : c.interval;
  const difference = c.difference * (reverse ? -1 : 1);
  return <div className="comparison-evidence"><b>{interval[0] > 0 ? 'A has the stronger estimated contribution' : interval[1] < 0 ? 'B has the stronger estimated contribution' : 'The interval includes no difference'}</b>
    <p>A minus B: {fmt(difference)} contextual runs per 100 pressure events. 95% match-cluster interval [{interval.map(fmt).join(', ')}].</p>
    <p>A: {reverse ? c.b_events : c.a_events} events / {reverse ? c.b_matches : c.a_matches} matches. B: {reverse ? c.a_events : c.b_events} / {reverse ? c.a_matches : c.b_matches}. {c.strata} shared strata. Excluded non-overlap events: A {reverse ? c.b_excluded_nonoverlap : c.a_excluded_nonoverlap}; B {reverse ? c.a_excluded_nonoverlap : c.b_excluded_nonoverlap}.</p>
    <p>{c.reference} This is uncertainty in expected contribution, not next-match win probability.</p>
  </div>;
}

export function ScoreBar({ value, scale, label, tone = '' }: { value: number; scale: number; label: string; tone?: string }) {
  const width = Math.min(48, (Math.abs(value) / Math.max(1, scale)) * 48);
  return <div className="score-track" role="img" aria-label={label} title={label}>
    <span className={`score-fill ${value < 0 ? 'negative' : 'positive'} ${tone}`} style={{ left: value < 0 ? `${50 - width}%` : '50%', width: `${width}%` }} />
  </div>;
}
