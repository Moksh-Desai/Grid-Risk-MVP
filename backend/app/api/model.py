from fastapi import APIRouter

from app.config import DATA_CUTOFF
from app.data.regions import PHASES, REGIONS, TECHNOLOGIES
from app.ml import predictor as predictor_mod

router = APIRouter()


@router.get("/meta")
def meta():
    return {
        "regions": [{"code": k, "name": v["name"]} for k, v in REGIONS.items()],
        "technologies": TECHNOLOGIES,
        "phases": [{"value": i, "label": p} for i, p in enumerate(PHASES)],
        "data_cutoff": DATA_CUTOFF.isoformat(),
        **predictor_mod.status(),
    }


@router.get("/model")
def model_info():
    st = predictor_mod.status()
    pred = predictor_mod.get_predictor()
    if pred is None:
        return st
    b = pred.bundle
    return {
        **st,
        "trained_at": b["trained_at"],
        "data_sources": b["data_sources"],
        "n_projects": b["n_projects"],
        "training_cohort": f"resolved projects that entered the queue through {b['cohort_end']}",
        "metrics": b["metrics"],
        "models": [
            {"name": "Completion", "type": "Blend: calibrated gradient boosting + logistic regression",
             "predicts": "Probability the project reaches commercial operation, given its current phase"},
            {"name": "Timeline", "type": "Quantile gradient boosting + conformal widening",
             "predicts": "P10 / P50 / P90 months from the current phase to operation"},
            {"name": "Upgrade cost", "type": "Quantile gradient boosting + conformal widening",
             "predicts": "P10 / P50 / P90 network upgrade cost ($/kW) before any study"},
        ],
        "reform_assumption": {
            "logit_shift": predictor_mod.REFORM_LOGIT_SHIFT,
            "why": "FERC Order No. 2023 cluster studies, readiness deposits and withdrawal penalties "
                   "aim to screen out speculative requests. No reformed cohort has finished yet, so "
                   "this lift is an assumption you can toggle, not something the model learned.",
        },
        "limitations": [
            "Trained on synthetic data calibrated to public statistics until real queue data is "
            "loaded (python -m app.data.lbnl <file>)." if b["data_sources"] == ["synthetic"]
            else "Trained on imported queue data.",
            "Statistical screening, not a power-flow study: it cannot see thermal or voltage limits "
            "on specific lines.",
            "Projects still active from the training cohort are left out, which can understate "
            "slow completions.",
            "Queue rules changed in 2023-2025; history is an imperfect guide to reformed processes.",
        ],
    }
