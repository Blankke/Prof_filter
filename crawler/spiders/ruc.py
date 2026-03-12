from __future__ import annotations

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class RucSpider(BaseSchoolSpider):
    school_id = "ruc"
    display_name = "中国人民大学"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        return self.parse_listing(page)

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        return []
