"""Import Berkeley Lab's public "Queued Up" project-level queue data.

Download the data file from https://emp.lbl.gov/queues, then:

    python -m app.data.lbnl path/to/queues.xlsx   # or .csv
    python -m app.ml.train                        # retrain on the real data

The file has one row per interconnection request across all ISOs and many
utilities. It reports queue, interconnection agreement, operation and
withdrawal dates, but not study-phase dates, upgrade costs or substation
coordinates, so those stay empty and the models use what is there. The POI
name is used as the substation key.
"""

import argparse
import hashlib
import re

import pandas as pd

from app.data.regions import normalize_region

# Accept a few spellings of each column across report editions.
COLUMN_ALIASES = {
    "q_id": ["q_id", "queue_id"],
    "q_status": ["q_status", "status"],
    "q_date": ["q_date", "queue_date"],
    "ia_date": ["ia_date"],
    "on_date": ["on_date", "cod_date"],
    "wd_date": ["wd_date", "withdrawn_date"],
    "state": ["state"],
    "region": ["region", "iso"],
    "entity": ["entity", "utility"],
    "poi_name": ["poi_name", "poi"],
    "type": ["type_clean", "type1", "project_type"],
    "type2": ["type2"],
    "mw": ["mw1", "mw", "capacity_mw"],
    "mw2": ["mw2"],
}

TECH_MAP = {
    "solar": "solar", "photovoltaic": "solar", "pv": "solar",
    "wind": "wind", "offshore wind": "wind",
    "battery": "storage", "storage": "storage",
    "gas": "gas", "natural gas": "gas",
}

SOUTHEAST = {"GA", "NC", "SC", "FL", "AL", "TN", "MS", "KY"}


def _pick(df, key):
    for name in COLUMN_ALIASES[key]:
        for col in df.columns:
            if col.strip().lower() == name:
                return df[col]
    return pd.Series([None] * len(df), index=df.index)


def _tech(primary, secondary):
    p = str(primary or "").strip().lower()
    s = str(secondary or "").strip().lower()
    tech = next((v for k, v in TECH_MAP.items() if k in p), None)
    if tech in ("solar", "wind") and ("battery" in s or "storage" in s):
        return "hybrid"
    if "+" in p or "hybrid" in p:
        return "hybrid"
    return tech


def _region(region, state):
    r = normalize_region(region)
    if r:
        return r
    st = str(state or "").strip().upper()
    if st in SOUTHEAST:
        return "Southeast"
    return "West" if st else None


def _poi_id(region, poi):
    key = re.sub(r"\s+", " ", str(poi or "").strip().lower())
    if not key or key == "nan":
        return None
    return f"{region}-L{hashlib.sha1(key.encode()).hexdigest()[:8]}"


def parse(df: pd.DataFrame):
    """Map an LBNL-style dataframe to (substations, projects) frames."""
    raw = pd.DataFrame({k: _pick(df, k) for k in COLUMN_ALIASES})
    for c in ["q_date", "ia_date", "on_date", "wd_date"]:
        raw[c] = pd.to_datetime(raw[c], errors="coerce").dt.date
    raw["mw"] = pd.to_numeric(raw["mw"], errors="coerce")
    raw["region"] = [_region(r, s) for r, s in zip(raw.region, raw.state)]
    raw["tech"] = [_tech(a, b) for a, b in zip(raw.type, raw.type2)]

    status = raw.q_status.astype(str).str.strip().str.lower()
    raw["status"] = status.map(
        {"operational": "operational", "withdrawn": "withdrawn", "active": "active",
         "suspended": "active"})
    raw = raw.dropna(subset=["q_date", "mw", "region", "tech", "status"])
    raw = raw[raw.mw > 0]

    raw["substation_id"] = [_poi_id(r, p) for r, p in zip(raw.region, raw.poi_name)]
    projects = pd.DataFrame({
        "project_id": [f"LBNL-{r}-{q}-{i}" for i, (r, q) in enumerate(zip(raw.region, raw.q_id))],
        "iso_region": raw.region,
        "state": raw.state,
        "substation_id": raw.substation_id,
        "technology_type": raw.tech,
        "is_hybrid": raw.tech == "hybrid",
        "proposed_capacity_mw": raw.mw,
        "queue_date": raw.q_date,
        "ia_date": raw.ia_date,
        "cod_date": raw.on_date.where(raw.status == "operational"),
        "withdrawn_date": raw.wd_date.where(raw.status == "withdrawn"),
        "status": raw.status,
        "max_phase": [4 if s == "operational" else (3 if pd.notna(ia) else 0)
                      for s, ia in zip(raw.status, raw.ia_date)],
        "upgrade_cost_per_kw": None,
        "data_source": "lbnl",
    })

    pois = raw.dropna(subset=["substation_id"]).drop_duplicates("substation_id")
    substations = pd.DataFrame({
        "substation_id": pois.substation_id,
        "substation_name": pois.poi_name.astype(str).str.strip(),
        "iso_region": pois.region,
        "state": pois.state,
        "data_source": "lbnl",
    })
    return substations, projects


def load_file(path):
    if str(path).lower().endswith((".xlsx", ".xls")):
        # The data sheet is the one with a q_status column.
        sheets = pd.read_excel(path, sheet_name=None)
        for _, sheet in sheets.items():
            if any(str(c).strip().lower() == "q_status" for c in sheet.columns):
                return sheet
            # Some editions put a title row above the header.
            header = sheet.iloc[:10].astype(str).apply(lambda r: r.str.lower().eq("q_status").any(), axis=1)
            if header.any():
                row = header.idxmax()
                sheet.columns = sheet.iloc[row]
                return sheet.iloc[row + 1:]
        raise ValueError("No sheet with a q_status column found")
    return pd.read_csv(path)


if __name__ == "__main__":
    from app.data.seed import replace_all

    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    args = ap.parse_args()
    subs, projects = parse(load_file(args.path))
    replace_all(subs, projects)
    print(f"Loaded {len(projects)} projects at {len(subs)} POIs from {args.path}.")
    print("Now retrain: python -m app.ml.train")
