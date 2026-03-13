from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "schools.yaml"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from crawler.catalog_builder import build_catalog, write_catalog
from crawler.core.models import SchoolSeed
from crawler.spiders.registry import SPIDER_REGISTRY


def load_seeds() -> list[SchoolSeed]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return [
        SchoolSeed(id=school["id"], name=school["name"], faculty_entry=school.get("faculty_entry"))
        for school in payload.get("schools", [])
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prof Filter crawler scaffold")
    parser.add_argument("--school", help="Run a single school spider by id")
    parser.add_argument("--list", action="store_true", help="List configured schools and spider status")
    parser.add_argument("--limit", type=int, default=None, help="Limit teacher count during crawl")
    parser.add_argument("--build-catalog", action="store_true", help="Build a live catalog from implemented school spiders")
    parser.add_argument("--output", default=str(BASE_DIR / "data" / "live_catalog.json"), help="Output path for the built catalog")
    parser.add_argument("--cache-dir", default=str(BASE_DIR / "data" / "cache"), help="Cache directory for school snapshots and OpenAlex responses")
    parser.add_argument("--refresh", action="store_true", help="Ignore school cache and rebuild data from source")
    parser.add_argument("--quiet", action="store_true", help="Disable progress logs during build-catalog")
    args = parser.parse_args()

    seeds = load_seeds()
    by_id = {seed.id: seed for seed in seeds}

    if args.list:
        for seed in seeds:
            has_spider = seed.id in SPIDER_REGISTRY
            has_entry = bool(seed.faculty_entry)
            print(f"{seed.id}\tspider={has_spider}\tentry={has_entry}\t{seed.name}")
        return

    if args.build_catalog:
        catalog = build_catalog(
            CONFIG_PATH,
            school_filter=args.school,
            limit=args.limit,
            cache_dir=Path(args.cache_dir),
            refresh=args.refresh,
            log_progress=not args.quiet,
        )
        output_path = Path(args.output)
        write_catalog(catalog, output_path)
        print(json.dumps({"output": str(output_path), "schools": len(catalog.schools), "teachers": len(catalog.teachers)}, ensure_ascii=False))
        return

    if not args.school:
        parser.error("Provide --school or use --list")

    seed = by_id.get(args.school)
    if seed is None:
        parser.error(f"Unknown school id: {args.school}")

    spider_type = SPIDER_REGISTRY.get(seed.id)
    if spider_type is None:
        parser.error(f"No spider registered for: {seed.id}")

    if not seed.faculty_entry:
        parser.error(f"Missing faculty entry URL for: {seed.id}")

    spider = spider_type(seed)
    teachers = spider.crawl_teachers(limit=args.limit)
    print(f"Fetched school={seed.id} teachers={len(teachers)}")


if __name__ == "__main__":
    main()
