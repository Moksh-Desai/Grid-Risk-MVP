import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_predictor
from app.data.regions import REGIONS

router = APIRouter()


@router.get("/substations/{region}")
def get_substations(region: str, pred=Depends(require_predictor)):
    if region not in REGIONS:
        raise HTTPException(404, f"Unknown region {region}")
    s = pred.subs_ctx[pred.subs_ctx.iso_region == region].reset_index()
    s = s.sort_values("substation_name")
    cols = ["substation_id", "substation_name", "state", "voltage_kv", "existing_capacity_mw",
            "latitude", "longitude", "poi_queue_mw", "poi_hist_n", "poi_hist_completed"]
    out = s[cols].rename(columns={"poi_queue_mw": "queued_mw", "poi_hist_n": "past_requests",
                                  "poi_hist_completed": "past_built"})
    out = out.astype(object).where(pd.notna(out), None)
    return {"region": region, "substations": out.to_dict("records")}
