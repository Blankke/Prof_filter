from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from app.models import Catalog, Teacher, build_school_overview


class CatalogService:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self._catalog: Catalog | None = None

    def load(self) -> Catalog:
        if self._catalog is None:
            payload = self.load_payload()
            self._catalog = Catalog.model_validate(payload)
        return self._catalog

    def load_payload(self) -> dict[str, object]:
        if self.data_path.is_dir():
            return self.load_payload_from_shards(self.data_path)
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    @staticmethod
    def load_payload_from_shards(shards_dir: Path) -> dict[str, object]:
        schools: list[dict[str, object]] = []
        teachers: list[dict[str, object]] = []
        school_ids: set[str] = set()
        notes: list[str] = []

        for path in sorted(shards_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for school in payload.get("schools", []):
                school_id = school.get("id")
                if school_id in school_ids:
                    continue
                school_ids.add(school_id)
                schools.append(school)
            teachers.extend(payload.get("teachers", []))
            note = str(payload.get("note") or "").strip()
            if note and note not in notes:
                notes.append(note)

        return {
            "generated_at": datetime.now().astimezone().isoformat(),
            "note": " | ".join(notes) if notes else "Merged from per-school catalogs.",
            "schools": schools,
            "teachers": teachers,
        }

    def overview(self) -> dict[str, object]:
        catalog = self.load()
        teachers = catalog.teachers
        unique_labs = {teacher.lab for teacher in teachers if teacher.lab}
        unique_areas = {area for teacher in teachers for area in teacher.research_areas}
        return {
            "generated_at": catalog.generated_at,
            "note": catalog.note,
            "schools": build_school_overview(catalog),
            "stats": {
                "school_count": len(catalog.schools),
                "teacher_count": len(teachers),
                "lab_count": len(unique_labs),
                "area_count": len(unique_areas),
            },
        }

    def list_teachers(
        self,
        school_id: str | None = None,
        query: str | None = None,
        research_area: str | None = None,
    ) -> list[Teacher]:
        teachers = self.load().teachers
        filtered = teachers

        if school_id:
            filtered = [teacher for teacher in filtered if teacher.school_id == school_id]

        if research_area:
            filtered = [
                teacher
                for teacher in filtered
                if any(research_area.casefold() in area.casefold() for area in teacher.research_areas)
            ]

        if query:
            needle = query.casefold()
            filtered = [
                teacher
                for teacher in filtered
                if needle in teacher.name.casefold()
                or needle in teacher.school.casefold()
                or needle in teacher.faculty.casefold()
                or needle in teacher.summary.casefold()
                or any(needle in area.casefold() for area in teacher.research_areas)
            ]

        return sorted(filtered, key=lambda teacher: (teacher.school, teacher.name))

    def get_teacher(self, teacher_id: str) -> Teacher | None:
        for teacher in self.load().teachers:
            if teacher.id == teacher_id:
                return teacher
        return None

    def labs(self, school_id: str | None = None) -> list[dict[str, object]]:
        teachers = self.list_teachers(school_id=school_id)
        by_lab: dict[str, dict[str, object]] = {}
        for teacher in teachers:
            lab_name = teacher.lab or "未明确实验室"
            entry = by_lab.setdefault(
                lab_name,
                {
                    "name": lab_name,
                    "school": teacher.school,
                    "faculty": teacher.faculty,
                    "teacher_count": 0,
                    "teachers": [],
                    "research_areas": set(),
                },
            )
            entry["teacher_count"] += 1
            entry["teachers"].append({"id": teacher.id, "name": teacher.name})
            entry["research_areas"].update(teacher.research_areas)

        result = []
        for value in by_lab.values():
            result.append(
                {
                    "name": value["name"],
                    "school": value["school"],
                    "faculty": value["faculty"],
                    "teacher_count": value["teacher_count"],
                    "teachers": value["teachers"],
                    "research_areas": sorted(value["research_areas"]),
                }
            )
        return sorted(result, key=lambda item: (item["school"], item["name"]))
