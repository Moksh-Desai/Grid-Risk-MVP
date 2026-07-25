from fastapi import APIRouter

router = APIRouter()


@router.post("/assess-site")
def assess_site():

    return {
        "risk_score": 65,
        "risk_level": "Moderate"
    }
