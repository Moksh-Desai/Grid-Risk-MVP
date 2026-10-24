"""Turn queue records into model features.

Every feature is computed as of a point in time (a project's queue date for
training, the data cutoff for live scoring), using only events before that
point, so the models never see the future.
"""

from datetime import date

import numpy as np
import pandas as pd

from app.data.regions import PHASES, REGIONS, TECHNOLOGIES
from app.database import engine

PHASE_DATE_COLS = ["queue_date", "sis_date", "facilities_date", "ia_date", "construction_date"]

CAT_FEATURES = ["iso_region", "technology_type"]
# Queue context enters as ratios, not raw counts. Raw counts (MW queued,
# past requests, regional GW) mostly grow with the calendar, so a model
# trained on older years would misread today's far larger queue.
#   poi_crowding:  (MW queued at the POI + this project) / POI capacity, divided
#                  by the same ratio for the whole region at that time
#   poi_hist_lift: POI completion rate / region completion rate, both as of entry
SITE_FEATURES = [
    "log_mw", "queue_year", "voltage_kv", "poi_crowding", "poi_hist_lift", "is_hybrid",
]
# Completion and timeline models also know the phase and any cost estimate.
STATUS_FEATURES = SITE_FEATURES + ["phase", "upgrade_cost_per_kw"]

REGION_DTYPE = pd.CategoricalDtype(list(REGIONS))
TECH_DTYPE = pd.CategoricalDtype(TECHNOLOGIES)
PRIOR_WEIGHT = 3.0
COST_MASK_RATE = 0.3  # pseudo-count pulling small-sample POI rates to the region rate


def load_frames():
    projects = pd.read_sql_table("projects", engine)
    subs = pd.read_sql_table("substations", engine)
    for c in PHASE_DATE_COLS + ["cod_date", "withdrawn_date"]:
        projects[c] = pd.to_datetime(projects[c]).dt.date
    return projects, subs


def _ordinal(series):
    s = pd.to_datetime(pd.Series(list(series)), errors="coerce")
    return ((s - pd.Timestamp("1970-01-01")).dt.days + date(1970, 1, 1).toordinal()).to_numpy(float)


def _counts_before(times, weights, t):
    """Sum of weights with time < t, for each t."""
    order = np.argsort(times)
    ts = times[order]
    cum = np.concatenate([[0.0], np.cumsum(weights[order])])
    return cum[np.searchsorted(ts, t, side="left")]


class QueueState:
    """Answers "what did the queue look like at time t" for regions and POIs."""

    def __init__(self, projects: pd.DataFrame):
        p = projects
        self.q = _ordinal(p.queue_date)
        end = np.where(p.status == "operational", _ordinal(p.cod_date), _ordinal(p.withdrawn_date))
        self.end = np.where(np.isnan(end), np.inf, end)
        self.mw = p.proposed_capacity_mw.to_numpy(float)
        self.done = (p.status == "operational").to_numpy(float)
        self.resolved = np.isfinite(self.end).astype(float)
        self.region_idx = p.groupby("iso_region", observed=True).indices
        self.poi_idx = p.groupby("substation_id").indices  # NaN keys are dropped

    def _group(self, idx, t):
        q, end, mw = self.q[idx], self.end[idx], self.mw[idx]
        active_mw = _counts_before(q, mw, t) - _counts_before(end, mw * self.resolved[idx], t)
        n_res = _counts_before(end, self.resolved[idx], t)
        n_done = _counts_before(end, self.done[idx] * self.resolved[idx], t)
        return active_mw, n_res, n_done

    def region(self, region, t):
        idx = self.region_idx.get(region)
        if idx is None:
            z = np.zeros(len(np.atleast_1d(t)))
            return z, z, z
        return self._group(idx, np.atleast_1d(t))

    def poi(self, sid, t):
        idx = self.poi_idx.get(sid)
        if idx is None:
            z = np.zeros(len(np.atleast_1d(t)))
            return z, z, z
        return self._group(idx, np.atleast_1d(t))


def smoothed_rate(n_done, n_res, prior=0.2, weight=10.0):
    """Region completion rate among resolved projects, steadied when few exist."""
    return (np.asarray(n_done) + weight * prior) / (np.asarray(n_res) + weight)


def entry_context(projects: pd.DataFrame, subs: pd.DataFrame, state: QueueState = None):
    """Queue context each project faced on the day it entered."""
    state = state or QueueState(projects)
    p = projects.reset_index(drop=True)
    t = _ordinal(p.queue_date)
    out = pd.DataFrame(index=p.index, columns=["poi_queue_mw", "poi_hist_n", "poi_hist_rate",
                                               "region_queue_gw", "region_rate_t"], dtype=float)
    region_rate = {}
    for region, idx in p.groupby("iso_region", observed=True).indices.items():
        active, n_res, n_done = state.region(region, t[idx])
        out.loc[idx, "region_queue_gw"] = active / 1000
        region_rate[region] = (idx, smoothed_rate(n_done, n_res))
    prior = np.full(len(p), 0.2)
    for idx, rate in region_rate.values():
        prior[idx] = rate
    out["region_rate_t"] = prior
    for sid, idx in p.groupby("substation_id").indices.items():
        active, n_res, n_done = state.poi(sid, t[idx])
        out.loc[idx, "poi_queue_mw"] = active
        out.loc[idx, "poi_hist_n"] = n_res
        out.loc[idx, "poi_hist_rate"] = (n_done + PRIOR_WEIGHT * prior[idx]) / (n_res + PRIOR_WEIGHT)
    return out


def region_capacity(subs):
    """Total substation capacity (MW) per region."""
    return subs.groupby("iso_region").existing_capacity_mw.sum(min_count=1).to_dict()


def assemble(df: pd.DataFrame, subs: pd.DataFrame):
    """Add substation attributes and derived columns; returns model-ready frame."""
    s = subs.set_index("substation_id")[["voltage_kv", "existing_capacity_mw"]]
    df = df.join(s, on="substation_id", rsuffix="_sub") if "voltage_kv" not in df else df
    out = pd.DataFrame(index=df.index)
    out["iso_region"] = df.iso_region.astype(REGION_DTYPE)
    out["technology_type"] = df.technology_type.astype(TECH_DTYPE)
    out["log_mw"] = np.log(df.proposed_capacity_mw.astype(float))
    out["queue_year"] = df.queue_year.astype(float)
    out["voltage_kv"] = df.voltage_kv.astype(float)
    out["poi_queue_mw"] = df.poi_queue_mw.astype(float)
    poi_ratio = (df.poi_queue_mw + df.proposed_capacity_mw) / df.existing_capacity_mw.astype(float)
    region_ratio = df.region_queue_gw.astype(float) * 1000 / df.iso_region.astype(str).map(region_capacity(subs)).astype(float)
    # Clipped to the range seen in training so extremes are not over-read.
    out["poi_crowding"] = (poi_ratio / np.maximum(region_ratio, 0.05)).clip(0.1, 20)
    out["poi_hist_lift"] = (df.poi_hist_rate.astype(float) / df.region_rate_t.astype(float)).clip(0.25, 3)
    out["is_hybrid"] = df.is_hybrid.astype(float)
    if "phase" in df:
        out["phase"] = df.phase.astype(float)
        out["upgrade_cost_per_kw"] = df.upgrade_cost_per_kw.astype(float)
    return out


def training_frames(projects: pd.DataFrame, subs: pd.DataFrame, cohort_end: int):
    """Build the three training sets.

    completion: one row per (project, phase reached) for resolved projects in
                the training cohort; target = reached operation.
    timeline:   same snapshots for built projects; target = months from the
                start of that phase to operation.
    cost:       one row per project with a study cost estimate; target = $/kW.
    """
    p = projects.reset_index(drop=True).copy()
    p["queue_year"] = [d.year for d in p.queue_date]
    p = pd.concat([p, entry_context(p, subs)], axis=1)

    snaps = []
    for k, col in enumerate(PHASE_DATE_COLS):
        has = p[col].notna()
        if not has.any():
            continue
        s = p[has].copy()
        s["phase"] = k
        s["phase_start"] = s[col]
        if k == 0:
            s["upgrade_cost_per_kw"] = np.nan  # not known before the first study
        else:
            # Hide the estimate on some later-phase rows so the model also
            # learns to score users who have not shared (or do not have) one.
            hide = np.random.default_rng(k).random(len(s)) < COST_MASK_RATE
            s.loc[hide, "upgrade_cost_per_kw"] = np.nan
        snaps.append(s)
    snaps = pd.concat(snaps, ignore_index=True)

    resolved = snaps.status.isin(["operational", "withdrawn"]) & (snaps.queue_year <= cohort_end)
    comp = snaps[resolved]
    built = snaps[snaps.status == "operational"].copy()
    built["months"] = (_ordinal(built.cod_date) - _ordinal(built.phase_start)) / 30.44
    built = built[built.months > 0]

    costed = p[p.upgrade_cost_per_kw.notna() & (p.upgrade_cost_per_kw > 0)]

    return {
        "completion": (assemble(comp, subs)[CAT_FEATURES + STATUS_FEATURES],
                       (comp.status == "operational").astype(int).to_numpy(),
                       comp.project_id.to_numpy(), comp.queue_year.to_numpy()),
        "timeline": (assemble(built, subs)[CAT_FEATURES + STATUS_FEATURES],
                     np.log(built.months.to_numpy()),
                     built.project_id.to_numpy(), built.queue_year.to_numpy()),
        "cost": (assemble(costed, subs)[CAT_FEATURES + SITE_FEATURES],
                 np.log(costed.upgrade_cost_per_kw.to_numpy(float)),
                 costed.project_id.to_numpy(), costed.queue_year.to_numpy()),
    }


def phase_label(k):
    return PHASES[int(k)] if 0 <= int(k) < len(PHASES) else "Operational"
