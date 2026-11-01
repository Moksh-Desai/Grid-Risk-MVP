from fastapi import HTTPException

from app.ml import predictor as predictor_mod


def require_predictor():
    pred = predictor_mod.get_predictor()
    if pred is None:
        st = predictor_mod.status()
        msg = {
            "training": "Models are training (first start takes about a minute). Try again shortly.",
            "loading": "Models are loading. Try again in a few seconds.",
            "error": f"Model load failed: {st['error']}",
        }.get(st["status"], "Models are not loaded yet.")
        raise HTTPException(status_code=503, detail=msg)
    return pred
