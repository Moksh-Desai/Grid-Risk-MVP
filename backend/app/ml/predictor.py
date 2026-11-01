"""Load trained models and score new projects against today's queue."""

import logging
import threading

import joblib
import numpy as np
import pandas as pd

from app.config import DATA_CUTOFF, MODEL_PATH
from app.data.regions import REGIONS
from app.config import TRAIN_COHORT_END
from app.ml.features import PRIOR_WEIGHT, QueueState, assemble, load_frames, smoothed_rate
from app.ml.train import data_fingerprint, predict_quantiles, train_and_save

log = logging.getLogger(__name__)

# Order No. 2023 reforms (readiness deposits, site control, withdrawal
# penalties) are meant to screen out speculative requests. No reformed
# cohort has finished yet, so this is an assumption, not a learned effect:
# +0.35 log-odds is roughly a 5-point lift at a 20% base rate. Off by default.
REFORM_LOGIT_SHIFT = 0.35


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


class Predictor:
    def __init__(self, bundle, projects, subs):
        self.bundle = bundle
        self.projects = projects
        self.subs = subs.set_index("substation_id")
        self._build_context()
        self._reference_scores()

    # ---- queue context as of the data cutoff -------------------------------
    def _build_context(self):
        state = QueueState(self.projects)
        t = np.array([float(DATA_CUTOFF.toordinal())])
        self.region_ctx = {}
        p = self.projects
        cohort = p[[d.year <= TRAIN_COHORT_END for d in p.queue_date]]
        for region in REGIONS:
            active, n_res, n_done = state.region(region, t)
            c = cohort[cohort.iso_region == region]
            self.region_ctx[region] = {
                "queue_gw": float(active[0] / 1000),
                # Same definition the models saw at training time.
                "rate": float(smoothed_rate(n_done, n_res)[0]),
                # Share of the historical cohort that got built (for display).
                "cohort_rate": float((c.status == "operational").mean()) if len(c) else None,
            }
        rows = []
        for sid, sub in self.subs.iterrows():
            active, n_res, n_done = state.poi(sid, t)
            prior = self.region_ctx.get(sub.iso_region, {"rate": 0.2})["rate"]
            rows.append({
                "substation_id": sid,
                "poi_queue_mw": float(active[0]),
                "poi_hist_n": float(n_res[0]),
                "poi_hist_completed": float(n_done[0]),
                "poi_hist_rate": float((n_done[0] + PRIOR_WEIGHT * prior) / (n_res[0] + PRIOR_WEIGHT)),
            })
        self.poi_ctx = pd.DataFrame(rows).set_index("substation_id")
        self.subs_ctx = self.subs.join(self.poi_ctx)

    def typical_site(self, region):
        s = self.subs_ctx[self.subs_ctx.iso_region == region]
        if s.empty:
            return {"voltage_kv": np.nan, "existing_capacity_mw": np.nan, "poi_queue_mw": 0.0,
                    "poi_hist_n": 0.0, "poi_hist_rate": self.region_ctx.get(region, {}).get("rate", 0.2)}
        return {
            "voltage_kv": float(s.voltage_kv.median()) if s.voltage_kv.notna().any() else np.nan,
            "existing_capacity_mw": float(s.existing_capacity_mw.median())
            if s.existing_capacity_mw.notna().any() else np.nan,
            "poi_queue_mw": float(s.poi_queue_mw.median()),
            "poi_hist_n": float(s.poi_hist_n.median()),
            "poi_hist_rate": self.region_ctx[region]["rate"],
        }

    # ---- feature rows -------------------------------------------------------
    def rows(self, items):
        """items: dicts with region, technology, capacity_mw and optional
        substation_id, phase, upgrade_cost_per_kw, queue_year."""
        out = []
        for it in items:
            region = it["region"]
            sid = it.get("substation_id")
            if sid and sid in self.subs_ctx.index:
                site = self.subs_ctx.loc[sid].to_dict()
            else:
                site, sid = self.typical_site(region), None
            out.append({
                "iso_region": region,
                "technology_type": it["technology"],
                "proposed_capacity_mw": float(it["capacity_mw"]),
                "queue_year": int(it.get("queue_year") or DATA_CUTOFF.year + 1),
                "substation_id": sid,
                "voltage_kv": site.get("voltage_kv"),
                "existing_capacity_mw": site.get("existing_capacity_mw"),
                "poi_queue_mw": site.get("poi_queue_mw", 0.0),
                "poi_hist_rate": site.get("poi_hist_rate"),
                "poi_hist_n": site.get("poi_hist_n", 0.0),
                "region_queue_gw": self.region_ctx.get(region, {}).get("queue_gw", 0.0),
                "region_rate_t": self.region_ctx.get(region, {}).get("rate", 0.2),
                "is_hybrid": it["technology"] == "hybrid",
                "phase": int(it.get("phase") or 0),
                "upgrade_cost_per_kw": it.get("upgrade_cost_per_kw"),
            })
        df = pd.DataFrame(out)
        df["upgrade_cost_per_kw"] = pd.to_numeric(df.upgrade_cost_per_kw, errors="coerce")
        return df

    def _features(self, df, name):
        X = assemble(df, self.subs.reset_index())
        return X[self.bundle[f"{name}_columns"]]

    # ---- predictions ---------------------------------------------------------
    def predict_frame(self, df, reform=False):
        p = self.bundle["completion"].predict_proba(self._features(df, "completion"))[:, 1]
        if reform:
            p = _sigmoid(_logit(p) + REFORM_LOGIT_SHIFT)
        res = pd.DataFrame({"p_complete": p}, index=df.index)
        for name in ("timeline", "cost"):
            if self.bundle.get(name) is None:
                for i, q in enumerate(("p10", "p50", "p90")):
                    res[f"{name}_{q}"] = np.nan
                continue
            q = predict_quantiles(self.bundle[name], self._features(df, name),
                                  self.bundle.get(f"{name}_widening", 0.0))
            for i, lab in enumerate(("p10", "p50", "p90")):
                res[f"{name}_{lab}"] = q[:, i]
        return res

    def predict(self, items, reform=False):
        return self.predict_frame(self.rows(items), reform)

    def _reference_scores(self):
        """Predicted completion odds for every project in the queue today."""
        active = self.projects[self.projects.status == "active"]
        if active.empty:
            self.reference = np.array([0.2])
            return
        df = pd.DataFrame({
            "iso_region": active.iso_region.values,
            "technology_type": active.technology_type.values,
            "proposed_capacity_mw": active.proposed_capacity_mw.values,
            "queue_year": [d.year for d in active.queue_date],
            "substation_id": active.substation_id.values,
            "is_hybrid": active.technology_type.eq("hybrid").values,
            "phase": active.max_phase.values,
            "upgrade_cost_per_kw": active.upgrade_cost_per_kw.values,
        })
        ctx = self.subs_ctx.reindex(df.substation_id)
        df["voltage_kv"] = ctx.voltage_kv.values
        df["existing_capacity_mw"] = ctx.existing_capacity_mw.values
        # Exclude each project's own MW from "already queued at the POI".
        df["poi_queue_mw"] = np.maximum(ctx.poi_queue_mw.fillna(0).values - df.proposed_capacity_mw, 0)
        df["poi_hist_rate"] = ctx.poi_hist_rate.values
        df["poi_hist_n"] = ctx.poi_hist_n.fillna(0).values
        df["region_queue_gw"] = df.iso_region.map(lambda r: self.region_ctx.get(r, {}).get("queue_gw", 0))
        df["region_rate_t"] = df.iso_region.map(lambda r: self.region_ctx.get(r, {}).get("rate", 0.2))
        p = self.predict_frame(df).p_complete.to_numpy()
        self.reference = np.sort(p)
        self.active_scored = df.assign(p_complete=p, project_id=active.project_id.values)

    def percentile(self, p):
        return float(np.searchsorted(self.reference, p, side="right") / len(self.reference) * 100)


# ---- singleton with background training -------------------------------------
_lock = threading.Lock()
_state = {"predictor": None, "status": "not_loaded", "error": None}


def _load(force_retrain=False):
    from app.data.seed import ensure_seeded

    try:
        _state["status"] = "loading"
        ensure_seeded()
        projects, subs = load_frames()
        bundle = None
        if MODEL_PATH.exists() and not force_retrain:
            try:
                bundle = joblib.load(MODEL_PATH)
                if bundle.get("fingerprint") != data_fingerprint(projects):
                    log.info("Data changed since last training; retraining.")
                    bundle = None
            except Exception:  # stale or incompatible pickle
                log.exception("Could not load saved models; retraining.")
                bundle = None
        if bundle is None:
            _state["status"] = "training"
            bundle = train_and_save(verbose=False)
        _state["predictor"] = Predictor(bundle, projects, subs)
        _state["status"] = "ready"
        _state["error"] = None
    except Exception as exc:
        log.exception("Model load failed")
        _state["status"] = "error"
        _state["error"] = str(exc)


def start_background_load(force_retrain=False):
    with _lock:
        if _state["status"] in ("loading", "training"):
            return
        _state["status"] = "loading"
    threading.Thread(target=_load, args=(force_retrain,), daemon=True).start()


def load_now():
    _load()
    return _state["predictor"]


def get_predictor():
    return _state["predictor"]


def status():
    return {"status": _state["status"], "error": _state["error"]}
