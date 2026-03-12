from __future__ import annotations

import csv
import io
import json

from app.models import Teacher


def export_records(teachers: list[Teacher]) -> list[dict[str, object]]:
    records = []
    for teacher in teachers:
        records.append(
            {
                "school": teacher.school,
                "faculty": teacher.faculty,
                "teacher_name": teacher.name,
                "title": teacher.title,
                "lab": teacher.lab or "",
                "lab_status": teacher.lab_status,
                "research_areas": teacher.research_areas,
                "homepage": teacher.homepage or "",
                "recent_publications": [publication.model_dump() for publication in teacher.recent_publications],
            }
        )
    return records


def export_json_bytes(teachers: list[Teacher]) -> bytes:
    return json.dumps(export_records(teachers), ensure_ascii=False, indent=2).encode("utf-8")


def export_csv_bytes(teachers: list[Teacher]) -> bytes:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "school",
            "faculty",
            "teacher_name",
            "title",
            "lab",
            "lab_status",
            "research_areas",
            "homepage",
            "recent_publications",
        ],
    )
    writer.writeheader()
    for teacher in teachers:
        writer.writerow(
            {
                "school": teacher.school,
                "faculty": teacher.faculty,
                "teacher_name": teacher.name,
                "title": teacher.title,
                "lab": teacher.lab or "",
                "lab_status": teacher.lab_status,
                "research_areas": " | ".join(teacher.research_areas),
                "homepage": teacher.homepage or "",
                "recent_publications": " | ".join(
                    f"{paper.year} {paper.title} [{paper.venue}]"
                    for paper in teacher.recent_publications
                ),
            }
        )
    return stream.getvalue().encode("utf-8")
