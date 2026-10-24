"""Reference numbers for each grid region, used to calibrate synthetic data.

The values are rounded approximations of public figures, mainly Berkeley
Lab's "Queued Up" reports (emp.lbl.gov/queues) and its interconnection cost
briefs for PJM, MISO and SPP (emp.lbl.gov/interconnection_costs):

- About 13% of capacity (roughly a fifth of projects) that requested
  interconnection in 2000-2019 reached commercial operation by end of 2024.
- Median request-to-operation time rose from under 2 years (built 2000-2007)
  to over 4 years (built 2018-2024).
- Withdrawn projects carried far higher upgrade cost estimates than completed
  ones (SPP ~$57/kW complete vs ~$304/kW withdrawn; MISO ~$102 vs ~$452).

Where no region-specific figure was found, values are estimates in line with
the national numbers. Replace them with real data via app.data.lbnl.
"""

# Study phases, in order. Index = phase number used everywhere.
PHASES = [
    "Feasibility / cluster entry",
    "System impact study",
    "Facilities study",
    "Interconnection agreement",
    "Construction",
]

TECHNOLOGIES = ["solar", "wind", "storage", "hybrid", "gas"]

REGIONS = {
    "PJM": {
        "name": "PJM (Mid-Atlantic / Ohio Valley)",
        "completion_rate": 0.20,
        "median_months": 62,
        "cost_complete": 80,
        "cost_withdrawn": 520,
        "share": 0.22,
        "states": [("PA", 40.9, -77.8), ("OH", 40.3, -82.8), ("VA", 37.5, -78.8),
                   ("NJ", 40.1, -74.6), ("MD", 39.0, -76.8), ("IL", 41.2, -88.9),
                   ("IN", 40.6, -86.2), ("WV", 38.6, -80.6)],
    },
    "MISO": {
        "name": "MISO (Midwest / South)",
        "completion_rate": 0.22,
        "median_months": 56,
        "cost_complete": 102,
        "cost_withdrawn": 452,
        "share": 0.17,
        "states": [("MN", 45.9, -94.3), ("IA", 42.0, -93.5), ("IL", 39.8, -89.4),
                   ("IN", 39.2, -86.8), ("MI", 43.3, -84.6), ("WI", 44.6, -89.8),
                   ("MO", 38.5, -92.5), ("LA", 31.0, -92.0), ("AR", 34.9, -92.4)],
    },
    "SPP": {
        "name": "SPP (Great Plains)",
        "completion_rate": 0.17,
        "median_months": 54,
        "cost_complete": 57,
        "cost_withdrawn": 304,
        "share": 0.09,
        "states": [("KS", 38.5, -98.4), ("OK", 35.6, -97.5), ("NE", 41.5, -99.8),
                   ("SD", 44.4, -100.2), ("ND", 47.5, -100.5), ("NM", 34.4, -103.6)],
    },
    "ERCOT": {
        "name": "ERCOT (Texas)",
        "completion_rate": 0.32,
        "median_months": 38,
        "cost_complete": 30,
        "cost_withdrawn": 90,
        "share": 0.14,
        "states": [("TX", 31.0, -99.0), ("TX", 32.8, -97.0), ("TX", 29.8, -95.6),
                   ("TX", 31.9, -102.3), ("TX", 27.8, -97.9)],
    },
    "CAISO": {
        "name": "CAISO (California)",
        "completion_rate": 0.12,
        "median_months": 66,
        "cost_complete": 110,
        "cost_withdrawn": 330,
        "share": 0.12,
        "states": [("CA", 35.3, -119.0), ("CA", 34.6, -116.8), ("CA", 37.8, -121.0),
                   ("CA", 39.5, -121.6)],
    },
    "NYISO": {
        "name": "NYISO (New York)",
        "completion_rate": 0.15,
        "median_months": 64,
        "cost_complete": 120,
        "cost_withdrawn": 400,
        "share": 0.04,
        "states": [("NY", 42.9, -76.0), ("NY", 42.7, -74.0), ("NY", 40.8, -73.2)],
    },
    "ISO-NE": {
        "name": "ISO-NE (New England)",
        "completion_rate": 0.17,
        "median_months": 58,
        "cost_complete": 110,
        "cost_withdrawn": 380,
        "share": 0.03,
        "states": [("MA", 42.3, -71.8), ("ME", 45.0, -69.2), ("CT", 41.6, -72.7),
                   ("NH", 43.6, -71.6), ("VT", 44.0, -72.7)],
    },
    "West": {
        "name": "West (non-ISO utilities)",
        "completion_rate": 0.18,
        "median_months": 52,
        "cost_complete": 70,
        "cost_withdrawn": 250,
        "share": 0.12,
        "states": [("AZ", 33.7, -111.9), ("NV", 38.5, -117.0), ("UT", 39.3, -111.7),
                   ("CO", 39.0, -105.5), ("WY", 43.0, -107.5), ("OR", 44.0, -120.5),
                   ("WA", 47.4, -120.5), ("ID", 43.6, -114.6)],
    },
    "Southeast": {
        "name": "Southeast (non-ISO utilities)",
        "completion_rate": 0.26,
        "median_months": 48,
        "cost_complete": 60,
        "cost_withdrawn": 220,
        "share": 0.07,
        "states": [("GA", 32.7, -83.4), ("NC", 35.6, -79.4), ("SC", 33.9, -80.9),
                   ("FL", 28.6, -82.4), ("AL", 32.8, -86.8), ("TN", 35.8, -86.4)],
    },
}

# Common aliases seen in public queue files.
REGION_ALIASES = {
    "pjm": "PJM", "miso": "MISO", "spp": "SPP", "ercot": "ERCOT",
    "caiso": "CAISO", "nyiso": "NYISO", "iso-ne": "ISO-NE", "isone": "ISO-NE",
    "iso ne": "ISO-NE", "west": "West", "southeast": "Southeast",
}


def normalize_region(value):
    if value is None:
        return None
    v = str(value).strip()
    return REGION_ALIASES.get(v.lower(), v if v in REGIONS else None)
