import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

# Local state (SQLite db, trained models). Override with GRIDRISK_DATA_DIR.
DATA_DIR = Path(os.getenv("GRIDRISK_DATA_DIR", BACKEND_DIR / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'gridrisk.db'}")
MODEL_PATH = DATA_DIR / "models.joblib"

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", REPO_DIR / "frontend" / "dist"))

# "As of" date for the queue snapshot. Projects whose outcome falls after
# this date are treated as still active.
DATA_CUTOFF = date.fromisoformat(os.getenv("GRIDRISK_DATA_CUTOFF", "2025-12-31"))

# Projects that entered the queue up to this year are old enough that most
# have resolved (built or withdrawn); the completion model trains on them.
# Mirrors the 2000-2019 cohort Berkeley Lab uses for completion rates.
TRAIN_COHORT_END = int(os.getenv("GRIDRISK_TRAIN_COHORT_END", "2019"))

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
