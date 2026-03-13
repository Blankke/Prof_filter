from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class RucSpider(BaseSchoolSpider):
    school_id = "ruc"
    display_name = "中国人民大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        soup = BeautifulSoup(page.content, "html.parser")
        links: list[str] = []
        for anchor in soup.select(".research a[href]"):
            href = self.clean_text(anchor.get("href", ""))
            if href and href.endswith(".htm"):
                links.append(self.make_absolute(href))
        return links

    def list_page_urls(self) -> list[str]:
        listing_page = self.fetch_listing()
        soup = BeautifulSoup(listing_page.content, "html.parser")
        page_urls: list[str] = [listing_page.url]
        for anchor in soup.select(".page_button a[href]"):
            href = self.clean_text(anchor.get("href", ""))
            if not href.endswith(".htm"):
                continue
            page_urls.append(self.make_absolute(href))
        deduped: list[str] = []
        seen: set[str] = set()
        for url in page_urls:
            if url in seen:
                continue
            deduped.append(url)
            seen.add(url)
        return deduped

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        teacher_links: list[str] = []
        teacher_research_hint: dict[str, str] = {}
        teacher_name_hint: dict[str, str] = {}

        for page_url in self.list_page_urls():
            page = self.fetcher.get(page_url)
            soup = BeautifulSoup(page.content, "html.parser")
            for card in soup.select(".research"):
                anchor = card.select_one("a[href]")
                if anchor is None:
                    continue
                href = self.clean_text(anchor.get("href", ""))
                if not href.endswith(".htm"):
                    continue
                profile_url = self.make_absolute(href)
                if profile_url in teacher_links:
                    continue
                teacher_links.append(profile_url)

                name_node = card.select_one(".text1")
                name_hint = self.clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
                if name_hint:
                    teacher_name_hint[profile_url] = name_hint

                text_blocks = [
                    self.clean_text(node.get_text(" ", strip=True))
                    for node in card.select(".text3")
                    if self.clean_text(node.get_text(" ", strip=True))
                ]
                if text_blocks:
                    teacher_research_hint[profile_url] = text_blocks[0]

                if limit is not None and len(teacher_links) >= limit:
                    break
            if limit is not None and len(teacher_links) >= limit:
                break

        teachers: list[Teacher] = []
        for profile_url in teacher_links:
            try:
                teacher = self.parse_teacher(
                    profile_url,
                    teacher_name_hint.get(profile_url, ""),
                    teacher_research_hint.get(profile_url, ""),
                )
            except Exception:
                continue
            if teacher is not None:
                teachers.append(teacher)
        return teachers

    def parse_teacher(self, profile_url: str, name_hint: str, research_hint: str) -> Teacher | None:
        soup = self.fetch_profile(profile_url)
        name = self.extract_name(soup, name_hint)
        if not name:
            return None

        title = self.extract_title(soup)
        summary = self.extract_summary(soup)
        contact_text = self.extract_contact(soup)
        research_areas = self.extract_research_areas(soup, research_hint)
        homepage = self.extract_homepage(contact_text)
        email = self.extract_email(contact_text)

        if email and email not in summary:
            summary = f"{summary} 邮箱：{email}".strip()

        lab = self.extract_lab(summary)
        teacher_id = self.clean_text(profile_url.split("/")[-1].replace(".htm", ""))

        return Teacher(
            id=f"ruc-{teacher_id}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="信息学院",
            name=name,
            title=title,
            lab=lab,
            lab_status="confirmed" if lab else "not_mentioned",
            homepage=homepage,
            research_areas=research_areas,
            recent_publications=[],
            summary=summary[:1600],
        )

    def extract_name(self, soup: BeautifulSoup, name_hint: str) -> str:
        node = soup.select_one(".card .name")
        if node is not None:
            name = self.clean_text(node.get_text(" ", strip=True))
            if name:
                return name
        return name_hint

    def extract_title(self, soup: BeautifulSoup) -> str:
        title_tag = self.clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        if title_tag:
            parts = [self.clean_text(part) for part in title_tag.split("-") if self.clean_text(part)]
            if len(parts) >= 2:
                return parts[1]
        return ""

    def extract_summary(self, soup: BeautifulSoup) -> str:
        intro = soup.select_one(".card .self_intro")
        if intro is None:
            return ""
        return self.clean_text(intro.get_text(" ", strip=True))

    def extract_contact(self, soup: BeautifulSoup) -> str:
        contact = soup.select_one(".card .contact")
        if contact is None:
            return ""
        return self.clean_text(contact.get_text(" ", strip=True))

    def extract_research_areas(self, soup: BeautifulSoup, research_hint: str) -> list[str]:
        for section in soup.select(".pro_info"):
            heading = section.select_one(".h2 .name")
            if heading is None:
                continue
            if self.clean_text(heading.get_text(" ", strip=True)) != "研究方向":
                continue
            para = section.select_one(".para")
            if para is None:
                break
            text = self.clean_text(para.get_text(" ", strip=True))
            return [
                self.clean_text(part)
                for part in re.split(r"[，,；;、/]", text)
                if self.clean_text(part)
            ]

        if research_hint:
            return [
                self.clean_text(part)
                for part in re.split(r"[，,；;、/]", research_hint)
                if self.clean_text(part)
            ]
        return []

    def extract_homepage(self, contact_text: str) -> str | None:
        match = re.search(r"(https?://[^\s]+)", contact_text)
        if match:
            return match.group(1)
        return None

    def extract_email(self, contact_text: str) -> str | None:
        match = re.search(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+", contact_text)
        return match.group(0) if match else None

    def extract_lab(self, text: str) -> str | None:
        match = re.search(r"((?:实验室|研究所|研究中心|中心|团队)[^，。；;]*)", text)
        if match:
            return self.clean_text(match.group(1))
        return None
