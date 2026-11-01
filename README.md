# Grid Risk MVP

Screening for grid interconnection risk. Describe a solar, wind, storage, hybrid or gas project
and get:

- **Completion odds:** the calibrated probability it reaches commercial operation, given where it is in the study process.
- **Timeline:** P10/P50/P90 months to operation, with likely in-service dates.
- **Network upgrade cost:** a P10/P50/P90 $/kW range before any study has been run.
- **Risk drivers:** which factors raise or lower the odds, compared with a typical request in the same region.
- **Better sites:** every substation in the region ranked for this project.
- **Portfolio screening:** a CSV of projects in, MW weighted by odds out.
- **Market view and model card:** queue statistics, model accuracy against baselines, calibration, and limitations.

## Why this exists: the industry and its gaps

Before a power plant connects to the U.S. grid, it waits in an interconnection queue run by a grid
operator (PJM, MISO, SPP, ERCOT, CAISO, NYISO, ISO-NE) or a utility. The operator runs a series of
studies: feasibility, system impact, then facilities. Those studies decide which grid upgrades the
project must pay for.

The process has become the main bottleneck for new generation:

- **Most projects never get built.** About 13% of capacity that requested interconnection from 2000 to
  2019 was operating by the end of 2024, and 77% withdrew ([Berkeley Lab, Queued Up 2025](https://emp.lbl.gov/publications/queued-2025-edition-characteristics)).
- **Waits keep getting longer.** The median time from request to operation doubled, from under 2 years
  (built 2000–2007) to over 4 years (built 2018–2024).
- **The queue is huge.** At the end of 2025 about 8,200 projects were active: roughly 1,312 GW of
  generation and 749 GW of storage ([Queued Up 2026](https://emp.lbl.gov/queued-2026-edition-characteristics-power-plants-seeking-transmission-interconnection-end-2025)).
- **Upgrade costs predict who drops out.** In SPP, withdrawn projects faced about $304/kW against
  about $57/kW for completed ones ([LBNL](https://emp.lbl.gov/news/spp-data-show-rising-network-upgrade)).
  In MISO the figures were about $452/kW against $102/kW ([LBNL via Renewable Energy World](https://www.renewableenergyworld.com/power-grid/transmission/miso-interconnection-costs-are-rising-fast-berkeley-lab-says/)).
- **The rules are changing.** FERC Order No. 2023 moved operators to cluster studies, readiness deposits
  and withdrawal penalties. PJM's queue fell from about 424 GW in 2023 to 31 GW in mid-2026 as it worked
  through its transition, then reopened.

Existing tools cluster at two ends:

- **Raw queue data aggregators.** These show what is in the queue but not what will get built.
- **Power-flow study replicas.** Pearl Street's SUGAR and Interconnect (part of Enverus) and Nira Energy
  model the grid itself. They are accurate, but expensive and slow, and aimed at large developers and
  grid operators.

That leaves these gaps, and this is how the MVP addresses each one:

| Gap | What Grid Risk does |
| --- | --- |
| Queue position ≠ megawatts. Developers and investors overestimate pipelines | Calibrated **P(reach operation)** per project, plus **expected MW** for a whole portfolio |
| Point estimates hide risk. A single "4 years" or "$100/kW" says nothing about the tails | **P10/P50/P90** ranges, with conformal widening so the 80% range actually covers about 80% |
| Risk scores are black boxes | **Driver breakdown:** each factor is swapped for the regional typical value and the project re-scored |
| Siting comes before studies, but studies are what reveal cost | **Site ranking:** every substation in the region scored as a new request, plotted as odds vs cost |
| Information arrives over time | Inputs for **study phase** and **your own study cost estimate** update the odds |
| Queue reforms make history an imperfect guide | An explicit, **toggleable reform assumption**, kept separate from the learned model |
| Small developers can't pay for power-flow studies just to screen | A fast statistical screen that runs **before** you pay for studies |

## Machine learning

All code is in `backend/app/ml/`.

| Model | Method | Target |
| --- | --- | --- |
| Completion | Equal blend of gradient boosting (isotonic-calibrated, monotonic constraints) and logistic regression | Reaches operation, given current phase |
| Timeline | Quantile gradient boosting (P10/P50/P90) + conformal widening | Months from current phase to operation |
| Upgrade cost | Quantile gradient boosting (P10/P50/P90) + conformal widening | Network upgrade $/kW, from site features alone |

The design choices that matter:

- **Point-in-time features.** Every feature is computed as of the project's queue date, using only
  earlier events, so there is no leakage from the future.
- **Phase snapshots.** Each project contributes one training row per study phase it reached. That is
  why the odds rise as a project advances.
- **Ratios, not raw counts.** Queue context is expressed as POI crowding relative to the region and
  the POI's completion rate relative to the region. Raw counts grow with the calendar and extrapolate
  badly to today's much larger queue.
- **Blend.** Trees capture interactions; logistic regression extrapolates the year-over-year decline
  that trees cannot. The blend beats either model alone on held-out years.
- **Honest evaluation.** Training uses queue years up to 2015 and testing uses 2016–2019. The model card
  reports AUC, Brier score, a calibration table, permutation importance and baselines (regional average,
  boosting alone, logistic alone).

### Data

Out of the box, the app generates a **synthetic queue** (`app/data/synthetic.py`), about 30k projects
from 2005 to 2025 across 9 regions. It is calibrated to the public figures above: completion by
region, rising wait times, and higher upgrade costs for projects that withdraw. Projects walk through
the study phases, and upgrade costs drive withdrawal once a study reveals them. The app labels every
result as synthetic.

**To use real data**, download Berkeley Lab's project-level queue file from
[emp.lbl.gov/queues](https://emp.lbl.gov/queues), then:

```bash
cd backend
../.venv/bin/python -m app.data.lbnl path/to/queues.xlsx
../.venv/bin/python -m app.ml.train
```

The importer maps statuses, dates, technologies and regions, and uses POI names as substations. The
LBNL file has no upgrade costs or substation coordinates, so the cost model and distances are skipped
when those are missing. Everything else retrains on real outcomes.

## Run locally

Requirements: Python 3.11+ and Node 20.19+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000
```

On first start the backend seeds the database (SQLite in `backend/var/`) and trains the models in
the background. That takes about a minute, and the UI shows a notice until it finishes.

Frontend dev server (proxies `/api` to port 8000):

```bash
cd frontend
npm install
npm run dev
```

Or build once and let the backend serve everything on one port:

```bash
cd frontend && npm run build   # backend serves frontend/dist at /
```

Tests:

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

### Config

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | SQLite in `backend/var/` | e.g. `postgresql://…` (install `psycopg2-binary`) |
| `GRIDRISK_DATA_DIR` | `backend/var` | Database and trained models |
| `GRIDRISK_DATA_CUTOFF` | `2025-12-31` | "As of" date for the queue snapshot |
| `ALLOWED_ORIGINS` | `http://localhost:5173,…` | CORS origins, comma-separated |
| `VITE_API_BASE` | (same origin) | Frontend API base URL |

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/assess` | Full assessment (odds, timeline, cost, drivers, site, capital at risk) |
| `POST /api/alternatives` | Rank substations in a region for a project |
| `GET /api/substations/{region}` | POIs with queued MW and track record |
| `POST /api/portfolio`, `POST /api/portfolio/csv` | Batch scoring |
| `GET /api/market` | Queue statistics |
| `GET /api/model` | Model card: metrics, calibration, importance, limitations |
| `GET /api/meta`, `GET /api/health` | Regions, phases, model status |
| `POST /api/assess-site` | Original MVP endpoint (score + level), kept for compatibility |

Interactive docs are at `/docs`.

## Limitations

- **Synthetic until you load real data.** The numbers show how the method works, not facts about real
  substations.
- **A statistical screen, not a power-flow study.** It cannot see the thermal or voltage limit on a
  specific line.
- **Recent queue entries are scored as if conditions match the last fully resolved cohort (2016–2019).**
  Use the reform toggle to test a more optimistic view.
- **Projects still active from the training cohort are excluded,** which can understate slow completions.
