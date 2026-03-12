from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services.catalog import CatalogService
from app.services.config import SchoolConfigService
from app.services.datasets import resolve_catalog_path
from app.services.exporter import export_csv_bytes, export_json_bytes


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "schools.yaml"

app = FastAPI(title="Prof Filter", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
catalog_service = CatalogService(resolve_catalog_path(BASE_DIR))
school_config_service = SchoolConfigService(CONFIG_PATH)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    overview = catalog_service.overview()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "overview": overview,
            "school_config": school_config_service.load(),
        },
    )


@app.get("/api/overview")
def api_overview() -> dict[str, object]:
    return catalog_service.overview()


@app.get("/api/teachers")
def api_teachers(
    school: str | None = Query(default=None),
    query: str | None = Query(default=None),
    area: str | None = Query(default=None),
) -> list[dict[str, object]]:
    teachers = catalog_service.list_teachers(school_id=school, query=query, research_area=area)
    return [teacher.model_dump(mode="json") for teacher in teachers]


@app.get("/api/teachers/{teacher_id}")
def api_teacher_detail(teacher_id: str) -> dict[str, object]:
    teacher = catalog_service.get_teacher(teacher_id)
    if teacher is None:
        raise HTTPException(status_code=404, detail="teacher_not_found")
    return teacher.model_dump(mode="json")


@app.get("/api/schools")
def api_schools() -> list[dict[str, object]]:
    return school_config_service.load()


@app.get("/api/labs")
def api_labs(school: str | None = Query(default=None)) -> list[dict[str, object]]:
    return catalog_service.labs(school_id=school)


@app.get("/api/export/json")
def api_export_json(
    school: str | None = Query(default=None),
    area: str | None = Query(default=None),
) -> StreamingResponse:
    teachers = catalog_service.list_teachers(school_id=school, research_area=area)
    return StreamingResponse(
        iter([export_json_bytes(teachers)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=prof-filter.json"},
    )


@app.get("/api/export/csv")
def api_export_csv(
    school: str | None = Query(default=None),
    area: str | None = Query(default=None),
) -> StreamingResponse:
    teachers = catalog_service.list_teachers(school_id=school, research_area=area)
    return StreamingResponse(
        iter([export_csv_bytes(teachers)]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=prof-filter.csv"},
    )
