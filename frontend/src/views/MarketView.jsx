import { useEffect, useState } from "react";
import { api } from "../api";
import { HBars, StackedColumns, YearLine } from "../components/charts";
import { TECH_COLOR, TECH_LABEL, months, num, pct } from "../format";

export default function MarketView({ meta }) {
  const [m, setM] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.market().then(setM).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!m) return <p className="muted">Loading market data…</p>;

  const synthetic = m.data_sources.length === 1 && m.data_sources[0] === "synthetic";
  const regions = [...m.regions].sort((a, b) => (b.completion_rate ?? 0) - (a.completion_rate ?? 0));

  return (
    <div className="page">
      {synthetic && (
        <p className="notice">
          These figures come from the synthetic queue the models train on, calibrated to Berkeley Lab
          averages. It is a scaled sample, so totals are smaller than the real U.S. queue. Published
          figures are listed below for reference.
        </p>
      )}

      <div className="headline four">
        <div><span className="eyebrow">Active requests</span><span className="big">{num(m.totals.active_projects)}</span></div>
        <div><span className="eyebrow">Active capacity</span><span className="big">{num(m.totals.active_gw)} GW</span></div>
        <div><span className="eyebrow">Built, {m.cohort}</span><span className="big">{pct(m.totals.completion_rate)}</span></div>
        <div><span className="eyebrow">Median wait, built 2018+</span><span className="big">{months(m.totals.median_months_recent)}</span></div>
      </div>

      <div className="grid2">
        <div className="block">
          <h3>Share of requests that got built</h3>
          <HBars rows={regions.map((r) => ({ label: r.region, value: r.completion_rate }))}
            format={(v) => pct(v)} />
        </div>
        <div className="block">
          <h3>Upgrade cost: built vs withdrawn ($/kW, median)</h3>
          <table className="data compact">
            <thead><tr><th>Region</th><th className="num">Built</th><th className="num">Withdrawn</th><th className="num">Ratio</th></tr></thead>
            <tbody>
              {regions.map((r) => (
                <tr key={r.region}>
                  <td>{r.region}</td>
                  <td className="num">{num(r.cost_built_per_kw)}</td>
                  <td className="num">{num(r.cost_withdrawn_per_kw)}</td>
                  <td className="num">
                    {r.cost_built_per_kw ? `${(r.cost_withdrawn_per_kw / r.cost_built_per_kw).toFixed(1)}×` : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="block">
        <h3>New requests entering the queue (GW per year)</h3>
        <StackedColumns data={m.entries_by_year_gw} keys={meta.technologies} colors={TECH_COLOR}
          labels={TECH_LABEL} />
      </div>

      <div className="grid2">
        <div className="block">
          <h3>Median request-to-operation time, by year built</h3>
          <YearLine data={m.duration_by_cod_year.filter((d) => d.n >= 5)} xKey="year" yKey="median_months"
            format={months} />
        </div>
        <div className="block">
          <h3>Active queue by region and technology (GW)</h3>
          <table className="data compact">
            <thead>
              <tr>
                <th>Region</th>
                {meta.technologies.map((t) => <th key={t} className="num">{TECH_LABEL[t].split(" ")[0]}</th>)}
                <th className="num">Model odds</th>
              </tr>
            </thead>
            <tbody>
              {m.regions.map((r) => (
                <tr key={r.region}>
                  <td>{r.region}</td>
                  {meta.technologies.map((t) => <td key={t} className="num">{num(r.active_gw_by_tech[t])}</td>)}
                  <td className="num">{pct(r.model_mean_active_probability)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Model odds: average predicted completion for projects active today.</p>
        </div>
      </div>

      <div className="block">
        <h3>Published reference figures</h3>
        <ul className="facts-list">
          {m.published.facts.map((f) => <li key={f}>{f}</li>)}
        </ul>
        <p className="muted small">Source: {m.published.source}</p>
      </div>
    </div>
  );
}
