from __future__ import annotations

from pathlib import Path


def resolve_catalog_path(base_dir: Path) -> Path:
    live_path = base_dir / "data" / "live_catalog.json"
    sample_path = base_dir / "data" / "sample_catalog.json"
    return live_path if live_path.exists() else sample_path
