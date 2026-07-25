from fastapi import APIRouter

router = APIRouter()


@router.get("/alternatives")
def alternatives():

    return [
        {
            "substation": "PJM_SUB_12",
            "score": 82
        },
        {
            "substation": "PJM_SUB_21",
            "score": 79
        }
    ]