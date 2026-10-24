import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.api.deps import require_predictor
from app.schemas import (AssessmentResponse, AssessRequest, PortfolioRequest, ProjectAssessmentRequest,
                         ProjectInput)
from app.scoring import risk_engine

router = APIRouter()


@router.post("/assess")
def assess(req: AssessRequest, pred=Depends(require_predictor)):
    """Full assessment: completion odds, timeline, upgrade cost, drivers."""
    if req.substation_id and req.substation_id not in pred.subs_ctx.index:
        raise HTTPException(404, f"Unknown substation {req.substation_id}")
    return risk_engine.assess(pred, req)


@router.post("/assess-site", response_model=AssessmentResponse)
def assess_site(project: ProjectAssessmentRequest, pred=Depends(require_predictor)):
    """Original MVP endpoint: a 0-100 score (higher = lower risk) and level."""
    try:
        req = AssessRequest(region=project.region, technology=project.technology,
                            capacity_mw=project.capacity_mw)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))
    out = risk_engine.assess(pred, req)
    return AssessmentResponse(risk_score=out["viability_score"], risk_level=out["risk_level"])


@router.post("/portfolio")
def portfolio(req: PortfolioRequest, pred=Depends(require_predictor)):
    return risk_engine.portfolio(pred, req.projects, req.reform_adjustment)


@router.post("/portfolio/csv")
async def portfolio_csv(file: UploadFile = File(...), reform_adjustment: bool = False,
                        pred=Depends(require_predictor)):
    """CSV columns: name, region, technology, capacity_mw, and optionally
    substation_id, phase, upgrade_cost_per_kw, queue_year."""
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    items, errors = [], []
    for i, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v)
               for k, v in row.items() if k}
        row = {k: v for k, v in row.items() if v not in ("", None)}
        try:
            items.append(ProjectInput(**row))
        except ValidationError as e:
            errors.append({"line": i, "error": "; ".join(
                f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())})
    if not items:
        raise HTTPException(422, {"message": "No valid rows", "errors": errors[:20]})
    if len(items) > 500:
        raise HTTPException(422, "At most 500 projects per upload")
    out = risk_engine.portfolio(pred, items, reform_adjustment)
    out["errors"] = errors[:50]
    return out
