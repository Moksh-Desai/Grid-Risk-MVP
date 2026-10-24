"""Synthetic interconnection queue, calibrated to public queue statistics.

Each project walks through the study phases. At every phase it either
advances or withdraws, with odds driven by region, technology, size, how
crowded its substation is, and its upgrade cost (expensive projects drop
out more, which is what Berkeley Lab's cost data shows). Outcomes after
DATA_CUTOFF are hidden, so recent projects show up as "active", the same
way they do in a real queue snapshot.

The point is to give the ML pipeline realistic structure to learn from
until real data is loaded (see app.data.lbnl). It is not real project data.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.config import DATA_CUTOFF
from app.data.regions import PHASES, REGIONS

TECH_LOGIT = {"gas": 0.55, "wind": 0.0, "solar": -0.10, "storage": -0.45, "hybrid": -0.25}
TECH_MW = {"gas": 250, "wind": 150, "solar": 100, "storage": 100, "hybrid": 150}
TECH_COST = {"gas": 1.10, "wind": 1.20, "solar": 1.00, "storage": 0.80, "hybrid": 1.00}

# Share of new requests by technology, interpolated between these years.
TECH_MIX = {
    2005: {"gas": 0.35, "wind": 0.50, "solar": 0.10, "storage": 0.02, "hybrid": 0.03},
    2015: {"gas": 0.20, "wind": 0.30, "solar": 0.40, "storage": 0.07, "hybrid": 0.03},
    2025: {"gas": 0.10, "wind": 0.06, "solar": 0.38, "storage": 0.32, "hybrid": 0.14},
}

# Base pass rate at each phase (before project-level effects).
PHASE_LOGIT = np.array([-0.2, 0.5, 1.0, 1.7, 2.6])
# Share of total queue time spent in each phase.
PHASE_TIME_SHARE = np.array([0.15, 0.25, 0.15, 0.15, 0.30])

KV_LEVELS = np.array([69, 115, 138, 161, 230, 345, 500, 765])
KV_PROBS = np.array([0.08, 0.16, 0.20, 0.08, 0.20, 0.18, 0.07, 0.03])
KV_CAPACITY = {69: 150, 115: 300, 138: 400, 161: 450, 230: 800, 345: 1500, 500: 2500, 765: 4000}

FIRST_YEAR, LAST_YEAR = 2005, 2025


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _tech_mix(year):
    years = sorted(TECH_MIX)
    lo = max(y for y in years if y <= year) if year >= years[0] else years[0]
    hi = min(y for y in years if y >= year) if year <= years[-1] else years[-1]
    w = 0.0 if hi == lo else (year - lo) / (hi - lo)
    mix = {t: (1 - w) * TECH_MIX[lo][t] + w * TECH_MIX[hi][t] for t in TECH_MIX[lo]}
    total = sum(mix.values())
    return {t: v / total for t, v in mix.items()}


def generate_substations(rng):
    rows = []
    for region, info in REGIONS.items():
        n = max(15, round(info["share"] * 420))
        for i in range(n):
            state, lat, lon = info["states"][rng.integers(len(info["states"]))]
            kv = int(rng.choice(KV_LEVELS, p=KV_PROBS))
            rows.append({
                "substation_id": f"{region}-{i:03d}",
                "substation_name": f"{state} {kv} kV · Sub {i:03d}",
                "iso_region": region,
                "state": state,
                "latitude": round(lat + rng.normal(0, 0.9), 4),
                "longitude": round(lon + rng.normal(0, 1.1), 4),
                "voltage_kv": float(kv),
                "existing_capacity_mw": round(KV_CAPACITY[kv] * rng.lognormal(0, 0.3), 0),
                "data_source": "synthetic",
                # Hidden site quality and popularity; not stored in the db.
                "_quality": rng.normal(0, 0.45),
                "_popularity": rng.gamma(0.8),
            })
    return pd.DataFrame(rows)


def _yearly_counts(n_projects):
    years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
    w = np.exp(0.15 * (years - FIRST_YEAR))
    # Fewer new requests once queue reforms and deposits kicked in.
    w[years == 2024] *= 0.8
    w[years == 2025] *= 0.6
    return dict(zip(years, np.round(w / w.sum() * n_projects).astype(int)))


def generate_projects(subs, rng, n_projects=30000):
    regions = list(REGIONS)
    region_p = np.array([REGIONS[r]["share"] for r in regions])
    region_p = region_p / region_p.sum()
    subs_by_region = {r: subs[subs.iso_region == r].reset_index(drop=True) for r in regions}

    rows = []
    for year, count in _yearly_counts(n_projects).items():
        mix = _tech_mix(year)
        techs = list(mix)
        for _ in range(count):
            region = regions[rng.choice(len(regions), p=region_p)]
            tech = techs[rng.choice(len(techs), p=list(mix.values()))]
            mw = float(np.clip(TECH_MW[tech] * rng.lognormal(0, 0.8), 5, 2000).round(1))
            rs = subs_by_region[region]
            # Larger projects favour substations that can take them.
            fit = np.where(rs.existing_capacity_mw.values > mw * 1.5, 1.0, 0.25)
            w = rs._popularity.values * fit
            sub = rs.iloc[rng.choice(len(rs), p=w / w.sum())]
            qdate = date(year, 1, 1) + timedelta(days=int(rng.integers(0, 365)))
            rows.append({
                "iso_region": region, "technology_type": tech, "proposed_capacity_mw": mw,
                "queue_date": qdate, "queue_year": year,
                "substation_id": sub.substation_id, "state": sub.state,
                "voltage_kv": sub.voltage_kv, "existing_capacity_mw": sub.existing_capacity_mw,
                "_quality": sub._quality,
            })
    df = pd.DataFrame(rows).sort_values("queue_date").reset_index(drop=True)
    df["project_id"] = [f"Q{i:05d}" for i in range(len(df))]
    df["is_hybrid"] = df.technology_type == "hybrid"
    return df


def _congestion(df):
    """MW requested at the same substation in the prior 4 years / its capacity."""
    out = np.zeros(len(df))
    for _, g in df.groupby("substation_id"):
        d = g.queue_date.map(date.toordinal).values
        mw = g.proposed_capacity_mw.values
        for j, idx in enumerate(g.index):
            prior = (d < d[j]) & (d >= d[j] - 4 * 365)
            out[df.index.get_loc(idx)] = mw[prior].sum()
    return out / df.existing_capacity_mw.values


def simulate_outcomes(df, rng):
    n = len(df)
    region_info = df.iso_region.map(REGIONS)
    years = df.queue_year.values
    log_mw = np.log(df.proposed_capacity_mw.values / 100)
    cong = np.clip(_congestion(df), 0, 6)
    quality = df._quality.values

    # Upgrade cost estimate ($/kW), as a study would report it.
    mid = 0.45 * region_info.map(lambda r: r["cost_complete"] ** 0.4 * r["cost_withdrawn"] ** 0.6).values
    log_cost = (
        np.log(mid)
        + np.log(df.technology_type.map(TECH_COST).values)
        + 0.30 * cong
        - 0.15 * np.log(df.voltage_kv.values / 230)
        - 0.10 * log_mw
        + 0.04 * (years - 2015)
        - 0.50 * quality
        + rng.normal(0, 0.85, n)
    )
    cost = np.exp(log_cost)

    # Site and project traits act at every phase, but softly: they compound
    # across five phases. The upgrade cost only bites from the system impact
    # study on, once the study has revealed it; that is when most real
    # withdrawals happen.
    z_site = 0.5 * (
        df.technology_type.map(TECH_LOGIT).values
        - 0.25 * log_mw
        - 0.03 * (years - 2012)
        - 0.30 * cong
        + 0.50 * quality
    ) + rng.normal(0, 0.3, n)
    z_cost = -0.6 * (log_cost - np.log(mid))
    cost_known = (np.arange(len(PHASES)) >= 1).astype(float)

    def stage_logits(idx, c):
        return (PHASE_LOGIT[None, :] + c + z_site[idx, None]
                + z_cost[idx, None] * cost_known[None, :])

    # Per-region offset so the 2005-2019 cohort matches its completion target.
    offset = np.zeros(n)
    cohort = years <= 2019
    for region, info in REGIONS.items():
        m = (df.iso_region.values == region)
        lo, hi = -6.0, 6.0
        for _ in range(40):
            c = (lo + hi) / 2
            p = np.prod(_sigmoid(stage_logits(m & cohort, c)), axis=1)
            lo, hi = (c, hi) if p.mean() < info["completion_rate"] else (lo, c)
        offset[m] = (lo + hi) / 2

    pass_p = _sigmoid(stage_logits(np.ones(n, bool), 0.0) + offset[:, None])
    true_p = np.prod(pass_p, axis=1)  # kept for model checks, not stored
    passed = rng.random((n, len(PHASES))) < pass_p
    # Phase where the project stops (len(PHASES) = reaches operation).
    stop = np.where(passed.all(axis=1), len(PHASES), np.argmin(passed, axis=1))

    # Phase durations in months; queues got slower every year.
    median_total = region_info.map(lambda r: r["median_months"]).values
    slow = 0.72 * np.exp(0.045 * (years - 2016)) * (1 + 0.25 * np.minimum(cong, 3))
    med = PHASE_TIME_SHARE[None, :] * (median_total * slow)[:, None]
    dur = med * rng.lognormal(0, 0.45, (n, len(PHASES)))
    start = np.concatenate([np.zeros((n, 1)), np.cumsum(dur, axis=1)], axis=1)

    q_ord = df.queue_date.map(date.toordinal).values
    cutoff = DATA_CUTOFF.toordinal()

    def to_date(months):
        return [date.fromordinal(int(q + m * 30.44)) for q, m in zip(q_ord, months)]

    phase_dates = {k: to_date(start[:, k]) for k in range(1, len(PHASES) + 1)}
    wd_months = start[np.arange(n), np.minimum(stop, len(PHASES) - 1)] + rng.uniform(0.2, 1.0, n) * dur[
        np.arange(n), np.minimum(stop, len(PHASES) - 1)]
    wd_dates = to_date(wd_months)

    status, max_phase, cols = [], [], {c: [] for c in
                                        ["sis_date", "facilities_date", "ia_date", "construction_date",
                                         "cod_date", "withdrawn_date"]}
    names = ["sis_date", "facilities_date", "ia_date", "construction_date", "cod_date"]
    for i in range(n):
        reached = 0
        for k, name in enumerate(names, start=1):
            d = phase_dates[k][i]
            ok = stop[i] >= k and d.toordinal() <= cutoff
            cols[name].append(d if ok else None)
            if ok and k < len(PHASES):
                reached = k
        wd = wd_dates[i] if stop[i] < len(PHASES) and wd_dates[i].toordinal() <= cutoff else None
        cols["withdrawn_date"].append(wd)
        if cols["cod_date"][i] is not None:
            status.append("operational")
            reached = len(PHASES) - 1
        elif wd is not None:
            status.append("withdrawn")
        else:
            status.append("active")
        max_phase.append(reached)

    df = df.assign(**cols, status=status, max_phase=max_phase)
    # Cost estimates exist only once a system impact study has been done.
    df["upgrade_cost_per_kw"] = np.where(df.sis_date.notna(), cost.round(1), np.nan)
    df["data_source"] = "synthetic"
    df["_true_p"] = true_p
    return df


def generate(seed=42, n_projects=30000):
    rng = np.random.default_rng(seed)
    subs = generate_substations(rng)
    projects = simulate_outcomes(generate_projects(subs, rng, n_projects), rng)
    return subs.drop(columns=["_quality", "_popularity"]), projects
