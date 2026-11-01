from fastapi import APIRouter, Depends, Query

from app.api.deps import require_predictor
from app.schemas import AssessRequest
from app.scoring import risk_engine

router = APIRouter()


@router.post("/alternatives")
def alternatives(req: AssessRequest, limit: int = Query(20, ge=1, le=200),
                 pred=Depends(require_predictor)):
    """Rank every substation in the region for this project as a new request."""
    return risk_engine.alternatives(pred, req, limit)
