# Grid-Risk-MVP

Run locally (development)

- Start backend (FastAPI):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Start frontend (dev, Vite):

```bash
cd frontend
npm install
npm run dev -- --host
```

Open the frontend at `http://localhost:5173/` for dev or `http://localhost:8000/` after building.

Serve production build via backend (same origin):

```bash
cd frontend
npm run build
# backend serves `frontend/dist` automatically at '/'
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Config

- Frontend: set `VITE_API_BASE` to an absolute URL (no trailing slash) to point API requests to a specific host when running dev.
- Backend: set `ALLOWED_ORIGINS` to a comma-separated list of allowed origins for CORS.

Example:

```bash
export VITE_API_BASE="http://localhost:8000"
export ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```