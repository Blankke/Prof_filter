from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup
from app.models import Publication, Teacher
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

        profile_summary = normalized_text
        profile_title = title_match.group(1) if title_match else ""
        profile_lab = self.clean_text(lab_match.group(1)) if lab_match else None
        profile_homepage = absolute
        profile_publications: list[Publication] = []
        try:
            details = self.parse_profile_details(absolute)
            profile_summary = details["summary"] or profile_summary
            profile_title = details["title"] or profile_title
            profile_lab = details["lab"] or profile_lab
            profile_homepage = details["homepage"] or profile_homepage
            if details["research_areas"]:
                areas = details["research_areas"]
            profile_publications = details["publications"]
        except Exception:
            pass

        return Teacher(
            id=f"sjtu-{absolute.rstrip('/').split('/')[-1].replace('.html', '').replace('.htm', '')}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算机学院",
            name=name_match.group(1) if name_match else normalized_text[:16],
            title=profile_title,
            lab=profile_lab,
            lab_status="confirmed" if profile_lab else "not_mentioned",
            homepage=profile_homepage,
            research_areas=areas,
            recent_publications=profile_publications,
            summary=profile_summary[:1600],
        )

    def parse_profile_details(self, url: str) -> dict[str, object]:
        soup = self.fetch_profile(url)
        text_root = soup.select_one(".txt") or soup
        profile_text = self.clean_text(text_root.get_text(" ", strip=True))
        line_texts = [self.clean_text(line) for line in text_root.get_text("\n", strip=True).splitlines() if self.clean_text(line)]

        title_text = ""
        title_node = text_root.select_one(".ls2")
        if title_node is not None:
            title_text = self.clean_text(title_node.get_text(" ", strip=True))

        lab_text = ""
        lab_match = re.search(r"(?:所在研究所|实验室|团队)[：:]\s*([^。；;\n]+)", profile_text)
        if lab_match:
            lab_text = self.clean_text(lab_match.group(1))

        homepage = url
        homepage_match = re.search(r"个人主页[：:]\s*(https?://\S+)", profile_text)
        if homepage_match:
            homepage = homepage_match.group(1).rstrip("。,;；")

        areas = self.extract_research_areas(profile_text)
        publications = self.extract_publications(line_texts)

        return {
            "summary": profile_text,
            "title": title_text,
            "lab": lab_text or None,
            "homepage": homepage,
            "research_areas": areas,
            "publications": publications,
        }

    def extract_research_areas(self, text: str) -> list[str]:
        match = re.search(
            r"(?:研究方向|研究领域|主要研究方向)[：:]\s*(.*?)\s*(?:邮箱|Email|个人主页|地址|所在研究所|$)",
            text,
        )
        if not match:
            return []
        areas_text = self.clean_text(match.group(1))
        return [
            self.clean_text(part)
            for part in re.split(r"[，,；;、/]", areas_text)
            if self.clean_text(part)
        ]

    def extract_publications(self, lines: list[str]) -> list[Publication]:
        publications: list[Publication] = []
        seen_titles: set[str] = set()
        venue_tokens = [
            "ieee",
            "acm",
            "cvpr",
            "iccv",
            "eccv",
            "aaai",
            "ijcai",
            "neurips",
            "icml",
            "iclr",
            "sigcomm",
            "sigmod",
            "vldb",
            "osdi",
            "sosp",
            "nsdi",
            "tpami",
            "tkde",
            "tifs",
            "tdsc",
        ]
        conference_tokens = {
            "cvpr",
            "iccv",
            "eccv",
            "aaai",
            "ijcai",
            "neurips",
            "icml",
            "iclr",
            "sigcomm",
            "sigmod",
            "vldb",
            "osdi",
            "sosp",
            "nsdi",
        }

        for line in lines:
            year_match = re.search(r"(19|20)\d{2}", line)
            if not year_match:
                continue
            lowered = line.casefold()
            if not any(token in lowered for token in venue_tokens) and "论文" not in line:
                continue

            title = self.clean_text(re.sub(r"^\[[^\]]+\]\s*", "", line))
            title_key = title.casefold()
            if not title or title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            year = int(year_match.group(0))
            venue = "上海交通大学计算机学院官网"
            kind = "other"
            for token in venue_tokens:
                if token in lowered:
                    venue = token.upper()
                    kind = "conference" if token in conference_tokens else "journal"
                    break

            publications.append(
                Publication(
                    title=title,
                    venue=venue,
                    year=year,
                    kind=kind,
                    source="上海交通大学计算机学院官网",
                    link=None,
                )
            )
            if len(publications) >= 30:
                break
        return publications

    @staticmethod
    def normalize_name_spacing(text: str) -> str:
        # Some SJTU cards render names as "陈 榕"; collapse CJK-internal spaces.
        return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text).strip()
