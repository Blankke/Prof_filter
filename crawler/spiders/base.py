from __future__ import annotations

from abc import ABC, abstractmethod
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.models import Teacher
from crawler.core.fetcher import Fetcher
from crawler.core.models import FetchedPage, SchoolSeed


class BaseSchoolSpider(ABC):
    school_id: str
    display_name: str

    def __init__(self, seed: SchoolSeed, fetcher: Fetcher | None = None) -> None:
        self.seed = seed
        self.fetcher = fetcher or Fetcher()

    def fetch_listing(self) -> FetchedPage:
        if not self.seed.faculty_entry:
            raise ValueError(f"Missing faculty entry URL for {self.seed.name}")
        return self.fetcher.get(self.seed.faculty_entry)

    def parse_listing(self, page: FetchedPage) -> list[str]:
        soup = BeautifulSoup(page.content, "html.parser")
        return [anchor.get("href") for anchor in soup.select("a[href]") if anchor.get("href")]

    def make_absolute(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return urljoin(self.seed.faculty_entry or "", href)

    @staticmethod
    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def fetch_profile(self, url: str) -> BeautifulSoup:
        page = self.fetcher.get(url)
        return BeautifulSoup(page.content, "lxml")

    @abstractmethod
    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        raise NotImplementedError
