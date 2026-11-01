import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import ProjectForm from "../components/ProjectForm";
import { toPayload } from "../input";
import { SiteScatter } from "../components/charts";
import { months, num, pct } from "../format";

const COLUMNS = [
  { key: "rank", label: "#", num: true },
  { key: "name", label: "Substation" },
  { key: "completion_probability", label: "Odds", num: true, fmt: (v) => pct(v, 1) },
  { key: "cost_p50_per_kw", label: "Upgrade $/kW", num: true, fmt: (v) => num(v) },
  { key: "months_p50", label: "To COD", num: true, fmt: months },
  { key: "queued_mw", label: "Queued MW", num: true, fmt: (v) => num(v) },
  { key: "existing_capacity_mw", label: "Capacity MW", num: true, fmt: (v) => num(v) },
  { key: "distance_miles", label: "Miles", num: true, fmt: (v) => num(v) },
];

export default function CompareView({ meta, input, setInput, onAssess }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(true);
  const [sort, setSort] = useState({ key: "rank", dir: 1 });

  // Every site is scored as a fresh request: no study phase, no cost estimate yet.
  const fetchRanks = (inp) =>
    api.alternatives({ ...toPayload(inp), phase: 0, upgrade_cost_per_kw: null }, 40);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await fetchRanks(input));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Score on open so the tab is useful straight away.
  useEffect(() => {
    let live = true;
    fetchRanks(input)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message))
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    const r = [...data.results];
    r.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av > bv ? 1 : av < bv ? -1 : 0) * sort.dir;
    });
    return r;
  }, [data, sort]);

  const pick = (row) => {
    setInput({ ...input, substation_id: row.substation_id });
    onAssess();
  };

  return (
    <div className="split">
      <aside>
        <h2>Find a better POI</h2>
        <p className="muted small">
          Every substation in the region, scored for this project as a new request. Use it before you
          pay for a study.
        </p>
        <ProjectForm meta={meta} input={input} onChange={setInput} onSubmit={run}
          submitLabel="Rank substations" busy={busy} compact />
      </aside>
      <section className="results">
        {error && <p className="error">{error}</p>}
        {data && (
          <>
            <h2>{data.total_substations} substations ranked</h2>
            <SiteScatter rows={data.results} selected={data.selected} onPick={pick} />
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    {COLUMNS.map((c) => (
                      <th key={c.key} className={c.num ? "num" : ""}
                        aria-sort={sort.key === c.key ? (sort.dir > 0 ? "ascending" : "descending") : "none"}>
                        <button type="button" className="sort"
                          onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? -s.dir : c.key === "rank" || c.key === "name" ? 1 : -1 }))}>
                          {c.label}{sort.key === c.key ? (sort.dir > 0 ? " ↑" : " ↓") : ""}
                        </button>
                      </th>
                    ))}
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.substation_id} className={r.substation_id === data.selected ? "selected" : ""}>
                      {COLUMNS.map((c) => (
                        <td key={c.key} className={c.num ? "num" : ""}>
                          {c.fmt ? c.fmt(r[c.key]) : r[c.key]}
                          {c.key === "name" && r.undersized && <span className="tag">undersized</span>}
                          {c.key === "name" && r.substation_id === data.selected && <span className="tag">current</span>}
                        </td>
                      ))}
                      <td><button type="button" className="link" onClick={() => pick(r)}>Assess</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
