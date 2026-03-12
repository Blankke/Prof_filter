from __future__ import annotations

from pathlib import Path

import yaml


class SchoolConfigService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> list[dict[str, object]]:
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return payload.get("schools", [])
