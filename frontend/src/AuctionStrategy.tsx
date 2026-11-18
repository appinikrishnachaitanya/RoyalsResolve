import { useEffect, useState } from 'react';

type Pick = {
  name: string;
  role: 'batting' | 'bowling';
  assignments: string[];
  rationale: string;
  status: string;
  ipl_output: number | null;
  ipl_range: [number, number] | null;
  deliveries: number;
  matches: number;
  positive_matches: number;
};

type Strategy = {
  analysis_id: string;
  as_of: string;
  squad: {
    retained_players: string[];
    maximum_vacancies: number;
    purse_crore: number;
    source: string;
  };
  picks: Pick[];
};

const crore = (lakhs: number) => '₹' + (lakhs / 100).toFixed(2) + ' crore';
const signed = (value: number) => (value > 0 ? '+' : '') + value.toFixed(1);

export function AuctionStrategy({ analysisId }: { analysisId: string }) {
  const [strategy, setStrategy] = useState<Strategy>();
  const [error, setError] = useState('');
  const [role, setRole] = useState<Pick['role']>('batting');
  const [bids, setBids] = useState<Record<string, string>>({});
  useEffect(() => {
    const controller = new AbortController();
    fetch('./results/auction-strategy.json', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error('The saved strategy could not be loaded.');
        return response.json() as Promise<Strategy>;
      })
      .then(result => {
        if (result.analysis_id !== analysisId) throw new Error('The rankings and auction strategy are from different runs.');
        setStrategy(result);
      })
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [analysisId]);

  if (!strategy) return <section className="panel" role="status">{error || 'Loading auction strategy…'}</section>;
  const { squad, picks } = strategy;
  const selected = picks.filter(p => Object.hasOwn(bids, p.name));
  const purse = Math.round(squad.purse_crore * 100);
  const entered = selected.filter(p => bids[p.name] !== '');
  const invalid = entered.some(p => !Number.isSafeInteger(Number(bids[p.name])) || Number(bids[p.name]) <= 0);
  const spent = entered.reduce((sum, p) => sum + (Number(bids[p.name]) || 0), 0);
  const batting = selected.filter(p => p.role === 'batting').length;
  const death = selected.filter(p => p.role === 'bowling' && p.assignments.includes('Death')).length;

  return <>
    <section className="panel auction-panel">
      <h2>RR Auction Strategy</h2>
      <p>Ten batting targets and ten bowling targets, grouped by RR squad needs. Confirm 2027 auction registration before pursuing any candidate.</p>
      <div className="filters auction-role-switch" role="group" aria-label="Auction target role">
        {(['batting', 'bowling'] as const).map(item => <button type="button" key={item}
          className={role === item ? 'active' : undefined} aria-pressed={role === item}
          onClick={() => setRole(item)}>{item === 'batting' ? 'Top 10 batters' : 'Top 10 bowlers'}</button>)}
      </div>
      <div className="table-wrap"><table className="auction-table"><colgroup><col/><col/><col/><col/></colgroup>
        <thead><tr><th>Player</th><th>Role and RR fit</th><th>IPL pressure evidence</th><th>Mock squad</th></tr></thead>
        <tbody>{picks.filter(p => p.role === role).map(p => {
          const added = Object.hasOwn(bids, p.name);
          return <tr key={p.name}>
            <th>{p.name}<span className="role">{p.status}</span></th>
            <td>{p.rationale}</td>
            <td>{p.ipl_output === null ? 'Below IPL sample rules' : `${signed(p.ipl_output)} runs ${p.role === 'bowling' ? 'saved' : 'above expectation'} / 100`}
              {p.ipl_range && <span className="role">95% range {p.ipl_range.map(signed).join(' to ')}</span>}
              <span className="role">{p.deliveries} deliveries · {p.positive_matches}/{p.matches} matches above expectation</span>
            </td>
            <td><button type="button" className="auction-action" aria-label={`${added ? "Remove" : "Add"} ${p.name}`} aria-pressed={added} disabled={!added && selected.length >= squad.maximum_vacancies}
              onClick={() => setBids(current => {
                const next = { ...current };
                if (Object.hasOwn(next, p.name)) delete next[p.name];
                else next[p.name] = '';
                return next;
              })}>{added ? 'Remove' : 'Add'}</button></td>
          </tr>;
        })}</tbody>
      </table></div>
    </section>
    <section className="panel auction-panel">
      <h3>Mock Auction</h3>
      <p>Set hypothetical bids in lakh. Review slot usage, role coverage and remaining purse as you add players.</p>
      <div className="stat-callouts" aria-live="polite">
        <div><b>{selected.length}/{squad.maximum_vacancies}</b><span>vacancies used</span></div>
        <div><b>{invalid ? 'Check bids' : crore(purse - spent)}</b><span>purse after entered bids</span></div>
        <div><b>{batting}</b><span>batting additions</span></div>
        <div><b>{death}</b><span>death bowling options</span></div>
      </div>
      {selected.length === 0 && <p>Add a player from the scouting table to start.</p>}
      {selected.length > 0 && <div className="auction-bids">{selected.map(p => <label key={p.name}>
        {p.name} bid in lakh
        <input type="number" min="1" step="1" value={bids[p.name]} onChange={event => {
          const value = event.target.value;
          setBids(current => ({ ...current, [p.name]: value }));
        }} />
      </label>)}
        <button type="button" className="auction-reset" onClick={() => setBids({})}>Reset mock squad</button>
      </div>}
      {(invalid || spent > purse) && <p role="alert">{invalid ? 'Enter bids in positive whole lakhs.' : 'Entered bids exceed the available purse.'}</p>}
      {entered.length < selected.length && <p>{selected.length - entered.length} selected players still need a bid.</p>}
      <details><summary>Current squad as of {strategy.as_of}</summary><ul>{squad.retained_players.map(name => <li key={name}>{name}</li>)}</ul>
        <a href={squad.source}>Rajasthan Royals squad announcement</a>
      </details>
    </section>
  </>;
}
