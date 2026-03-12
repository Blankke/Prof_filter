from __future__ import annotations

import time

import requests

from crawler.core.models import FetchedPage


class Fetcher:
    def __init__(self, delay_seconds: float = 0.1, timeout_seconds: float = 20.0) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds

    def get(self, url: str) -> FetchedPage:
        response = requests.get(
            url,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "ProfFilterBot/0.1 (+public faculty indexing MVP)",
            },
            allow_redirects=True,
        )
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        time.sleep(self.delay_seconds)
        return FetchedPage(url=str(response.url), content=response.text, status_code=response.status_code)
