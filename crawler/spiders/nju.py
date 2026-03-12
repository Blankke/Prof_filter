from __future__ import annotations

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class NjuSpider(BaseSchoolSpider):
    school_id = "nju"
    display_name = "南京大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        return self.parse_listing(page)

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        return []
