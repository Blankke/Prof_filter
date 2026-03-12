from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import yaml

from app.models import Catalog, School, Teacher
from crawler.core.models import SchoolSeed
from crawler.spiders.registry import SPIDER_REGISTRY


def load_school_config(config_path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return payload.get("schools", [])


def build_catalog(config_path: Path, school_filter: str | None = None, limit: int | None = None) -> Catalog:
    school_entries = load_school_config(config_path)
    schools: list[School] = []
    teachers: list[Teacher] = []

    for entry in school_entries:
        school_id = entry["id"]
        if school_filter and school_id != school_filter:
            continue

        schools.append(
            School(
                id=school_id,
                name=entry["name"],
                faculties=entry.get("faculties", []),
            )
        )

        spider_type = SPIDER_REGISTRY.get(school_id)
        if spider_type is None:
            continue

        seed = SchoolSeed(id=school_id, name=entry["name"], faculty_entry=entry.get("faculty_entry"))
        if not seed.faculty_entry:
            continue

        spider = spider_type(seed)
        try:
            teachers.extend(spider.crawl_teachers(limit=limit))
        except Exception:
            continue

    return Catalog(
        generated_at=datetime.now().astimezone().isoformat(),
        note="Live catalog generated from public faculty pages. Some schools are still pending adapter implementation.",
        schools=schools,
        teachers=teachers,
    )


def write_catalog(catalog: Catalog, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
