from __future__ import annotations

import re
from urllib.parse import urljoin

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class PkuSpider(BaseSchoolSpider):
    school_id = "pku"
    display_name = "北京大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        soup = self.fetch_profile(self.seed.faculty_entry or "")
        links: list[str] = []
        seen: set[str] = set()
        for page_url in self.list_page_urls(soup):
            page_soup = self.fetch_profile(page_url)
            for anchor in page_soup.select('a[href*="info/"]'):
                href = anchor.get("href", "")
                text = self.clean_text(anchor.get_text(" ", strip=True))
                if not href or not text:
                    continue
                absolute = urljoin(page_url, href)
                if absolute in seen:
                    continue
                seen.add(absolute)
                links.append(absolute)
        return links

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        soup = self.fetch_profile(self.seed.faculty_entry or "")
        anchors = []
        for page_url in self.list_page_urls(soup):
            page_soup = self.fetch_profile(page_url)
            for anchor in page_soup.select('a[href*="info/"]'):
                if self.clean_text(anchor.get_text(" ", strip=True)):
                    anchors.append((page_url, anchor))
        if limit is not None:
            anchors = anchors[:limit]

        teachers: list[Teacher] = []
        seen_ids: set[str] = set()
        for page_url, anchor in anchors:
            try:
                teacher = self.parse_teacher(anchor, page_url)
            except Exception:
                continue
            if teacher is not None and teacher.id not in seen_ids:
                seen_ids.add(teacher.id)
                teachers.append(teacher)
        return teachers

    def list_page_urls(self, soup) -> list[str]:
        base_url = self.seed.faculty_entry or ""
        pages = {base_url}
        for anchor in soup.select('a[href$=".htm"]'):
            href = anchor.get("href", "")
            if href == "ALL.htm" or href.startswith("ALL/"):
                pages.add(urljoin(base_url, href))
        return sorted(pages)

    def parse_teacher(self, anchor, page_url: str) -> Teacher | None:
        href = anchor.get("href", "")
        absolute_url = urljoin(page_url, href)
        summary_line = self.clean_text(anchor.get_text(" ", strip=True))
        if not summary_line:
            return None

        name_match = re.match(r"([^\s]+)", summary_line)
        title_match = re.search(r"职称：\s*(.*?)\s*研究所：", summary_line)
        lab_match = re.search(r"研究所：\s*(.*?)\s*研究领域：", summary_line)
        area_match = re.search(r"研究领域：\s*(.*?)\s*(办公电话：|电子邮件：)", summary_line)
        email_match = re.search(r"电子邮件：\s*(.*)$", summary_line)

        detail = self.fetch_profile(absolute_url)
        detail_text = self.clean_text(detail.get_text(" ", strip=True))
        homepage_match = re.search(r"个人主页：\s*([^\s]+)", detail_text)
        directions_match = re.search(r"主要研究方向\s*(.*?)\s*(主要荣誉与获奖|主要科研项目|代表性学术论著)", detail_text)

        areas = []
        if area_match:
            areas = [self.clean_text(part) for part in re.split(r"[，,；;、/]", area_match.group(1)) if self.clean_text(part)]
        elif directions_match:
            areas = [self.clean_text(part) for part in re.split(r"[，,；;、/]", directions_match.group(1)) if self.clean_text(part)]

        homepage = homepage_match.group(1) if homepage_match else absolute_url
        if homepage and not homepage.startswith("http"):
            homepage = f"https://{homepage}"

        summary = self.clean_text(directions_match.group(1)) if directions_match else summary_line
        if email_match:
            summary = f"{summary} 邮箱：{self.clean_text(email_match.group(1)).replace(' ', '@', 1).replace(' ', '')}"

        return Teacher(
            id=f"pku-{absolute_url.rstrip('/').split('/')[-1].replace('.htm', '')}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算机学院",
            name=name_match.group(1) if name_match else "",
            title=title_match.group(1) if title_match else "",
            lab=self.clean_text(lab_match.group(1)) if lab_match else None,
            lab_status="confirmed" if lab_match else "not_mentioned",
            homepage=homepage,
            research_areas=areas,
            recent_publications=[],
            summary=summary,
        )
