"""Load data into the database.

    python -m app.data.seed              # synthetic data (default)
    python -m app.data.seed --reset      # wipe and regenerate
"""

import argparse
import os

import pandas as pd
from sqlalchemy import delete, func, select

from app.database import SessionLocal, engine, init_db
from app.models.project import Project
from app.models.substation import Substation

PROJECT_COLS = [c.name for c in Project.__table__.columns]
SUBSTATION_COLS = [c.name for c in Substation.__table__.columns]


def _records(df, cols):
    out = df[[c for c in cols if c in df.columns]].astype(object)
    return out.where(pd.notna(out), None).to_dict("records")


def replace_all(substations: pd.DataFrame, projects: pd.DataFrame):
    init_db()
    with engine.begin() as conn:
        conn.execute(delete(Project))
        conn.execute(delete(Substation))
        conn.execute(Substation.__table__.insert(), _records(substations, SUBSTATION_COLS))
        conn.execute(Project.__table__.insert(), _records(projects, PROJECT_COLS))


def project_count():
    init_db()
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(Project))


def seed_synthetic(seed=42):
    from app.data.synthetic import generate

    n = int(os.getenv("GRIDRISK_SYNTHETIC_N", "30000"))
    subs, projects = generate(seed=seed, n_projects=n)
    replace_all(subs, projects)
    return len(subs), len(projects)


def ensure_seeded():
    if project_count() == 0:
        seed_synthetic()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="replace existing data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if args.reset or project_count() == 0:
        n_subs, n_proj = seed_synthetic(args.seed)
        print(f"Seeded {n_subs} substations and {n_proj} projects (synthetic).")
    else:
        print("Database already has data; pass --reset to regenerate.")
