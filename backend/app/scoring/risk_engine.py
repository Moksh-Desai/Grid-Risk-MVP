"""Turn model outputs into a decision-ready assessment."""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.data.regions import REGIONS
from app.ml.features import phase_label

DRIVER_GROUPS = [
    ("Study phase", ["phase"]),
    ("Upgrade cost estimate", ["upgrade_cost_per_kw"]),
    ("Project size", ["proposed_capacity_mw"]),
    ("Technology", ["technology_type", "is_hybrid"]),
    ("POI completion track record", ["poi_hist_rate", "poi_hist_n"]),
    ("POI crowding", ["poi_queue_mw"]),
    ("POI voltage", ["voltage_kv"]),
]


def risk_level(score):
    if score >= 67:
        return "Low"
    if score >= 33:
        return "Moderate"
    return "High"


def _months_to_date(months, start=None):
    start = start or date.today()
    return (start + timedelta(days=int(months * 30.44))).isoformat()


def _reference_row(pred, row):
    """A typical new request in the same region, for comparison."""
    region = row.iso_region
    active = pred.projects[(pred.projects.status == "active") & (pred.projects.iso_region == region)]
    ref = row.copy()
    site = pred.typical_site(region)
    for k, v in site.items():
        ref[k] = v
    ref["substation_id"] = None
    ref["phase"] = 0
    ref["upgrade_cost_per_kw"] = np.nan
    if not active.empty:
        ref["proposed_capacity_mw"] = float(active.proposed_capacity_mw.median())
        ref["technology_type"] = active.technology_type.mode().iloc[0]
        ref["is_hybrid"] = ref["technology_type"] == "hybrid"
    return ref


def drivers(pred, row, p_user, reform):
    """What moves this project's odds, versus a typical request in its region.

    For each factor, swap in the typical value and re-score. The difference
    is that factor's contribution in percentage points.
    """
    ref = _reference_row(pred, row)
    variants, labels = [], []
    for label, cols in DRIVER_GROUPS:
        if all(pd.isna(row[c]) and pd.isna(ref[c]) for c in cols):
            continue
        if all((row[c] == ref[c]) or (pd.isna(row[c]) and pd.isna(ref[c])) for c in cols):
            continue
        v = row.copy()
        for c in cols:
            v[c] = ref[c]
        if cols == ["poi_queue_mw"]:
            # Compare crowding as a share of capacity, at this project's own POI.
            v["poi_queue_mw"] = max(_crowding(ref) * row.existing_capacity_mw - row.proposed_capacity_mw, 0)
        variants.append(v)
        labels.append((label, cols))
    if not variants:
        return []
    p_alt = pred.predict_frame(pd.DataFrame(variants), reform).p_complete.to_numpy()
    out = []
    for (label, cols), pa in zip(labels, p_alt):
        effect = (p_user - pa) * 100
        out.append({
            "factor": label,
            "effect_pp": round(float(effect), 1),
            "yours": _describe(row, cols),
            "typical": _describe(ref, cols),
        })
    return sorted(out, key=lambda d: -abs(d["effect_pp"]))


def _crowding(r):
    """MW queued at the POI, including this project, as a multiple of its capacity."""
    cap = r.get("existing_capacity_mw")
    if cap is None or pd.isna(cap) or cap <= 0:
        return np.nan
    return (r["poi_queue_mw"] + r["proposed_capacity_mw"]) / cap


def _describe(r, cols):
    c = cols[0]
    v = r[c]
    if c == "phase":
        return phase_label(v)
    if c == "upgrade_cost_per_kw":
        return "not yet studied" if pd.isna(v) else f"${v:,.0f}/kW"
    if c == "proposed_capacity_mw":
        return f"{v:,.0f} MW"
    if c == "technology_type":
        return str(v)
    if c == "poi_hist_rate":
        n = r.get("poi_hist_n", 0) or 0
        return f"{v:.0%} built ({int(n)} past requests)"
    if c == "poi_queue_mw":
        ratio = _crowding(r)
        return f"{v:,.0f} MW queued" if pd.isna(ratio) else f"{ratio:.1f}× capacity queued"
    if c == "voltage_kv":
        return "unknown" if pd.isna(v) else f"{v:,.0f} kV"
    return str(v)


def assess(pred, req):
    item = req.model_dump()
    df = pred.rows([item])
    res = pred.predict_frame(df, req.reform_adjustment).iloc[0]
    row = df.iloc[0]
    p = float(res.p_complete)
    score = round(pred.percentile(p), 1)
    mw = req.capacity_mw
    region_rate = pred.region_ctx[req.region]["cohort_rate"] or 0.0

    timeline = None
    if not math.isnan(res.timeline_p50):
        timeline = {
            "months": {q: round(float(res[f"timeline_{q}"]), 1) for q in ("p10", "p50", "p90")},
            "cod_date": {q: _months_to_date(res[f"timeline_{q}"]) for q in ("p10", "p50", "p90")},
            "from_phase": phase_label(req.phase),
        }

    cost = None
    if not math.isnan(res.cost_p50):
        per_kw = {q: round(float(res[f"cost_{q}"]), 0) for q in ("p10", "p50", "p90")}
        cost = {
            "per_kw": per_kw,
            "total_musd": {q: round(v * mw / 1000, 1) for q, v in per_kw.items()},
            "your_estimate_per_kw": req.upgrade_cost_per_kw,
            "your_estimate_total_musd": round(req.upgrade_cost_per_kw * mw / 1000, 1)
            if req.upgrade_cost_per_kw is not None else None,
        }

    at_risk_musd = req.at_risk_per_kw * mw / 1000
    site = None
    if row.substation_id:
        s = pred.subs_ctx.loc[row.substation_id]
        site = {
            "substation_id": row.substation_id,
            "name": s.substation_name,
            "state": s.state,
            "voltage_kv": None if pd.isna(s.voltage_kv) else float(s.voltage_kv),
            "existing_capacity_mw": None if pd.isna(s.existing_capacity_mw) else float(s.existing_capacity_mw),
            "queued_mw": round(float(s.poi_queue_mw), 1),
            "past_requests": int(s.poi_hist_n),
            "past_built": int(s.poi_hist_completed),
        }

    warnings = []
    if site and site["existing_capacity_mw"] and mw > 0.8 * site["existing_capacity_mw"]:
        warnings.append("Project is large relative to this substation; expect major network upgrades.")
    if site and site["existing_capacity_mw"] and site["queued_mw"] > site["existing_capacity_mw"]:
        warnings.append("More MW are already queued at this POI than it can carry today.")
    if not site:
        warnings.append("No substation chosen: scored against a typical site in this region.")
    if req.reform_adjustment:
        warnings.append("Includes the Order 2023 reform assumption, which is not learned from data.")
    if set(pred.bundle["data_sources"]) == {"synthetic"}:
        warnings.append("Models are trained on synthetic data calibrated to public statistics; "
                        "load real queue data before relying on results.")

    return {
        "input": item,
        "region_name": REGIONS[req.region]["name"],
        "completion_probability": round(p, 4),
        "regional_base_rate": round(region_rate, 4),
        "viability_score": score,
        "risk_level": risk_level(score),
        "score_meaning": f"Better odds than {score:.0f}% of projects in today's queue",
        "timeline": timeline,
        "upgrade_cost": cost,
        "capital_at_risk": {
            "at_risk_musd": round(at_risk_musd, 2),
            "expected_loss_musd": round((1 - p) * at_risk_musd, 2),
        },
        "drivers": drivers(pred, row, p, req.reform_adjustment),
        "site": site,
        "warnings": warnings,
    }


def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def alternatives(pred, req, limit=20):
    """Score every substation in the region for this project as a new request."""
    subs = pred.subs_ctx[pred.subs_ctx.iso_region == req.region]
    if subs.empty:
        return {"origin": None, "results": []}
    base = req.model_dump()
    items = [{**base, "substation_id": sid, "phase": 0, "upgrade_cost_per_kw": None} for sid in subs.index]
    res = pred.predict(items, req.reform_adjustment)
    res.index = subs.index

    lat, lon = req.latitude, req.longitude
    if (lat is None or lon is None) and req.substation_id in subs.index:
        lat, lon = subs.loc[req.substation_id, ["latitude", "longitude"]]
    dist = None
    if lat is not None and lon is not None and subs.latitude.notna().any():
        dist = haversine_miles(lat, lon, subs.latitude.to_numpy(float), subs.longitude.to_numpy(float))

    table = pd.DataFrame({
        "substation_id": subs.index,
        "name": subs.substation_name.values,
        "state": subs.state.values,
        "voltage_kv": subs.voltage_kv.values,
        "existing_capacity_mw": subs.existing_capacity_mw.values,
        "queued_mw": subs.poi_queue_mw.round(0).values,
        "past_requests": subs.poi_hist_n.astype(int).values,
        "completion_probability": res.p_complete.round(4).values,
        "cost_p50_per_kw": res.cost_p50.round(0).values,
        "months_p50": res.timeline_p50.round(1).values,
        "distance_miles": None if dist is None else np.round(dist, 0),
        "latitude": subs.latitude.values,
        "longitude": subs.longitude.values,
    })
    table["undersized"] = table.existing_capacity_mw.notna() & (req.capacity_mw > 0.8 * table.existing_capacity_mw)
    table = table.sort_values(["undersized", "completion_probability"], ascending=[True, False])
    table["rank"] = range(1, len(table) + 1)

    current = None
    if req.substation_id in table.substation_id.values:
        current = table[table.substation_id == req.substation_id].iloc[0]
    out = table.head(limit)
    if current is not None and req.substation_id not in out.substation_id.values:
        out = pd.concat([out, current.to_frame().T])
    out = out.astype(object).where(pd.notna(out), None)
    return {
        "origin": None if lat is None else {"latitude": float(lat), "longitude": float(lon)},
        "selected": req.substation_id,
        "total_substations": int(len(table)),
        "results": out.to_dict("records"),
    }


def portfolio(pred, items, reform):
    data = [i.model_dump() for i in items]
    res = pred.predict(data, reform)
    rows = []
    for item, (_, r) in zip(data, res.iterrows()):
        p = float(r.p_complete)
        score = round(pred.percentile(p), 1)
        rows.append({
            "name": item.get("name") or f"{item['region']} {item['technology']} {item['capacity_mw']:.0f} MW",
            **{k: item[k] for k in ("region", "technology", "capacity_mw", "substation_id", "phase")},
            "completion_probability": round(p, 4),
            "viability_score": score,
            "risk_level": risk_level(score),
            "months_p50": None if math.isnan(r.timeline_p50) else round(float(r.timeline_p50), 1),
            "cost_p50_per_kw": None if math.isnan(r.cost_p50) else round(float(r.cost_p50), 0),
            "expected_mw": round(p * item["capacity_mw"], 1),
        })
    total_mw = sum(i["capacity_mw"] for i in data)
    expected = sum(r["expected_mw"] for r in rows)
    return {
        "summary": {
            "projects": len(rows),
            "total_mw": round(total_mw, 1),
            "expected_mw_built": round(expected, 1),
            "expected_projects_built": round(sum(r["completion_probability"] for r in rows), 2),
        },
        "results": sorted(rows, key=lambda r: r["completion_probability"]),
    }
