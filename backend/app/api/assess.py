from fastapi import APIRouter

from app.schemas import (
    ProjectAssessmentRequest,
    AssessmentResponse
)

from app.scoring.risk_engine import (
    calculate_risk_score
)

router = APIRouter()


@router.post(
    "/assess-site",
    response_model=AssessmentResponse
)
def assess_site(project: ProjectAssessmentRequest):

    score = calculate_risk_score(
        withdrawal_rate=0.80,
        avg_wait_days=1200,
        upgrade_cost=40000000,
        capacity_mw=project.capacity_mw,
        active_projects=35
    )

    level = (
        "Low"
        if score >= 70
        else "Moderate"
        if score >= 40
        else "High"
    )

    return AssessmentResponse(
        risk_score=score,
        risk_level=level
    )