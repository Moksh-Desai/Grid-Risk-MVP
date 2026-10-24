from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.data.regions import REGIONS, TECHNOLOGIES


class ProjectInput(BaseModel):
    region: str
    technology: str
    capacity_mw: float = Field(gt=0, le=5000)
    substation_id: Optional[str] = None
    phase: int = Field(0, ge=0, le=4, description="Current study phase (0 = just entering)")
    upgrade_cost_per_kw: Optional[float] = Field(
        None, ge=0, le=5000, description="Network upgrade estimate from a study, if you have one")
    queue_year: Optional[int] = Field(None, ge=2000, le=2035)
    name: Optional[str] = None

    @field_validator("region")
    @classmethod
    def _region(cls, v):
        if v not in REGIONS:
            raise ValueError(f"region must be one of {list(REGIONS)}")
        return v

    @field_validator("technology")
    @classmethod
    def _tech(cls, v):
        v = v.lower()
        if v not in TECHNOLOGIES:
            raise ValueError(f"technology must be one of {TECHNOLOGIES}")
        return v


class AssessRequest(ProjectInput):
    at_risk_per_kw: float = Field(
        25.0, ge=0, le=1000,
        description="Pre-construction spend ($/kW) lost if the project withdraws: "
                    "deposits, studies, land options, development costs")
    reform_adjustment: bool = Field(
        False, description="Apply the Order 2023 reform assumption (see /api/model)")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class PortfolioRequest(BaseModel):
    projects: list[ProjectInput] = Field(min_length=1, max_length=500)
    reform_adjustment: bool = False


# Original MVP endpoint, kept for compatibility.
class ProjectAssessmentRequest(BaseModel):
    region: str
    technology: str
    capacity_mw: float


class AssessmentResponse(BaseModel):
    risk_score: float
    risk_level: str
