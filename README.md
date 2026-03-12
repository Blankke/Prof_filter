# Prof Filter

Prof Filter is a seven-school aggregation project for public faculty information from Chinese computer-science-related schools. The current MVP ships a runnable backend, a browser dashboard, a crawler scaffold, export endpoints, and a demo dataset. The demo dataset is synthetic seed data so the UI and pipeline can run before the real adapters are finished.

## Scope

- Schools: Tsinghua, Peking, Zhejiang, Shanghai Jiao Tong, Nanjing, Fudan, Renmin.
- Target output: teacher, lab or team, research directions, recent publications.
- Public-only boundary: school sites and public academic indexes.

## Stack

- Backend: FastAPI
- Frontend: server-rendered HTML plus vanilla JavaScript
- Parsing pipeline: YAML config, spider registry, export service

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/

## API

- `GET /api/overview`
- `GET /api/teachers`
- `GET /api/teachers/{teacher_id}`
- `GET /api/labs`
- `GET /api/export/json`
- `GET /api/export/csv`

## Project layout

- `config/`: school definitions and output schema.
- `crawler/`: fetcher and school adapter scaffold.
- `app/`: API, models, services.
- `web/`: dashboard template and assets.
- `data/`: seed dataset used by the MVP.
- `exports/`: generated export files.

## Current status

Implemented now:

- Unified schema for teachers, labs, directions, and recent publications.
- Seven-school configuration file.
- FastAPI endpoints for browsing and exporting results.
- A polished dashboard for school overview and teacher exploration.
- Spider registry and per-school adapter placeholders for the real scraping phase.

Still to do:

- Fill each school adapter with real faculty list and detail-page parsing logic.
- Add DBLP and OpenAlex enrichment.
- Replace synthetic seed data with crawler output.
# Prof_filter
