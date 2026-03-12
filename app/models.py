from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field


LabStatus = Literal["confirmed", "not_mentioned", "parse_failed"]
PaperKind = Literal["conference", "journal", "preprint", "other"]


class Publication(BaseModel):
    title: str
    venue: str
    year: int
    kind: PaperKind = "other"
    source: str
    link: str | None = None


class Teacher(BaseModel):
    id: str
    school_id: str
    school: str
    faculty: str
    name: str
    title: str
    lab: str | None = None
    lab_status: LabStatus = "not_mentioned"
    homepage: str | None = None
    research_areas: list[str] = Field(default_factory=list)
    recent_publications: list[Publication] = Field(default_factory=list)
    summary: str = ""


class School(BaseModel):
    id: str
    name: str
    faculties: list[str]


class Catalog(BaseModel):
    generated_at: str
    note: str
    schools: list[School]
    teachers: list[Teacher]


class SchoolOverview(BaseModel):
    id: str
    name: str
    teacher_count: int
    lab_count: int
    publication_count: int
    top_areas: list[str]


def build_school_overview(catalog: Catalog) -> list[SchoolOverview]:
    teachers_by_school: dict[str, list[Teacher]] = {school.id: [] for school in catalog.schools}
    for teacher in catalog.teachers:
        teachers_by_school.setdefault(teacher.school_id, []).append(teacher)

    overview: list[SchoolOverview] = []
    for school in catalog.schools:
        teachers = teachers_by_school.get(school.id, [])
        area_counter: Counter[str] = Counter()
        lab_names = {teacher.lab for teacher in teachers if teacher.lab}
        publication_count = 0
        for teacher in teachers:
            area_counter.update(teacher.research_areas)
            publication_count += len(teacher.recent_publications)

        overview.append(
            SchoolOverview(
                id=school.id,
                name=school.name,
                teacher_count=len(teachers),
                lab_count=len(lab_names),
                publication_count=publication_count,
                top_areas=[area for area, _ in area_counter.most_common(4)],
            )
        )
    return overview
