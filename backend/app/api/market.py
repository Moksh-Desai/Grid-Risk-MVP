"""Queue-wide statistics for the market view."""

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends

from app.api.deps import require_predictor
from app.config import TRAIN_COHORT_END
from app.data.regions import REGIONS, TECHNOLOGIES

router = APIRouter()

# Headline figures from Berkeley Lab's Queued Up reports, for context next to
# whatever data the app is running on.
PUBLISHED = {
    "source": "Berkeley Lab, Queued Up 2025 and 2026 editions (emp.lbl.gov/queues)",
    "facts": [
        "About 13% of capacity requesting interconnection in 2000-2019 reached operation by "
        "end of 2024; 77% withdrew.",
        "Median time from interconnection request to operation rose from under 2 years "
        "(built 2000-2007) to over 4 years (built 2018-2024).",
        "End of 2025: ~8,200 active projects, ~1,312 GW of generation and ~749 GW of storage, "
        "down about 10% from a year earlier.",
        "Withdrawn projects carried far higher upgrade estimates than completed ones "
        "(SPP: ~$304/kW vs ~$57/kW; MISO: ~$452/kW vs ~$102/kW).",
    ],
}


def _median(s):
    s = s.dropna()
    return None if s.empty else round(float(s.median()), 1)


@router.get("/market")
def market(pred=Depends(require_predictor)):
    p = pred.projects.copy()
    p["queue_year"] = [d.year for d in p.queue_date]
    active = p[p.status == "active"]
    cohort = p[p.queue_year <= TRAIN_COHORT_END]
    built = p[p.status == "operational"].copy()
    built["months"] = (pd.to_datetime(built.cod_date) - pd.to_datetime(built.queue_date)).dt.days / 30.44
    built["cod_year"] = pd.to_datetime(built.cod_date).dt.year
    recent_built = built[built.cod_year >= 2018]

    regions = []
    for code, info in REGIONS.items():
        a = active[active.iso_region == code]
        c = cohort[cohort.iso_region == code]
        rb = recent_built[recent_built.iso_region == code]
        r = p[p.iso_region == code]
        if r.empty:
            continue
        regions.append({
            "region": code,
            "name": info["name"],
            "active_projects": int(len(a)),
            "active_gw": round(a.proposed_capacity_mw.sum() / 1000, 1),
            "active_gw_by_tech": {t: round(a[a.technology_type == t].proposed_capacity_mw.sum() / 1000, 1)
                                  for t in TECHNOLOGIES},
            "completion_rate": None if c.empty else round(float((c.status == "operational").mean()), 3),
            "withdrawal_rate": None if c.empty else round(float((c.status == "withdrawn").mean()), 3),
            "median_months_to_cod": _median(rb.months),
            "cost_built_per_kw": _median(r[r.status == "operational"].upgrade_cost_per_kw),
            "cost_withdrawn_per_kw": _median(r[r.status == "withdrawn"].upgrade_cost_per_kw),
            "model_mean_active_probability": round(float(
                pred.active_scored[pred.active_scored.iso_region == code].p_complete.mean()), 3)
            if (pred.active_scored.iso_region == code).any() else None,
        })

    years = sorted(p.queue_year.unique())
    entries = [{"year": int(y), **{t: round(float(
        p[(p.queue_year == y) & (p.technology_type == t)].proposed_capacity_mw.sum() / 1000), 1)
        for t in TECHNOLOGIES}} for y in years]
    durations = [{"year": int(y), "median_months": _median(built[built.cod_year == y].months),
                  "n": int((built.cod_year == y).sum())}
                 for y in sorted(built.cod_year.dropna().unique())]

    by_tech = []
    for t in TECHNOLOGIES:
        c = cohort[cohort.technology_type == t]
        by_tech.append({"technology": t,
                        "completion_rate": None if c.empty else round(float((c.status == "operational").mean()), 3),
                        "active_gw": round(active[active.technology_type == t].proposed_capacity_mw.sum() / 1000, 1)})

    phase_counts = np.bincount(active.max_phase.astype(int), minlength=5).tolist() if len(active) else [0] * 5
    return {
        "data_sources": sorted(p.data_source.unique()),
        "cohort": f"queue years through {TRAIN_COHORT_END}",
        "totals": {
            "projects": int(len(p)),
            "active_projects": int(len(active)),
            "active_gw": round(active.proposed_capacity_mw.sum() / 1000, 1),
            "completion_rate": round(float((cohort.status == "operational").mean()), 3),
            "median_months_recent": _median(recent_built.months),
        },
        "regions": regions,
        "by_technology": by_tech,
        "entries_by_year_gw": entries,
        "duration_by_cod_year": durations,
        "active_by_phase": phase_counts,
        "published": PUBLISHED,
    }
