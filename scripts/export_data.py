from __future__ import annotations

from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "exports"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.catalog import CatalogService
from app.services.datasets import resolve_catalog_path
from app.services.exporter import export_csv_bytes, export_json_bytes


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    service = CatalogService(resolve_catalog_path(BASE_DIR))
    teachers = service.list_teachers()

    json_path = EXPORT_DIR / "prof-filter.json"
    csv_path = EXPORT_DIR / "prof-filter.csv"

    json_path.write_bytes(export_json_bytes(teachers))
    csv_path.write_bytes(export_csv_bytes(teachers))

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
