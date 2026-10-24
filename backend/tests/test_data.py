import numpy as np
import pandas as pd

from app.data import lbnl
from app.data.regions import REGIONS
from app.data.synthetic import generate


def test_synthetic_matches_public_calibration():
    subs, p = generate(seed=1, n_projects=8000)
    p["queue_year"] = [d.year for d in p.queue_date]
    cohort = p[p.queue_year <= 2019]
    rate = (cohort.status == "operational").mean()
    assert 0.12 < rate < 0.28  # roughly a fifth of requests get built
    # Withdrawn projects carry higher upgrade estimates than built ones.
    costs = p.groupby("status").upgrade_cost_per_kw.median()
    assert costs["withdrawn"] > 2 * costs["operational"]
    # Recent requests are still in the queue.
    assert (p[p.queue_year >= 2024].status == "active").mean() > 0.5
    assert set(p.iso_region) <= set(REGIONS)
    assert subs.substation_id.is_unique


def test_phase_dates_are_ordered():
    _, p = generate(seed=2, n_projects=3000)
    cols = ["queue_date", "sis_date", "facilities_date", "ia_date", "construction_date", "cod_date"]
    for a, b in zip(cols, cols[1:]):
        both = p[a].notna() & p[b].notna()
        assert (p.loc[both, a] <= p.loc[both, b]).all()


def test_lbnl_parser_maps_columns():
    raw = pd.DataFrame({
        "q_id": ["1", "2", "3", "4"],
        "q_status": ["operational", "withdrawn", "active", "suspended"],
        "q_date": ["2012-03-01", "2015-06-01", "2023-01-15", "2021-09-30"],
        "ia_date": ["2014-01-01", None, None, "2024-02-01"],
        "on_date": ["2016-05-01", None, None, None],
        "wd_date": [None, "2017-01-01", None, None],
        "state": ["TX", "PA", "GA", "CA"],
        "region": ["ERCOT", "PJM", "Southeast", "CAISO"],
        "poi_name": ["Big Sub 345kV", "Other Sub", "GA Sub", None],
        "type_clean": ["Solar", "Wind", "Battery", "Solar"],
        "type2": [None, None, None, "Battery"],
        "mw1": [100, 200, 50, 300],
    })
    subs, projects = lbnl.parse(raw)
    assert list(projects.technology_type) == ["solar", "wind", "storage", "hybrid"]
    assert list(projects.status) == ["operational", "withdrawn", "active", "active"]
    assert list(projects.max_phase) == [4, 0, 0, 3]
    assert projects.substation_id.iloc[3] is None
    assert len(subs) == 3
    assert np.isnan(projects.upgrade_cost_per_kw.astype(float)).all()
