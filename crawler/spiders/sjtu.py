from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup
from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class SjtuSpider(BaseSchoolSpider):
    school_id = "sjtu"
    display_name = "上海交通大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        return self.parse_listing(page)

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        cards = self.fetch_cards()
        if limit is not None:
            cards = cards[:limit]
        teachers: list[Teacher] = []
        for card in cards:
            teacher = self.parse_card(card)
            if teacher is not None:
                teachers.append(teacher)
        return teachers

    def fetch_cards(self) -> list[dict[str, str]]:
        cards: list[dict[str, str]] = []
        seen: set[str] = set()
        for type_id in (1, 2, 3):
            page = 1
            while True:
                response = self.fetcher.get_json(
                    "https://www.cs.sjtu.edu.cn/active/ajax_teacher_list.html",
                    data={
                        "page": page,
                        "cat_id": "20",
                        "cat_code": "jiaoshiml",
                        "type": type_id,
                        "zm": "All",
                        "zc": "全部",
                        "search": "",
                    },
                )
                content = (response or {}).get("content") or ""
                if not content:
                    break
                soup = BeautifulSoup(content, "lxml")
                page_cards = 0
                for anchor in soup.select('a[href]'):
                    href = anchor.get("href", "")
                    text = self.clean_text(anchor.get_text(" ", strip=True))
                    if not href or not text:
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    cards.append({"href": href, "text": text})
                    page_cards += 1
                if page_cards == 0:
                    break
                page += 1
                if page > 40:
                    break
        return cards

    def parse_card(self, card: dict[str, str]) -> Teacher | None:
        text = card["text"]
        href = card["href"]
        absolute = self.make_absolute(href)
        normalized_text = self.normalize_name_spacing(text)
        name_match = re.match(r"([^\s]+)", normalized_text)
        title_match = re.search(r"职称[：:]\s*(.*?)\s*(系所|研究方向|电子邮件|个人主页|$)", text)
        lab_match = re.search(r"(?:系所|团队|实验室)[：:]\s*(.*?)\s*(研究方向|电子邮件|个人主页|$)", text)
        area_match = re.search(r"研究方向[：:]\s*(.*?)\s*(电子邮件|个人主页|$)", text)
        areas = [self.clean_text(part) for part in re.split(r"[，,；;、/]", area_match.group(1)) if self.clean_text(part)] if area_match else []
        return Teacher(
            id=f"sjtu-{absolute.rstrip('/').split('/')[-1].replace('.html', '').replace('.htm', '')}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算机学院",
            name=name_match.group(1) if name_match else normalized_text[:16],
            title=title_match.group(1) if title_match else "",
            lab=self.clean_text(lab_match.group(1)) if lab_match else None,
            lab_status="confirmed" if lab_match else "not_mentioned",
            homepage=absolute,
            research_areas=areas,
            recent_publications=[],
            summary=normalized_text,
        )

    @staticmethod
    def normalize_name_spacing(text: str) -> str:
        # Some SJTU cards render names as "陈 榕"; collapse CJK-internal spaces.
        return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text).strip()
