# SaveMyGrade

Mountain Madness 2026

SaveMyGrade helps students discover lower-difficulty courses by combining:
- class average/performance data
- professor quality data (RateMyProfessor)
- query-based recommendations from an LLM-backed backend

## Frontend (React + Vite)

The frontend lives in `frontend/` and is already wired to call:
- `POST /api/recommendations`

When running locally, Vite proxies `/api/*` to `http://localhost:5000`, so your Flask backend should run there during development.

### Run locally

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start the React dev server:

```bash
npm run dev
```

3. Open the app:

`http://localhost:5173`

## Current stack

- Python / Flask backend
- React frontend (JavaScript)
- Docker
- RateMyProfessor Database API: https://pypi.org/project/RateMyProfessor-Database-APIs/
