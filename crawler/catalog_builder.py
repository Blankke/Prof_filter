from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from time import perf_counter

import yaml

from app.models import Catalog, School, Teacher
from crawler.enrichment import OpenAlexEnricher
from crawler.core.models import SchoolSeed
from crawler.spiders.registry import SPIDER_REGISTRY


MAX_PUBLICATIONS_PER_TEACHER = 30
PUBLICATION_YEAR_START = 2024
PUBLICATION_YEAR_END = 2026


def render_progress(label: str, current: int, total: int, width: int = 24) -> str:
    safe_total = max(total, 1)
    clamped = min(max(current, 0), safe_total)
    ratio = clamped / safe_total
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    return f"{label} [{bar}] {clamped}/{safe_total}"


def normalize_teacher_publications(teacher: Teacher) -> Teacher:
    teacher.recent_publications = [
        publication
        for publication in teacher.recent_publications
        if PUBLICATION_YEAR_START <= publication.year <= PUBLICATION_YEAR_END
    ]
    teacher.recent_publications = sorted(
        teacher.recent_publications,
        key=lambda publication: (publication.year, publication.title),
        reverse=True,
    )[:MAX_PUBLICATIONS_PER_TEACHER]
    return teacher


def normalize_teachers_publications(teachers: list[Teacher]) -> list[Teacher]:
    return [normalize_teacher_publications(teacher) for teacher in teachers]


def school_cache_path(cache_dir: Path, school_id: str) -> Path:
    return cache_dir / "schools" / f"{school_id}.json"


def load_cached_teachers(cache_dir: Path, school_id: str) -> list[Teacher] | None:
    path = school_cache_path(cache_dir, school_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Teacher.model_validate(item) for item in payload.get("teachers", [])]


def write_cached_teachers(cache_dir: Path, school_id: str, teachers: list[Teacher]) -> None:
    path = school_cache_path(cache_dir, school_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"teachers": [teacher.model_dump(mode="json") for teacher in teachers]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_school_config(config_path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return payload.get("schools", [])


def build_catalog(
    config_path: Path,
    school_filter: str | None = None,
    limit: int | None = None,
    cache_dir: Path | None = None,
    refresh: bool = False,
    log_progress: bool = True,
) -> Catalog:
    school_entries = load_school_config(config_path)
    schools: list[School] = []
    teachers: list[Teacher] = []
    resolved_cache_dir = cache_dir or config_path.parent.parent / "data" / "cache"
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)
    enricher = OpenAlexEnricher(cache_dir=resolved_cache_dir / "openalex", log_progress=log_progress)

    school_total = sum(1 for entry in school_entries if not school_filter or entry["id"] == school_filter)
    school_index = 0

    for entry in school_entries:
        school_id = entry["id"]
        if school_filter and school_id != school_filter:
            continue
        school_index += 1
        if log_progress:
            print(render_progress("schools", school_index, school_total) + f" -> {entry['name']}")

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
            if log_progress:
                print(f"[{school_index}/{school_total}] {entry['name']} skipped: missing faculty_entry")
            continue

        spider = spider_type(seed)
        started = perf_counter()

        if not refresh:
            cached_teachers = load_cached_teachers(resolved_cache_dir, school_id)
            if cached_teachers is not None:
                cached_teachers = normalize_teachers_publications(cached_teachers)
                write_cached_teachers(resolved_cache_dir, school_id, cached_teachers)
                teachers.extend(cached_teachers)
                if log_progress:
                    print(
                        f"[{school_index}/{school_total}] {entry['name']} cache-hit teachers={len(cached_teachers)} elapsed={perf_counter() - started:.1f}s"
                    )
                continue

        try:
            if log_progress:
                print(f"[{school_index}/{school_total}] {entry['name']} crawl-start")
            crawled_teachers = spider.crawl_teachers(limit=limit)
            if log_progress:
                print(f"[{school_index}/{school_total}] {entry['name']} crawl-done teachers={len(crawled_teachers)}")

            for teacher_index, teacher in enumerate(crawled_teachers, start=1):
                if log_progress:
                    print(render_progress("teachers", teacher_index, len(crawled_teachers)) + f" -> {teacher.name}")
                    print(f"  [teacher {teacher_index}/{len(crawled_teachers)}] enrich-start {teacher.name}")
                try:
                    teacher = enricher.enrich_teacher(teacher)
                    teacher = normalize_teacher_publications(teacher)
                    if log_progress:
                        print(
                            f"  [teacher {teacher_index}/{len(crawled_teachers)}] enrich-done {teacher.name} publications={len(teacher.recent_publications)}"
                        )
                except Exception as exc:
                    if log_progress:
                        print(
                            f"  [teacher {teacher_index}/{len(crawled_teachers)}] enrich-failed {teacher.name} reason={exc.__class__.__name__}"
                        )
            write_cached_teachers(resolved_cache_dir, school_id, crawled_teachers)
            teachers.extend(crawled_teachers)
            if log_progress:
                print(
                    f"[{school_index}/{school_total}] {entry['name']} done teachers={len(crawled_teachers)} elapsed={perf_counter() - started:.1f}s"
                )
        except Exception as exc:
            if log_progress:
                print(f"[{school_index}/{school_total}] {entry['name']} failed, skipped reason={exc.__class__.__name__}")
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
