import { useEffect, useState } from "react";
import { api } from "../api";
import { TECH_LABEL } from "../format";

export default function ProjectForm({ meta, input, onChange, onSubmit, submitLabel, busy, compact }) {
  const [subs, setSubs] = useState([]);
  const [subsError, setSubsError] = useState(null);
  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    onChange({ ...input, [k]: v, ...(k === "region" ? { substation_id: "" } : {}) });
  };

  useEffect(() => {
    let live = true;
    api.substations(input.region)
      .then((r) => live && (setSubs(r.substations), setSubsError(null)))
      .catch((e) => live && (setSubs([]), setSubsError(e.message)));
    return () => {
      live = false;
    };
  }, [input.region]);

  const submit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form className="project-form" onSubmit={submit}>
      <label>
        Grid region
        <select value={input.region} onChange={set("region")}>
          {meta.regions.map((r) => (
            <option key={r.code} value={r.code}>{r.name}</option>
          ))}
        </select>
      </label>

      <div className="row2">
        <label>
          Technology
          <select value={input.technology} onChange={set("technology")}>
            {meta.technologies.map((t) => (
              <option key={t} value={t}>{TECH_LABEL[t] || t}</option>
            ))}
          </select>
        </label>
        <label>
          Size (MW)
          <input type="number" min="1" max="5000" step="1" value={input.capacity_mw}
            onChange={set("capacity_mw")} required />
        </label>
      </div>

      <label>
        Point of interconnection
        <select value={input.substation_id} onChange={set("substation_id")}>
          <option value="">Not chosen yet (typical site)</option>
          {subs.map((s) => (
            <option key={s.substation_id} value={s.substation_id}>
              {s.substation_name}
              {s.queued_mw != null ? ` · ${Math.round(s.queued_mw)} MW queued` : ""}
            </option>
          ))}
        </select>
        {subsError && <span className="field-note bad">{subsError}</span>}
      </label>

      {!compact && (
        <>
          <label>
            Where the project is now
            <select value={input.phase} onChange={set("phase")}>
              {meta.phases.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>

          <div className="row2">
            <label>
              Upgrade estimate ($/kW)
              <input type="number" min="0" step="1" placeholder="from a study, if any"
                value={input.upgrade_cost_per_kw} onChange={set("upgrade_cost_per_kw")}
                disabled={Number(input.phase) === 0} />
            </label>
            <label>
              Spend at risk ($/kW)
              <input type="number" min="0" step="1" value={input.at_risk_per_kw} onChange={set("at_risk_per_kw")} />
            </label>
          </div>
          <p className="field-note">
            Spend at risk: deposits, studies, land options and development cost you lose if the project withdraws.
          </p>
        </>
      )}

      <label className="check">
        <input type="checkbox" checked={input.reform_adjustment} onChange={set("reform_adjustment")} />
        Assume FERC Order 2023 reforms lift completion
      </label>

      <button type="submit" disabled={busy}>{busy ? "Working…" : submitLabel}</button>
    </form>
  );
}
