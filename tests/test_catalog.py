from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog import CatalogService
from app.services.datasets import resolve_catalog_path
from app.services.exporter import export_csv_bytes


def test_overview_contains_seven_schools() -> None:
    service = CatalogService(Path("data/sample_catalog.json"))
    overview = service.overview()
    assert overview["stats"]["school_count"] == 7
    assert len(overview["schools"]) == 7


def test_csv_export_contains_expected_headers() -> None:
    service = CatalogService(Path("data/sample_catalog.json"))
    teachers = service.list_teachers(school_id="tsinghua")
    csv_payload = export_csv_bytes(teachers).decode("utf-8")
    assert "teacher_name" in csv_payload
    assert "recent_publications" in csv_payload
    assert "清华大学" in csv_payload


def test_api_returns_filtered_teachers() -> None:
    service = CatalogService(resolve_catalog_path(Path(".")))
    active_catalog = service.load()
    target_school = active_catalog.schools[0].id
    expected_count = len(service.list_teachers(school_id=target_school))

    client = TestClient(app)
    response = client.get("/api/teachers", params={"school": target_school})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == expected_count
    assert all(item["school_id"] == target_school for item in payload)


def test_api_returns_404_for_missing_teacher() -> None:
    client = TestClient(app)
    response = client.get("/api/teachers/missing-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "teacher_not_found"


def test_resolve_catalog_path_falls_back_to_sample(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    sample = data_dir / "sample_catalog.json"
    sample.write_text("{}", encoding="utf-8")
    assert resolve_catalog_path(tmp_path) == sample
