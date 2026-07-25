from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assess import router as assess_router
from app.api.alternatives import router as alternatives_router
from app.api.substations import router as substations_router

app = FastAPI(
    title="Grid Risk MVP",
    description="Interconnection Queue Risk Analysis Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://silver-enigma-p7gjqrx66pj7crpgw-5173.app.github.dev"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    assess_router,
    prefix="/api"
)

app.include_router(
    alternatives_router,
    prefix="/api"
)

app.include_router(
    substations_router,
    prefix="/api"
)


@app.get("/")
def root():
    return {
        "product": "Grid Risk MVP",
        "status": "running"
    }