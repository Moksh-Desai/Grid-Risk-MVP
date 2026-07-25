from pydantic import BaseModel


class ProjectAssessmentRequest(BaseModel):
    region: str
    technology: str
    capacity_mw: float


class AssessmentResponse(BaseModel):
    risk_score: float
    risk_level: str