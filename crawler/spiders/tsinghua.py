from __future__ import annotations

import re

from app.models import Publication, Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class TsinghuaSpider(BaseSchoolSpider):
    school_id = "tsinghua"
    display_name = "清华大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        soup = self.fetch_profile(self.seed.faculty_entry or "")
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select('a[href^="../info/"]'):
            href = anchor.get("href", "")
            text = self.clean_text(anchor.get_text(" ", strip=True))
            if not href or not text:
                continue
            absolute = self.make_absolute(href)
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        listing = self.fetch_listing()
        links = self.normalize_profile_links(listing)
        if limit is not None:
            links = links[:limit]

        teachers: list[Teacher] = []
        for url in links:
            try:
                teacher = self.parse_teacher(url)
            except Exception:
                continue
            if teacher is not None:
                teachers.append(teacher)
        return teachers

    def parse_teacher(self, url: str) -> Teacher | None:
        soup = self.fetch_profile(url)
        text = self.clean_text(soup.get_text(" ", strip=True))
        name_match = re.search(r"姓名：\s*([^\s]+)", text)
        title_match = re.search(r"职称：\s*([^\s]+)", text)
        area_match = re.search(r"研究领域\s*(.*?)\s*(研究概况|教学概况|讲授课程|研究课题|奖励与荣誉|学术成果|下一篇：|上一篇：)", text)
        summary_match = re.search(r"(研究概况|教学概况)\s*(.*?)\s*(研究课题|奖励与荣誉|学术成果|下一篇：|上一篇：|【 关闭 】)", text)
        lab_match = re.search(r"首页\s*>\s*师资状况\s*>\s*教职工名录\s*>\s*(.*?)\s*>\s*[^>]*\s*>\s*正文", text)
        name = name_match.group(1) if name_match else self.clean_text(soup.title.get_text(strip=True).split("-")[0])
        if not name:
            return None

        research_areas = []
        if area_match:
            research_areas = [
                self.clean_text(part)
                for part in re.split(r"[，,；;、/]", area_match.group(1))
                if self.clean_text(part) and len(self.clean_text(part)) <= 32
            ]

        return Teacher(
            id=f"tsinghua-{url.rstrip('/').split('/')[-1].replace('.htm', '')}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算机科学与技术系",
            name=name,
            title=title_match.group(1) if title_match else "",
            lab=self.clean_text(lab_match.group(1)) if lab_match else None,
            lab_status="confirmed" if lab_match else "not_mentioned",
            homepage=url,
            research_areas=research_areas,
            recent_publications=self.extract_publications(text),
            summary=self.clean_text(summary_match.group(2)) if summary_match else "",
        )

    def extract_publications(self, text: str) -> list[Publication]:
        block_match = re.search(r"学术成果\s*(.*?)\s*(下一篇：|上一篇：|【 关闭 】|师资状况)", text)
        if not block_match:
            return []

        citations = re.findall(r"\[(\d+)\]\s*(.*?)(?=(\[\d+\]\s*)|$)", block_match.group(1))
        publications: list[Publication] = []
        for _, citation, _ in citations:
            clean_citation = self.clean_text(citation)
            year_match = re.search(r"(20\d{2}|19\d{2})", clean_citation)
            year = int(year_match.group(1)) if year_match else 0
            if year and year < 2021:
                continue
            venue_match = re.search(r"(DAC|ISPD|ICCAD|DATE|TCAD|TCAS-II|TVLSI|IEICE|IET|VLSI)", clean_citation, re.IGNORECASE)
            publications.append(
                Publication(
                    title=clean_citation,
                    venue=venue_match.group(1) if venue_match else "学校官网",
                    year=year,
                    kind="other",
                    source="清华大学计算机系官网",
                    link=None,
                )
            )
        publications.sort(key=lambda publication: (publication.year, publication.title), reverse=True)
        return publications[:30]
