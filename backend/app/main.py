from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

from app.api.assess import router as assess_router
from app.api.alternatives import router as alternatives_router
from app.api.substations import router as substations_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="Grid Risk MVP",
    description="Interconnection Queue Risk Analysis Platform",
    version="1.0.0"
)

allowed = os.getenv("ALLOWED_ORIGINS")
if allowed:
    origins = [o.strip() for o in allowed.split(",") if o.strip()]
else:
    origins = [
        "https://silver-enigma-p7gjqrx66pj7crpgw-5173.app.github.dev",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error processing request %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

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
    dist_index = "/workspaces/Grid-Risk-MVP/frontend/dist/index.html"
    if os.path.exists(dist_index):
        return FileResponse(dist_index, media_type="text/html")

    return {
        "product": "Grid Risk MVP",
        "status": "running"
    }

# Serve frontend production build when available
app.mount("/", StaticFiles(directory="/workspaces/Grid-Risk-MVP/frontend/dist", html=True), name="frontend")