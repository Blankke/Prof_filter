from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup
from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class FudanSpider(BaseSchoolSpider):
    school_id = "fudan"
    display_name = "复旦大学"
    article_url = "https://ai.fudan.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        teachers = self.fetch_teachers()
        return [teacher.get("cnUrl", "") for teacher in teachers if teacher.get("cnUrl")]

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        teacher_rows = self.fetch_teachers()
        if limit is not None:
            teacher_rows = teacher_rows[:limit]

        teachers: list[Teacher] = []
        for row in teacher_rows:
            try:
                teacher = self.parse_teacher(row)
            except Exception:
                continue
            if teacher is not None:
                teachers.append(teacher)
        return teachers

    def fetch_teachers(self) -> list[dict[str, object]]:
        response = self.fetcher.get_json(
            self.article_url,
            data={
                "siteId": 577,
                "pageIndex": 1,
                "rows": 999,
                "conditions": json.dumps([]),
                "orders": json.dumps([{"field": "publishTime", "type": "desc"}]),
                "returnInfos": json.dumps(
                    [
                        {"field": "title", "name": "title"},
                        {"field": "cnUrl", "name": "cnUrl"},
                        {"field": "headerPic", "name": "headerPic"},
                        {"field": "summary", "name": "summary"},
                        {"field": "exField1", "name": "exField1"},
                        {"field": "exField2", "name": "exField2"},
                        {"field": "exField3", "name": "exField3"},
                        {"field": "exField4", "name": "exField4"},
                        {"field": "exField5", "name": "exField5"},
                        {"field": "exField6", "name": "exField6"},
                        {"field": "exField7", "name": "exField7"},
                        {"field": "exField8", "name": "exField8"},
                        {"field": "exField9", "name": "exField9"},
                        {"field": "exField10", "name": "exField10"},
                        {"field": "exField11", "name": "exField11"},
                        {"field": "exField12", "name": "exField12"},
                        {"field": "email", "name": "email"},
                        {"field": "columnId", "name": "columnId"},
                    ]
                ),
                "articleType": 1,
                "level": 1,
            },
        )
        rows = response.get("data") or []
        return [row for row in rows if isinstance(row, dict) and row.get("title") and row.get("cnUrl")]

    def parse_teacher(self, row: dict[str, object]) -> Teacher | None:
        profile_url = self.make_absolute(str(row.get("cnUrl") or ""))
        name = self.clean_text(str(row.get("title") or ""))
        if not name:
            return None

        title = self.pick_title_from_row(row)
        areas = self.extract_research_areas_from_row(row)
        lab = self.extract_lab_from_row(row)
        email = self.clean_text(str(row.get("email") or "")) or None
        summary_text = self.build_summary_from_row(row)
        if email and email not in summary_text:
            summary_text = f"{summary_text} 邮箱：{email}"
        if "来源：复旦AI名录" not in summary_text:
            summary_text = f"{summary_text} 来源：复旦AI名录字段".strip()

        column_id = str(row.get("columnId") or "").strip()
        teacher_id = column_id or re.sub(r"[^a-z0-9]+", "-", profile_url.casefold()).strip("-")

        return Teacher(
            id=f"fudan-{teacher_id}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算与智能创新学院",
            name=name,
            title=title,
            lab=lab,
            lab_status="confirmed" if lab else "not_mentioned",
            homepage=profile_url,
            research_areas=areas,
            recent_publications=[],
            summary=summary_text[:1600],
        )

    def pick_title_from_row(self, row: dict[str, object]) -> str:
        for key in ("exField1", "exField6", "exField9", "exField8"):
            value = self.clean_text(str(row.get(key) or ""))
            if value and value != "无":
                return value
        return ""

    def extract_research_areas_from_row(self, row: dict[str, object]) -> list[str]:
        candidates = []
        for key in ("exField4", "exField5", "exField10", "summary"):
            value = self.clean_text(str(row.get(key) or ""))
            if value and value != "无":
                candidates.append(value)
        areas_text = " ".join(candidates)
        if not areas_text:
            return []

        match = re.search(r"(?:研究方向|研究领域|方向)[:：]?\s*(.*)", areas_text)
        if match:
            areas_text = self.clean_text(match.group(1))

        return [
            self.clean_text(part)
            for part in re.split(r"[，,；;、/]", areas_text)
            if self.clean_text(part) and self.clean_text(part) != "无"
        ][:8]

    def extract_lab_from_row(self, row: dict[str, object]) -> str | None:
        for key in ("summary", "exField10", "exField11", "exField12", "exField5"):
            value = self.clean_text(str(row.get(key) or ""))
            if not value or value == "无":
                continue
            match = re.search(r"((?:实验室|研究所|研究中心|中心|团队)[^，。；;]*)", value)
            if match:
                return self.clean_text(match.group(1))
        return None

    def build_summary_from_row(self, row: dict[str, object]) -> str:
        parts: list[str] = []
        for key in (
            "summary",
            "exField1",
            "exField2",
            "exField3",
            "exField4",
            "exField5",
            "exField6",
            "exField7",
            "exField8",
            "exField9",
            "exField10",
            "exField11",
            "exField12",
        ):
            value = self.clean_text(str(row.get(key) or ""))
            if not value or value == "无":
                continue
            if value in parts:
                continue
            parts.append(value)
        return self.clean_text("；".join(parts))

    def extract_name(self, soup: BeautifulSoup, row: dict[str, object]) -> str:
        title_node = soup.select_one(".infobox .news_title")
        if title_node is not None:
            name = self.clean_text(title_node.get_text(" ", strip=True))
            if name:
                return name
        return self.clean_text(str(row.get("title") or ""))

    def extract_title(self, soup: BeautifulSoup, row: dict[str, object], summary_text: str) -> str:
        title_parts = [
            self.clean_text(node.get_text(" ", strip=True))
            for node in soup.select(".infobox .news_cara span[class^='nr']")
            if self.clean_text(node.get_text(" ", strip=True))
        ]
        if title_parts:
            return " ".join(title_parts)

        fallback = self.clean_text(str(row.get("exField9") or ""))
        if fallback:
            return fallback

        match = re.search(r"职称[：:]\s*(.*?)\s*(邮件|邮箱|研究领域|个人简介|$)", summary_text)
        return self.clean_text(match.group(1)) if match else ""

    def extract_homepage(self, soup: BeautifulSoup, profile_url: str) -> str:
        anchor = soup.select_one(".infobox .news_gr a[href]")
        if anchor is None:
            return profile_url
        href = self.clean_text(anchor.get("href", ""))
        return self.make_absolute(href) if href else profile_url

    def extract_email(self, soup: BeautifulSoup, row: dict[str, object], summary_text: str) -> str | None:
        email_node = soup.select_one(".infobox .news_email .nr")
        if email_node is not None:
            email = self.clean_text(email_node.get_text(" ", strip=True))
            if email:
                return email

        fallback = self.clean_text(str(row.get("email") or ""))
        if fallback:
            return fallback

        match = re.search(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+", summary_text)
        return match.group(0) if match else None

    def extract_research_areas(self, soup: BeautifulSoup, summary_text: str) -> list[str]:
        areas_text = ""
        area_node = soup.select_one(".infobox .news_ex .nr")
        if area_node is not None:
            areas_text = self.clean_text(area_node.get_text(" ", strip=True))

        if not areas_text:
            intro_node = soup.select_one(".infobox .news_jj .nr")
            intro_text = self.clean_text(intro_node.get_text(" ", strip=True)) if intro_node is not None else summary_text
            patterns = [
                r"主要研究方向包括(.*?)(?:。|；|,|，)",
                r"研究方向包括(.*?)(?:。|；|,|，)",
                r"研究领域包括(.*?)(?:。|；|,|，)",
                r"主要研究领域包括(.*?)(?:。|；|,|，)",
                r"研究方向[：:](.*?)(?:个人简介|主持|研究成果|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, intro_text)
                if match:
                    areas_text = self.clean_text(match.group(1))
                    break

        if not areas_text:
            return []

        return [
            self.clean_text(part)
            for part in re.split(r"[，,；;、/]|\s{2,}", areas_text)
            if self.clean_text(part)
        ]

    def extract_lab(self, summary_text: str) -> str | None:
        match = re.search(r"((?:实验室|研究所|研究中心|中心|团队)[^，。；;]*)", summary_text)
        if match:
            return self.clean_text(match.group(1))
        return None
