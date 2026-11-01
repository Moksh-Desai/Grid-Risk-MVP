import { useEffect, useState } from "react";
import { api } from "../api";
import { CalibrationPlot, HBars } from "../components/charts";
import { num, pct } from "../format";

export default function ModelView() {
  const [m, setM] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.model().then(setM).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!m || m.status !== "ready") return <p className="muted">Model status: {m?.status ?? "loading"}…</p>;

  const c = m.metrics.completion;
  const imp = c.importance.filter((r) => r.drop_in_auc > 0.0005).slice(0, 8);

  return (
    <div className="page">
      <p className="lead">
        Three models, trained {new Date(m.trained_at).toLocaleString()} on {num(m.n_projects)} queue records
        ({m.data_sources.join(", ")}). Scores below are measured on {m.metrics.test_window}, which the
        evaluation model never saw.
      </p>

      <div className="block">
        <h3>Models</h3>
        <table className="data">
          <thead><tr><th>Model</th><th>Method</th><th>Predicts</th></tr></thead>
          <tbody>
            {m.models.map((x) => (
              <tr key={x.name}><td>{x.name}</td><td>{x.type}</td><td>{x.predicts}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid2">
        <div className="block">
          <h3>Completion model vs baselines</h3>
          <table className="data compact">
            <thead><tr><th>Approach</th><th className="num">AUC</th><th className="num">Brier</th></tr></thead>
            <tbody>
              <tr><td><strong>Blend (used)</strong></td><td className="num">{c.auc.toFixed(3)}</td><td className="num">{c.brier.toFixed(4)}</td></tr>
              <tr><td>Gradient boosting alone</td><td className="num">{c.baselines.gradient_boosting.auc.toFixed(3)}</td><td className="num">{c.baselines.gradient_boosting.brier.toFixed(4)}</td></tr>
              <tr><td>Logistic regression</td><td className="num">{c.baselines.logistic_regression.auc.toFixed(3)}</td><td className="num">{c.baselines.logistic_regression.brier.toFixed(4)}</td></tr>
              <tr><td>Regional average only</td><td className="num">{c.baselines.regional_base_rate.auc.toFixed(3)}</td><td className="num">{c.baselines.regional_base_rate.brier.toFixed(4)}</td></tr>
            </tbody>
          </table>
          <p className="muted small">
            Trees capture interactions but cannot extrapolate the steady decline in completion rates;
            logistic regression can. Averaging the two beats either alone on ranking.
            AUC: how well the model ranks built above withdrawn projects (1 = perfect, 0.5 = coin flip).
            Brier: mean squared error of the probability (lower is better). AUC at queue entry only,
            before any study: {c.auc_at_entry ? c.auc_at_entry.toFixed(3) : "–"}. Test base rate {pct(c.test_base_rate)}.
          </p>
        </div>
        <div className="block">
          <h3>Calibration</h3>
          <CalibrationPlot bins={c.calibration} />
          <p className="muted small">Each dot is a tenth of test projects. On the dashed line, a 30% prediction comes true 30% of the time.</p>
        </div>
      </div>

      <div className="grid2">
        <div className="block">
          <h3>What the completion model relies on</h3>
          <HBars rows={imp.map((r) => ({ label: r.label, value: r.drop_in_auc }))} format={(v) => v.toFixed(3)} />
          <p className="muted small">Drop in test AUC when the feature is shuffled.</p>
        </div>
        <div className="block">
          <h3>Range models</h3>
          <table className="data compact">
            <thead><tr><th /><th className="num">Median error</th><th className="num">P10–P90 hit rate</th></tr></thead>
            <tbody>
              {["timeline", "cost"].map((k) => m.metrics[k] && (
                <tr key={k}>
                  <td>{k === "timeline" ? "Timeline" : "Upgrade cost"}</td>
                  <td className="num">{num(m.metrics[k].median_abs_error, 1)} {m.metrics[k].unit}</td>
                  <td className="num">
                    {pct(m.metrics[k].p10_p90_coverage)}
                    <span className="muted"> (raw {pct(m.metrics[k].p10_p90_coverage_raw)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Queues slowed and got pricier every year, so raw quantile models trained on older projects are
            overconfident. Conformal widening on recent projects brings the 80% range back to about 80%.
          </p>
        </div>
      </div>

      <div className="block">
        <h3>The reform assumption</h3>
        <p>{m.reform_assumption.why} When switched on, it adds {m.reform_assumption.logit_shift} to the log-odds.</p>
      </div>

      <div className="block">
        <h3>Limitations</h3>
        <ul className="facts-list">{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </div>
    </div>
  );
}
