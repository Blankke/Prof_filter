from __future__ import annotations

import re
from urllib.parse import urljoin

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class NjuSpider(BaseSchoolSpider):
    school_id = "nju"
    display_name = "南京大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        page_urls = [
            "https://cs.nju.edu.cn/2639/list.htm",
            "https://cs.nju.edu.cn/2640/list.htm",
            "https://cs.nju.edu.cn/zzp/list.htm",
            "https://cs.nju.edu.cn/kxkbd/list.htm",
            "https://cs.nju.edu.cn/2641/list.htm",
            "https://cs.nju.edu.cn/2642/list.htm",
        ]
        links: list[str] = []
        seen: set[str] = set()
        for page_url in page_urls:
            soup = self.fetch_profile(page_url)
            for anchor in soup.select('a[href]'):
                href = anchor.get("href", "")
                text = self.clean_text(anchor.get_text(" ", strip=True))
                if not text or not href:
                    continue
                if "/page.htm" not in href and "nju.edu.cn/info/" not in href:
                    continue
                absolute = urljoin(page_url, href)
                if absolute in seen:
                    continue
                seen.add(absolute)
                links.append(absolute)
        return links

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        links = self.normalize_profile_links(self.fetch_listing())
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
        title_text = self.clean_text(soup.title.get_text(strip=True)) if soup.title else ""
        name_match = re.match(r"([^\s(（]+)", title_text)
        email_match = re.search(r"电子邮件[：:]?\s*([A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+)", text)
        area_match = re.search(r"研究方向(?:包括)?[：:]?\s*(.*?)\s*(电话[：:]|电子邮件[：:]|Email|个人主页|科研项目|代表性成果|论文|著作|$)", text)
        lab_match = re.search(r"(计算机[^，。\s]*研究所|国家重点实验室|实验室主任|研究所副所长)", text)
        summary = text[:1200]
        areas = []
        if area_match:
            areas = [self.clean_text(part) for part in re.split(r"[，,；;、/]", area_match.group(1)) if self.clean_text(part)]

        if email_match and email_match.group(1) not in summary:
            summary = f"{summary} 邮箱：{email_match.group(1)}"

        return Teacher(
            id=f"nju-{url.rstrip('/').split('/')[-2] if url.endswith('/page.htm') else url.rstrip('/').split('/')[-1].replace('.htm', '')}",
            school_id=self.school_id,
            school=self.display_name,
            faculty="计算机学院",
            name=name_match.group(1) if name_match else title_text.split("-")[0],
            title="教授" if "/2639/" in url else "副教授" if "/2640/" in url else "",
            lab=self.clean_text(lab_match.group(1)) if lab_match else None,
            lab_status="confirmed" if lab_match else "not_mentioned",
            homepage=url,
            research_areas=areas,
            recent_publications=[],
            summary=summary,
        )
