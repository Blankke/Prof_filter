# Prof Filter

Prof Filter is a seven-school aggregation project for public faculty information from Chinese computer-science-related schools. The current MVP ships a runnable backend, a browser dashboard, export endpoints, and a real crawling pipeline for the first implemented schools. When a live catalog exists, the UI loads it automatically; otherwise it falls back to the demo dataset.

## Scope

- Schools: Tsinghua, Peking, Zhejiang, Shanghai Jiao Tong, Nanjing, Fudan, Renmin.
- Target output: teacher, lab or team, research directions, recent publications.
- Publication display policy: keep at most the most recent 30 publications per teacher.
- Public-only boundary: school sites and public academic indexes.

## Stack

- Backend: FastAPI
- Frontend: server-rendered HTML plus vanilla JavaScript
- Parsing pipeline: YAML config, spider registry, export service

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 httpx beautifulsoup4 pyyaml pydantic pytest requests lxml
.venv/bin/python scripts/crawl.py --build-catalog
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

## Utility scripts

```bash
.venv/bin/python scripts/crawl.py --build-catalog
.venv/bin/python scripts/crawl.py --build-catalog --refresh
.venv/bin/python scripts/crawl.py --build-catalog --school pku --refresh
.venv/bin/python scripts/export_data.py
.venv/bin/python scripts/crawl.py --list
```

## Pipeline behavior

- School-level progress logs are printed during `--build-catalog` unless `--quiet` is used.
- HTTP requests for teacher pages and OpenAlex enrichment use timeouts and retry limits.
- School results are cached in `data/cache/schools/` so repeated runs do not always re-crawl everything.
- OpenAlex author and works responses are cached in `data/cache/openalex/`.
- Use `--refresh` to ignore caches and rebuild from upstream sources.

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
- Real adapters for 清华大学 and 北京大学 public faculty pages.
- Real adapters for 南京大学 and 上海交通大学 are in place and ready for broader validation.
- Spider registry and adapter placeholders for the remaining schools.

Still to do:

- Fill the remaining five school adapters with real faculty list and detail-page parsing logic.
- Add DBLP and OpenAlex enrichment.
- Improve publication enrichment when school homepages only expose representative venues.
