import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.alternatives import router as alternatives_router
from app.api.assess import router as assess_router
from app.api.market import router as market_router
from app.api.model import router as model_router
from app.api.substations import router as substations_router
from app.config import ALLOWED_ORIGINS, FRONTEND_DIST
from app.database import init_db
from app.ml import predictor

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seeds data and trains models on first run without blocking startup.
    predictor.start_background_load()
    yield


app = FastAPI(
    title="Grid Risk MVP",
    description="Interconnection queue risk: completion odds, timeline and upgrade cost, "
                "with site alternatives and portfolio screening.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error processing request %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


for router in (assess_router, alternatives_router, substations_router, market_router, model_router):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"product": "Grid Risk MVP", **predictor.status()}


# Serve the built frontend (npm run build) from the same origin when present.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"product": "Grid Risk MVP", "status": "running",
                "hint": "Build the frontend (cd frontend && npm run build) or open the Vite dev server."}
