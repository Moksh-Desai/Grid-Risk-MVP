import { useState } from "react";
import { api } from "../api";
import ProjectForm from "../components/ProjectForm";
import { toPayload } from "../input";
import { DriverBars, RangeBar } from "../components/charts";
import { LEVEL_CLASS, money, monthYear, months, num, pct } from "../format";

export default function AssessView({ meta, input, setInput, onCompare }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.assess(toPayload(input)));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="split">
      <aside>
        <h2>Your project</h2>
        <ProjectForm meta={meta} input={input} onChange={setInput} onSubmit={run}
          submitLabel="Assess project" busy={busy} />
      </aside>
      <section className="results" aria-live="polite">
        {error && <p className="error">{error}</p>}
        {!result && !error && <Intro />}
        {result && <Assessment r={result} onCompare={onCompare} />}
      </section>
    </div>
  );
}

function Intro() {
  return (
    <div className="intro">
      <h2>Will this project actually get built?</h2>
      <p>
        Most projects that enter a U.S. interconnection queue never reach operation. Berkeley Lab finds
        only about 13% of capacity that requested interconnection from 2000 to 2019 was operating by 2024, and the
        median wait has passed four years. Studies that price the upgrades take months and cost real money.
      </p>
      <p>
        This tool is the screen before the study. Describe a project and get calibrated odds of
        completion, a timeline range, an upgrade-cost range, what drives the risk, and which nearby
        substations would do better.
      </p>
    </div>
  );
}

function Assessment({ r, onCompare }) {
  const t = r.timeline;
  const c = r.upgrade_cost;
  return (
    <>
      <div className="headline">
        <div>
          <span className="eyebrow">Chance of reaching operation</span>
          <span className="big">{pct(r.completion_probability, r.completion_probability < 0.1 ? 1 : 0)}</span>
          <span className="muted">
            {r.region_name}: {pct(r.regional_base_rate)} of past requests got built
          </span>
        </div>
        <div>
          <span className="eyebrow">Viability score</span>
          <span className={`big ${LEVEL_CLASS[r.risk_level]}`}>{Math.round(r.viability_score)}</span>
          <span className="muted">{r.score_meaning} · {r.risk_level} risk</span>
        </div>
      </div>

      {r.warnings.length > 0 && (
        <ul className="warnings">
          {r.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}

      <div className="grid2">
        {t && (
          <div className="block">
            <h3>Time to operation</h3>
            <p className="lead">
              Likely <strong>{months(t.months.p50)}</strong> from {t.from_phase.toLowerCase()}
              <span className="muted"> · around {monthYear(t.cod_date.p50)}</span>
            </p>
            <RangeBar {...t.months} format={months} />
            <p className="muted small">
              80% range: {monthYear(t.cod_date.p10)} to {monthYear(t.cod_date.p90)}, if it gets built.
            </p>
          </div>
        )}
        {c && (
          <div className="block">
            <h3>Network upgrade cost</h3>
            <p className="lead">
              Typical <strong>${num(c.per_kw.p50)}/kW</strong>
              <span className="muted"> · about {money(c.total_musd.p50)} for this project</span>
            </p>
            <RangeBar {...c.per_kw} format={(v) => `$${num(v)}`}
              marker={c.your_estimate_per_kw ?? undefined} markerLabel="your estimate" />
            <p className="muted small">
              80% range {money(c.total_musd.p10)} to {money(c.total_musd.p90)} before any study. Projects that
              later withdraw tend to sit at the high end.
            </p>
          </div>
        )}
      </div>

      <div className="block">
        <h3>What moves the odds</h3>
        <p className="muted small">
          Each factor is swapped for a typical new request in this region and the project re-scored.
          Positive means the factor helps.
        </p>
        <DriverBars drivers={r.drivers} />
      </div>

      <div className="grid2">
        <div className="block">
          <h3>Money at risk</h3>
          <dl className="facts">
            <dt>Pre-construction spend</dt><dd>{money(r.capital_at_risk.at_risk_musd)}</dd>
            <dt>Expected loss from withdrawal</dt><dd>{money(r.capital_at_risk.expected_loss_musd)}</dd>
          </dl>
          <p className="muted small">Expected loss = spend × chance the project withdraws.</p>
        </div>
        <div className="block">
          <h3>Point of interconnection</h3>
          {r.site ? (
            <dl className="facts">
              <dt>Substation</dt><dd>{r.site.name}</dd>
              <dt>Capacity</dt><dd>{num(r.site.existing_capacity_mw)} MW at {num(r.site.voltage_kv)} kV</dd>
              <dt>Already queued</dt><dd>{num(r.site.queued_mw)} MW</dd>
              <dt>Track record</dt><dd>{r.site.past_built} built of {r.site.past_requests} resolved requests</dd>
            </dl>
          ) : (
            <p className="muted">No substation picked. Compare sites to find one.</p>
          )}
          <button type="button" className="secondary" onClick={onCompare}>Compare sites in this region →</button>
        </div>
      </div>
    </>
  );
}
