def _assess(client, **kw):
    body = {"region": "PJM", "technology": "solar", "capacity_mw": 150, **kw}
    r = client.post("/api/assess", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_meta_and_health(client):
    meta = client.get("/api/meta").json()
    assert meta["status"] == "ready"
    assert {r["code"] for r in meta["regions"]} >= {"PJM", "ERCOT", "MISO", "SPP"}
    assert len(meta["phases"]) == 5


def test_assessment_shape(client):
    out = _assess(client)
    assert 0 <= out["completion_probability"] <= 1
    assert 0 <= out["viability_score"] <= 100
    assert out["risk_level"] in {"Low", "Moderate", "High"}
    m = out["timeline"]["months"]
    assert m["p10"] <= m["p50"] <= m["p90"]
    c = out["upgrade_cost"]["per_kw"]
    assert c["p10"] <= c["p50"] <= c["p90"]
    assert out["capital_at_risk"]["expected_loss_musd"] <= out["capital_at_risk"]["at_risk_musd"]


def test_later_phase_never_lowers_odds(client):
    sid = client.get("/api/substations/PJM").json()["substations"][0]["substation_id"]
    probs = [_assess(client, substation_id=sid, phase=k)["completion_probability"] for k in range(5)]
    assert probs == sorted(probs)
    assert probs[-1] > probs[0]


def test_higher_cost_estimate_lowers_odds(client):
    cheap = _assess(client, phase=1, upgrade_cost_per_kw=30)["completion_probability"]
    pricey = _assess(client, phase=1, upgrade_cost_per_kw=1500)["completion_probability"]
    assert cheap >= pricey


def test_reform_toggle_raises_odds(client):
    base = _assess(client)["completion_probability"]
    reform = _assess(client, reform_adjustment=True)["completion_probability"]
    assert reform > base


def test_alternatives_ranked(client):
    subs = client.get("/api/substations/MISO").json()["substations"]
    r = client.post("/api/alternatives?limit=10", json={
        "region": "MISO", "technology": "wind", "capacity_mw": 200,
        "substation_id": subs[0]["substation_id"]}).json()
    rows = r["results"]
    assert 1 <= len(rows) <= 11
    fit = [x for x in rows if not x["undersized"]][:10]
    probs = [x["completion_probability"] for x in fit]
    assert probs == sorted(probs, reverse=True)
    assert all(x["distance_miles"] is not None for x in rows)


def test_portfolio_json_and_csv(client):
    r = client.post("/api/portfolio", json={"projects": [
        {"region": "ERCOT", "technology": "storage", "capacity_mw": 100},
        {"region": "CAISO", "technology": "solar", "capacity_mw": 300, "phase": 3},
    ]}).json()
    assert r["summary"]["projects"] == 2
    assert r["summary"]["expected_mw_built"] <= r["summary"]["total_mw"]

    csv = "name,region,technology,capacity_mw,phase\nA,MISO,wind,200,1\nB,Nowhere,solar,10,0\n"
    r = client.post("/api/portfolio/csv", files={"file": ("p.csv", csv, "text/csv")}).json()
    assert r["summary"]["projects"] == 1
    assert r["errors"][0]["line"] == 3


def test_validation_and_legacy(client):
    assert client.post("/api/assess", json={"region": "XX", "technology": "solar",
                                            "capacity_mw": 10}).status_code == 422
    legacy = client.post("/api/assess-site", json={"region": "SPP", "technology": "wind",
                                                   "capacity_mw": 150}).json()
    assert set(legacy) == {"risk_score", "risk_level"}


def test_market_and_model(client):
    m = client.get("/api/market").json()
    assert m["totals"]["active_projects"] > 0
    assert len(m["regions"]) == 9
    info = client.get("/api/model").json()
    assert 0.5 < info["metrics"]["completion"]["auc"] <= 1
    assert info["metrics"]["completion"]["calibration"]
