from fastapi import APIRouter

router = APIRouter()


@router.get("/substations/{region}")
def get_substations(region: str):

    return {
        "region": region
    }