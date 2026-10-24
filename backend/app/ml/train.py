"""Train the three models and evaluate them on a held-out time window.

    python -m app.ml.train

1. Completion: P(reach operation) given region, technology, size, POI
   context and current study phase. An equal blend of calibrated gradient
   boosting (non-linear effects, interactions) and logistic regression
   (extrapolates the year-over-year decline that trees cannot).
2. Timeline: quantile gradient boosting (P10/P50/P90) for months from the
   current phase to commercial operation.
3. Upgrade cost: quantile gradient boosting (P10/P50/P90) for network
   upgrade cost in $/kW, from site features alone (before any study).

Evaluation trains on queue years up to TEST_START-1 and tests on later
years, so scores reflect predicting projects the model has never seen.
The saved models are then refit on all data.
"""

import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import MODEL_PATH, TRAIN_COHORT_END
from app.ml.blend import BlendClassifier
from app.ml.features import CAT_FEATURES, load_frames, training_frames

QUANTILES = (0.1, 0.5, 0.9)
MODEL_VERSION = 7
FEATURE_LABELS = {
    "iso_region": "Region", "technology_type": "Technology", "log_mw": "Project size",
    "queue_year": "Queue entry year", "voltage_kv": "POI voltage",
    "poi_crowding": "POI crowding vs region",
    "poi_hist_lift": "POI completion track record",
    "is_hybrid": "Hybrid (with storage)",
    "phase": "Study phase", "upgrade_cost_per_kw": "Upgrade cost estimate",
}


def data_fingerprint(projects):
    key = f"{MODEL_VERSION}|{len(projects)}|{sorted(projects.data_source.unique())}|" \
          f"{projects.proposed_capacity_mw.sum():.1f}|{TRAIN_COHORT_END}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


# Direction each feature is allowed to push a prediction (+1 up, -1 down).
# Keeps the models sensible at the edges of the data, e.g. a later study
# phase can never lower completion odds.
MONOTONIC = {
    "completion": {"phase": 1, "upgrade_cost_per_kw": -1, "poi_crowding": -1, "poi_hist_lift": 1,
                   "queue_year": -1},
    "timeline": {"phase": -1, "poi_crowding": 1, "queue_year": 1},
    "cost": {"poi_crowding": 1},
}


def _monotonic(name, X):
    return {c: v for c, v in MONOTONIC[name].items() if c in X.columns}


def _classifier(groups, X, y):
    base = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=100,
        l2_regularization=2.0, categorical_features="from_dtype",
        monotonic_cst=_monotonic("completion", X), random_state=0)
    # Group folds so snapshots of one project never straddle a fold.
    folds = list(GroupKFold(n_splits=3).split(X, y, groups))
    return CalibratedClassifierCV(base, method="isotonic", cv=folds).fit(X, y)


def _completion_model(groups, X, y):
    return BlendClassifier([_classifier(groups, X, y), _logistic(X, y)])


def _logistic(X, y):
    num = [c for c in X.columns if c not in CAT_FEATURES]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                              StandardScaler()), num),
    ])
    return make_pipeline(pre, LogisticRegression(max_iter=2000)).fit(X, y)


def _quantile_models(X, y, name):
    return {
        q: HistGradientBoostingRegressor(
            loss="quantile", quantile=q, max_iter=200, learning_rate=0.08,
            min_samples_leaf=60, categorical_features="from_dtype",
            monotonic_cst=_monotonic(name, X), random_state=0).fit(X, y)
        for q in QUANTILES
    }


def predict_quantiles(models, X, widen=0.0):
    preds = np.sort(np.column_stack([models[q].predict(X) for q in QUANTILES]), axis=1)
    preds[:, 0] -= widen
    preds[:, 2] += widen
    return np.exp(preds)  # keep P10 <= P50 <= P90


def conformal_widening(models, X, y, target=0.8):
    """How much to widen P10-P90 (in log space) so it covers `target` of
    held-out projects. Queues drift over time, so raw quantile models trained
    on older years tend to be overconfident about newer ones."""
    preds = np.sort(np.column_stack([models[q].predict(X) for q in QUANTILES]), axis=1)
    score = np.maximum(preds[:, 0] - y, y - preds[:, 2])
    return float(max(0.0, np.quantile(score, target)))


def _calibration_table(y, p, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        if m.any():
            rows.append({"predicted": float(p[m].mean()), "observed": float(y[m].mean()),
                         "n": int(m.sum())})
    return rows


def _split(frame, test_start, test_end=None):
    X, y, groups, years = frame
    tr = years < test_start
    te = years >= test_start if test_end is None else (years >= test_start) & (years <= test_end)
    return (X[tr], y[tr], groups[tr]), (X[te], y[te], groups[te])


def evaluate(frames, test_start):
    metrics = {"test_window": f"queue years {test_start}-{TRAIN_COHORT_END}"}

    (Xtr, ytr, gtr), (Xte, yte, _) = _split(frames["completion"], test_start, TRAIN_COHORT_END)
    clf = _completion_model(gtr, Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    gb = clf.models[0].predict_proba(Xte)[:, 1]
    lr = clf.models[1].predict_proba(Xte)[:, 1]
    region_rate = pd.Series(ytr).groupby(Xtr.iso_region.to_numpy()).mean()
    base = Xte.iso_region.map(region_rate).astype(float).fillna(ytr.mean()).to_numpy()
    phase = Xte.phase.to_numpy()
    metrics["completion"] = {
        "n_train": int(len(ytr)), "n_test": int(len(yte)),
        "test_base_rate": float(yte.mean()),
        "auc": float(roc_auc_score(yte, p)),
        "brier": float(brier_score_loss(yte, p)),
        "log_loss": float(log_loss(yte, np.clip(p, 1e-4, 1 - 1e-4))),
        "baselines": {
            "gradient_boosting": {"auc": float(roc_auc_score(yte, gb)),
                                  "brier": float(brier_score_loss(yte, gb))},
            "logistic_regression": {"auc": float(roc_auc_score(yte, lr)),
                                    "brier": float(brier_score_loss(yte, lr))},
            "regional_base_rate": {"auc": float(roc_auc_score(yte, base)),
                                   "brier": float(brier_score_loss(yte, base))},
        },
        "auc_at_entry": float(roc_auc_score(yte[phase == 0], p[phase == 0]))
        if len(set(yte[phase == 0])) > 1 else None,
        "calibration": _calibration_table(yte, p),
    }
    sample = np.random.default_rng(0).choice(len(yte), size=min(2500, len(yte)), replace=False)
    imp = permutation_importance(clf, Xte.iloc[sample], yte[sample], scoring="roc_auc",
                                 n_repeats=2, random_state=0)
    metrics["completion"]["importance"] = sorted(
        [{"feature": c, "label": FEATURE_LABELS.get(c, c), "drop_in_auc": float(v)}
         for c, v in zip(Xte.columns, imp.importances_mean)],
        key=lambda r: -r["drop_in_auc"])

    for name in ("timeline", "cost"):
        (Xtr, ytr, _), (Xte, yte, _) = _split(frames[name], test_start)
        if len(ytr) < 200 or len(yte) < 50:
            metrics[name] = None
            continue
        models = _quantile_models(Xtr, ytr, name)
        # Fit the widening on half the test window, measure coverage on the other half.
        half = np.random.default_rng(1).random(len(yte)) < 0.5
        widen = conformal_widening(models, Xte[half], yte[half])
        raw = predict_quantiles(models, Xte[~half])
        q = predict_quantiles(models, Xte[~half], widen)
        actual = np.exp(yte[~half])
        metrics[name] = {
            "n_train": int(len(ytr)), "n_test": int(len(yte)),
            "median_abs_error": float(np.median(np.abs(q[:, 1] - actual))),
            "p10_p90_coverage_raw": float(np.mean((actual >= raw[:, 0]) & (actual <= raw[:, 2]))),
            "p10_p90_coverage": float(np.mean((actual >= q[:, 0]) & (actual <= q[:, 2]))),
            "widening": conformal_widening(models, Xte, yte),
            "unit": "months" if name == "timeline" else "$/kW",
        }
    return metrics


def train_and_save(path=MODEL_PATH, verbose=True):
    projects, subs = load_frames()
    frames = training_frames(projects, subs, TRAIN_COHORT_END)
    test_start = TRAIN_COHORT_END - 3
    if verbose:
        print(f"Training rows: completion={len(frames['completion'][1])}, "
              f"timeline={len(frames['timeline'][1])}, cost={len(frames['cost'][1])}")
    metrics = evaluate(frames, test_start)

    X, y, groups, _ = frames["completion"]
    bundle = {
        "version": MODEL_VERSION,
        "fingerprint": data_fingerprint(projects),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_sources": sorted(projects.data_source.unique()),
        "n_projects": int(len(projects)),
        "cohort_end": TRAIN_COHORT_END,
        "completion": _completion_model(groups, X, y),
        "completion_columns": list(X.columns),
        "timeline": None, "cost": None,
        "metrics": metrics,
    }
    for name in ("timeline", "cost"):
        Xn, yn, _, _ = frames[name]
        if len(yn) >= 200:
            bundle[name] = _quantile_models(Xn, yn, name)
            bundle[f"{name}_columns"] = list(Xn.columns)
            bundle[f"{name}_widening"] = (metrics[name] or {}).get("widening", 0.0)
    joblib.dump(bundle, path)
    if verbose:
        c = metrics["completion"]
        print(f"Completion AUC {c['auc']:.3f} (boosting {c['baselines']['gradient_boosting']['auc']:.3f}, "
              f"logistic {c['baselines']['logistic_regression']['auc']:.3f}, "
              f"region base rate {c['baselines']['regional_base_rate']['auc']:.3f}); "
              f"Brier {c['brier']:.4f}")
        for name in ("timeline", "cost"):
            if metrics[name]:
                m = metrics[name]
                print(f"{name}: median abs error {m['median_abs_error']:.1f} {m['unit']}, "
                      f"P10-P90 coverage {m['p10_p90_coverage_raw']:.0%} raw -> "
                      f"{m['p10_p90_coverage']:.0%} after conformal widening")
        print(f"Saved {path}")
    return bundle


if __name__ == "__main__":
    from app.data.seed import ensure_seeded

    ensure_seeded()
    b = train_and_save()
    print(json.dumps(b["metrics"]["completion"]["importance"][:6], indent=2))
