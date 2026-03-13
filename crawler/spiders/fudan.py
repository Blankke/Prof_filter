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
    article_url = "https://cs.fudan.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"

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
                        {"field": "exField1", "name": "exField1"},
                        {"field": "exField7", "name": "exField7"},
                        {"field": "exField9", "name": "exField9"},
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
        soup = self.fetch_profile(profile_url)
        info_root = soup.select_one(".infobox .news_info") or soup
        summary_text = self.clean_text(info_root.get_text(" ", strip=True))

        name = self.extract_name(soup, row)
        if not name:
            return None

        title = self.extract_title(soup, row, summary_text)
        homepage = self.extract_homepage(soup, profile_url)
        lab = self.extract_lab(summary_text)
        areas = self.extract_research_areas(soup, summary_text)

        email = self.extract_email(soup, row, summary_text)
        if email and email not in summary_text:
            summary_text = f"{summary_text} 邮箱：{email}"

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
            homepage=homepage,
            research_areas=areas,
            recent_publications=[],
            summary=summary_text[:1600],
        )

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
