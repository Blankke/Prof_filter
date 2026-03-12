from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchoolSeed:
    id: str
    name: str
    faculty_entry: str | None


@dataclass(slots=True)
class FetchedPage:
    url: str
    content: str
    status_code: int
