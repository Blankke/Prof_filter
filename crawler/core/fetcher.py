from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from crawler.core.models import FetchedPage


class Fetcher:
    def __init__(
        self,
        delay_seconds: float = 0.1,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        backoff_factor: float = 0.6,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ProfFilterBot/0.1 (+public faculty indexing MVP)"})

        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, url: str) -> FetchedPage:
        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        time.sleep(self.delay_seconds)
        return FetchedPage(url=str(response.url), content=response.text, status_code=response.status_code)

    def get_json(self, url: str, data: dict[str, object] | None = None) -> dict[str, object]:
        response = self.session.post(
            url,
            data=data or {},
            timeout=self.timeout_seconds,
            headers={
                "X-Requested-With": "XMLHttpRequest",
            },
            allow_redirects=True,
        )
        time.sleep(self.delay_seconds)
        try:
            return response.json()
        except Exception:
            return {}
