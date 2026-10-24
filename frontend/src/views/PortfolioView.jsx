import { useState } from "react";
import { api } from "../api";
import { LEVEL_CLASS, TECH_LABEL, months, num, pct } from "../format";

const SAMPLE = `name,region,technology,capacity_mw,phase,upgrade_cost_per_kw
Prairie Wind II,SPP,wind,250,1,180
Lone Star Storage,ERCOT,storage,200,0,
Valley Solar,CAISO,solar,400,2,240
Keystone Hybrid,PJM,hybrid,150,3,95
Lakeshore Solar,MISO,solar,120,0,`;

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  const head = lines[0].split(",").map((h) => h.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    const row = {};
    head.forEach((h, i) => {
      const v = (cells[i] ?? "").trim();
      if (v !== "") row[h] = ["capacity_mw", "phase", "upgrade_cost_per_kw", "queue_year"].includes(h) ? Number(v) : v;
    });
    return row;
  });
}

function toCsv(rows) {
  const cols = ["name", "region", "technology", "capacity_mw", "phase", "completion_probability",
    "viability_score", "risk_level", "months_p50", "cost_p50_per_kw", "expected_mw"];
  const esc = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v);
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export default function PortfolioView() {
  const [text, setText] = useState(SAMPLE);
  const [reform, setReform] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const handle = async (promise) => {
    setBusy(true);
    setError(null);
    try {
      setData(await promise);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const runText = () => {
    let projects;
    try {
      projects = parseCsv(text);
    } catch {
      setError("Could not read that CSV.");
      return;
    }
    handle(api.portfolio(projects, reform));
  };

  const upload = (e) => {
    const f = e.target.files?.[0];
    if (f) handle(api.portfolioCsv(f, reform));
    e.target.value = "";
  };

  const download = () => {
    const blob = new Blob([toCsv(data.results)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "grid-risk-portfolio.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="split">
      <aside>
        <h2>Screen a portfolio</h2>
        <p className="muted small">
          Paste or upload a CSV with <code>name, region, technology, capacity_mw</code> and optionally{" "}
          <code>phase</code> (0–4), <code>upgrade_cost_per_kw</code>, <code>substation_id</code>. Up to 500 rows.
        </p>
        <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
          aria-label="Portfolio CSV" />
        <label className="check">
          <input type="checkbox" checked={reform} onChange={(e) => setReform(e.target.checked)} />
          Assume FERC Order 2023 reforms lift completion
        </label>
        <div className="buttons">
          <button type="button" onClick={runText} disabled={busy}>{busy ? "Scoring…" : "Score pasted rows"}</button>
          <label className="button secondary">
            Upload CSV
            <input type="file" accept=".csv,text/csv" onChange={upload} hidden />
          </label>
        </div>
      </aside>
      <section className="results">
        {error && <p className="error">{error}</p>}
        {!data && !error && (
          <div className="intro">
            <h2>How much of the pipeline will really get built?</h2>
            <p>
              Queue positions are not megawatts. Weight each project by its odds to get a realistic view of
              what a pipeline will deliver, and to see which projects to fund, fix or drop.
            </p>
          </div>
        )}
        {data && (
          <>
            <div className="headline">
              <div>
                <span className="eyebrow">Pipeline</span>
                <span className="big">{num(data.summary.total_mw)} MW</span>
                <span className="muted">{data.summary.projects} projects</span>
              </div>
              <div>
                <span className="eyebrow">Expected to be built</span>
                <span className="big">{num(data.summary.expected_mw_built)} MW</span>
                <span className="muted">≈ {num(data.summary.expected_projects_built, 1)} projects</span>
              </div>
            </div>
            {data.errors?.length > 0 && (
              <ul className="warnings">
                {data.errors.map((e) => <li key={e.line}>Line {e.line} skipped: {e.error}</li>)}
              </ul>
            )}
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Project</th><th>Region</th><th>Tech</th><th className="num">MW</th>
                    <th className="num">Odds</th><th className="num">Score</th><th className="num">To COD</th>
                    <th className="num">Upgrade $/kW</th><th className="num">Expected MW</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((r, i) => (
                    <tr key={`${r.name}-${i}`}>
                      <td>{r.name}</td><td>{r.region}</td><td>{TECH_LABEL[r.technology]}</td>
                      <td className="num">{num(r.capacity_mw)}</td>
                      <td className="num">{pct(r.completion_probability, 1)}</td>
                      <td className={`num ${LEVEL_CLASS[r.risk_level]}`}>{Math.round(r.viability_score)}</td>
                      <td className="num">{months(r.months_p50)}</td>
                      <td className="num">{num(r.cost_p50_per_kw)}</td>
                      <td className="num">{num(r.expected_mw, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button type="button" className="secondary" onClick={download}>Download results CSV</button>
          </>
        )}
      </section>
    </div>
  );
}
