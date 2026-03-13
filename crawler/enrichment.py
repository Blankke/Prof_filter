from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import quote_plus, unquote
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from pypinyin import lazy_pinyin
from urllib3.util.retry import Retry

try:
    from scholarly import scholarly
except Exception:
    scholarly = None

from app.models import Publication, Teacher


OPENALEX_AUTHOR_URL = "https://api.openalex.org/authors"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DBLP_AUTHOR_URL = "https://dblp.org/search/author/api"
DBLP_PID_XML_URL = "https://dblp.org/pid/{pid}.xml"
YEAR_START = 2024
YEAR_END = 2026
TARGET_PUBLICATIONS = 30

SCHOOL_ALIASES: dict[str, list[str]] = {
    "清华大学": ["Tsinghua University"],
    "北京大学": ["Peking University"],
    "南京大学": ["Nanjing University"],
    "上海交通大学": ["Shanghai Jiao Tong University", "Shanghai Jiao Tong University School of Electronic Information and Electrical Engineering"],
    "复旦大学": ["Fudan University"],
    "浙江大学": ["Zhejiang University"],
    "中国人民大学": ["Renmin University of China"],
}


class OpenAlexEnricher:
    def __init__(
        self,
        timeout: float = 12.0,
        max_retries: int = 1,
        cache_dir: Path | None = None,
        log_progress: bool = False,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.log_progress = log_progress
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ProfFilterBot/0.1 (+public faculty indexing MVP)"})
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if self.cache_dir is not None:
            (self.cache_dir / "authors").mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "works").mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "dblp_authors").mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "dblp_pid").mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "scholar_web").mkdir(parents=True, exist_ok=True)

    def enrich_teacher(self, teacher: Teacher) -> Teacher:
        existing_titles = {publication.title.casefold() for publication in teacher.recent_publications}
        enriched = list(teacher.recent_publications)
        openalex_added = 0
        dblp_added = 0
        scholar_added = 0
        scholar_web_added = 0

        author_id = self.safe_call(
            teacher=teacher,
            source="OpenAlex",
            operation="match-author",
            func=lambda: self.match_author_id(teacher),
            default=None,
        )
        if author_id:
            openalex_added = self.append_unique_publications(
                enriched=enriched,
                existing_titles=existing_titles,
                publications=self.safe_call(
                    teacher=teacher,
                    source="OpenAlex",
                    operation="fetch-works",
                    func=lambda: self.fetch_recent_works(author_id),
                    default=[],
                ),
                limit=TARGET_PUBLICATIONS,
            )

        if len(enriched) < TARGET_PUBLICATIONS:
            if self.log_progress:
                print(
                    f"    [papers-trigger] {teacher.school} {teacher.name} source=DBLP reason=below-target current={len(enriched)} target={TARGET_PUBLICATIONS}"
                )
            dblp_added = self.append_unique_publications(
                enriched=enriched,
                existing_titles=existing_titles,
                publications=self.safe_call(
                    teacher=teacher,
                    source="DBLP",
                    operation="fetch-works",
                    func=lambda: self.fetch_recent_works_dblp(teacher),
                    default=[],
                ),
                limit=TARGET_PUBLICATIONS,
            )

        if len(enriched) < TARGET_PUBLICATIONS:
            if self.log_progress:
                print(
                    f"    [papers-trigger] {teacher.school} {teacher.name} source=Google Scholar reason=below-target current={len(enriched)} target={TARGET_PUBLICATIONS}"
                )
            scholar_added = self.append_unique_publications(
                enriched=enriched,
                existing_titles=existing_titles,
                publications=self.safe_call(
                    teacher=teacher,
                    source="Google Scholar",
                    operation="fetch-works",
                    func=lambda: self.fetch_recent_works_scholar(teacher),
                    default=[],
                ),
                limit=TARGET_PUBLICATIONS,
            )

        if len(enriched) < TARGET_PUBLICATIONS:
            if self.log_progress:
                print(
                    f"    [papers-trigger] {teacher.school} {teacher.name} source=Google Scholar Web reason=below-target current={len(enriched)} target={TARGET_PUBLICATIONS}"
                )
            scholar_web_added = self.append_unique_publications(
                enriched=enriched,
                existing_titles=existing_titles,
                publications=self.safe_call(
                    teacher=teacher,
                    source="Google Scholar Web",
                    operation="fetch-works",
                    func=lambda: self.fetch_recent_works_scholar_web(teacher),
                    default=[],
                ),
                limit=TARGET_PUBLICATIONS,
            )

        teacher.recent_publications = sorted(
            enriched,
            key=lambda publication: (publication.year, publication.title),
            reverse=True,
        )
        if self.log_progress:
            print(f"    [papers] {teacher.school} {teacher.name} publications={len(teacher.recent_publications)}")
            openalex_count = sum(1 for publication in teacher.recent_publications if publication.source == "OpenAlex")
            print(
                f"    [papers-openalex] {teacher.school} {teacher.name} added={openalex_added} openalex_publications={openalex_count}"
            )
            if dblp_added > 0:
                dblp_count = sum(1 for publication in teacher.recent_publications if publication.source == "DBLP")
                print(
                    f"    [papers-dblp] {teacher.school} {teacher.name} added={dblp_added} dblp_publications={dblp_count}"
                )
            if scholar_added > 0:
                scholar_count = sum(1 for publication in teacher.recent_publications if publication.source == "Google Scholar")
                print(
                    f"    [papers-scholar] {teacher.school} {teacher.name} added={scholar_added} scholar_publications={scholar_count}"
                )
            if scholar_web_added > 0:
                scholar_web_count = sum(
                    1 for publication in teacher.recent_publications if publication.source == "Google Scholar Web"
                )
                print(
                    f"    [papers-scholar-web] {teacher.school} {teacher.name} added={scholar_web_added} scholar_web_publications={scholar_web_count}"
                )
        return teacher

    @staticmethod
    def append_unique_publications(
        enriched: list[Publication],
        existing_titles: set[str],
        publications: list[Publication],
        limit: int,
    ) -> int:
        added = 0
        for publication in publications:
            if len(enriched) >= limit:
                break
            title_key = publication.title.casefold()
            if title_key in existing_titles:
                continue
            existing_titles.add(title_key)
            enriched.append(publication)
            added += 1
        return added

    def safe_call(self, teacher: Teacher, source: str, operation: str, func, default):
        try:
            return func()
        except Exception as exc:
            if self.log_progress:
                print(
                    f"    [papers-source-failed] {teacher.school} {teacher.name} source={source} operation={operation} reason={exc.__class__.__name__}"
                )
            return default

    def fetch_recent_works_scholar(self, teacher: Teacher) -> list[Publication]:
        if scholarly is None:
            return []

        canonical_name = self.canonicalize_teacher_name(teacher.name, teacher.school)
        school_aliases = SCHOOL_ALIASES.get(teacher.school, [])
        queries = [
            f"{canonical_name} {teacher.school}",
            canonical_name,
            *self.build_author_queries(canonical_name),
        ]

        best_author: dict[str, object] | None = None
        best_score = 0.0
        for query in dict.fromkeys(queries):
            try:
                candidates = scholarly.search_author(query)
            except Exception:
                continue

            for _ in range(5):
                try:
                    candidate = next(candidates)
                except StopIteration:
                    break
                except Exception:
                    break

                candidate_name = str(candidate.get("name") or "")
                affiliation = str(candidate.get("affiliation") or "")
                alias_score = 1.0 if any(alias.casefold() in affiliation.casefold() for alias in school_aliases) else 0.0
                cn_name_score = 1.0 if teacher.name and teacher.name in candidate_name else 0.0
                en_name_score = max(
                    SequenceMatcher(None, self.normalize_name(candidate_name), self.normalize_name(query)).ratio(),
                    SequenceMatcher(None, self.normalize_name(candidate_name), self.normalize_name(canonical_name)).ratio(),
                )
                score = alias_score * 2 + cn_name_score + en_name_score
                if score > best_score:
                    best_score = score
                    best_author = candidate

        if best_author is None or best_score < 1.5:
            return []

        try:
            filled_author = scholarly.fill(best_author, sections=["publications"])
        except Exception:
            return []

        publications: list[Publication] = []
        raw_pubs = filled_author.get("publications") or []
        for raw in raw_pubs[:80]:
            bib = raw.get("bib") or {}
            year_text = str(bib.get("pub_year") or bib.get("year") or "").strip()
            try:
                year = int(year_text)
            except ValueError:
                continue
            if not (YEAR_START <= year <= YEAR_END):
                continue

            title = self.clean_publication_title(str(bib.get("title") or ""))
            if not title:
                continue

            venue = self.clean_text(str(bib.get("journal") or bib.get("venue") or bib.get("publisher") or "Google Scholar"))
            venue_cf = venue.casefold()
            kind = "conference" if any(token in venue_cf for token in ["proc", "conf", "symposium", "workshop"]) else "journal"
            link = raw.get("pub_url") or raw.get("author_pub_id")

            publications.append(
                Publication(
                    title=title,
                    venue=venue,
                    year=year,
                    kind=kind,
                    source="Google Scholar",
                    link=str(link) if link else None,
                )
            )
        return publications

    def fetch_recent_works_scholar_web(self, teacher: Teacher) -> list[Publication]:
        canonical_name = self.canonicalize_teacher_name(teacher.name, teacher.school)
        queries = [
            f"{canonical_name} {teacher.school}",
            canonical_name,
            *self.build_author_queries(canonical_name),
        ]

        publications: list[Publication] = []
        seen_titles: set[str] = set()
        for query in dict.fromkeys([q.strip() for q in queries if q.strip()]):
            url = f"https://scholar.google.com/scholar?hl=en&q={quote_plus(query)}"
            html = self.cached_get_text(
                url,
                params=None,
                cache_bucket="scholar_web",
                cache_key=f"{teacher.school}:{canonical_name}:{query}",
            )
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select("div.gs_ri"):
                title_node = item.select_one("h3.gs_rt")
                if title_node is None:
                    continue
                title = self.clean_publication_title(title_node.get_text(" ", strip=True))
                if not title:
                    continue

                year = self.extract_year(item.select_one("div.gs_a").get_text(" ", strip=True) if item.select_one("div.gs_a") else "")
                if year is None or not (YEAR_START <= year <= YEAR_END):
                    continue

                title_key = title.casefold()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                meta_text = item.select_one("div.gs_a").get_text(" ", strip=True) if item.select_one("div.gs_a") else ""
                venue = self.clean_text(meta_text) or "Google Scholar"
                venue_cf = venue.casefold()
                kind = "conference" if any(token in venue_cf for token in ["proc", "conf", "symposium", "workshop"]) else "journal"
                link_node = title_node.select_one("a")
                link = link_node.get("href") if link_node else None

                publications.append(
                    Publication(
                        title=title,
                        venue=venue,
                        year=year,
                        kind=kind,
                        source="Google Scholar Web",
                        link=link,
                    )
                )
                if len(publications) >= 30:
                    return publications
        return publications

    def match_author_id(self, teacher: Teacher) -> str | None:
        canonical_name = self.canonicalize_teacher_name(teacher.name, teacher.school)
        queries = self.build_author_queries(canonical_name)
        aliases = SCHOOL_ALIASES.get(teacher.school, [])
        best_id: str | None = None
        best_score = 0.0

        for query in queries:
            payload = self.cached_get_json(
                OPENALEX_AUTHOR_URL,
                params={"search": query, "per-page": 8},
                cache_bucket="authors",
                cache_key=f"{teacher.school}:{teacher.name}:{query}",
            )
            results = payload.get("results", [])
            for item in results:
                display_name = item.get("display_name") or ""
                institutions = item.get("last_known_institutions") or []
                institution_names = [institution.get("display_name", "") for institution in institutions]
                institution_score = 1.0 if any(alias in institution_names for alias in aliases) else 0.0
                name_score = max(
                    SequenceMatcher(None, self.normalize_name(display_name), self.normalize_name(query)).ratio(),
                    SequenceMatcher(None, self.normalize_name(display_name), self.normalize_name(canonical_name)).ratio(),
                )
                score = institution_score * 2 + name_score + min((item.get("works_count") or 0) / 500, 0.5)
                if score > best_score:
                    best_score = score
                    best_id = item.get("id")

        return best_id if best_score >= 2.2 else None

    def match_dblp_pid(self, teacher: Teacher) -> str | None:
        canonical_name = self.canonicalize_teacher_name(teacher.name, teacher.school)
        queries = [canonical_name, *self.build_author_queries(canonical_name)]
        best_pid: str | None = None
        best_score = 0.0

        for query in dict.fromkeys(queries):
            payload = self.cached_get_json(
                DBLP_AUTHOR_URL,
                params={"q": query, "h": 8, "format": "json"},
                cache_bucket="dblp_authors",
                cache_key=f"{teacher.school}:{teacher.name}:{query}",
            )
            hits = (((payload.get("result") or {}).get("hits") or {}).get("hit") or [])
            if isinstance(hits, dict):
                hits = [hits]

            for hit in hits:
                info = hit.get("info") or {}
                author_name = str(info.get("author") or "")
                url = str(info.get("url") or "")
                match = re.search(r"/pid/(.+?)\\.html", url)
                if not match:
                    continue
                pid = unquote(match.group(1))
                score = max(
                    SequenceMatcher(None, self.normalize_name(author_name), self.normalize_name(canonical_name)).ratio(),
                    SequenceMatcher(None, self.normalize_name(author_name), self.normalize_name(query)).ratio(),
                )
                if score > best_score:
                    best_score = score
                    best_pid = pid

        return best_pid if best_score >= 0.74 else None

    def fetch_recent_works_dblp(self, teacher: Teacher) -> list[Publication]:
        pid = self.match_dblp_pid(teacher)
        if not pid:
            return []

        xml_text = self.cached_get_text(
            DBLP_PID_XML_URL.format(pid=pid),
            params=None,
            cache_bucket="dblp_pid",
            cache_key=pid,
        )
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        publications: list[Publication] = []
        for item in root.findall("./r/*"):
            year_text = self.element_text(item.find("year"))
            try:
                year = int(year_text)
            except ValueError:
                continue
            if not (YEAR_START <= year <= YEAR_END):
                continue

            title = self.clean_publication_title(self.element_text(item.find("title")))
            if not title:
                continue

            venue = self.element_text(item.find("journal")) or self.element_text(item.find("booktitle")) or "DBLP"
            link = self.element_text(item.find("ee")) or self.element_text(item.find("url"))
            kind = "journal" if item.tag == "article" else "conference" if item.tag in {"inproceedings", "proceedings"} else "other"
            publications.append(
                Publication(
                    title=title,
                    venue=venue,
                    year=year,
                    kind=kind,
                    source="DBLP",
                    link=link or None,
                )
            )
        return publications

    def fetch_recent_works(self, author_id: str) -> list[Publication]:
        payload = self.cached_get_json(
            OPENALEX_WORKS_URL,
            params={
                "filter": f"author.id:{author_id},from_publication_date:{YEAR_START}-01-01,to_publication_date:{YEAR_END}-12-31",
                "sort": "publication_date:desc",
                "per-page": 30,
            },
            cache_bucket="works",
            cache_key=author_id,
        )
        works = payload.get("results", [])
        publications: list[Publication] = []
        for work in works:
            title = (work.get("display_name") or "").strip()
            if not title:
                continue
            source = (work.get("primary_location") or {}).get("source") or {}
            venue = source.get("display_name") or "OpenAlex"
            year = work.get("publication_year") or 0
            publication_type = work.get("type") or "other"
            kind = "journal" if publication_type in {"article", "journal-article"} else "conference" if publication_type in {"proceedings-article", "conference"} else "other"
            publications.append(
                Publication(
                    title=title,
                    venue=venue,
                    year=year,
                    kind=kind,
                    source="OpenAlex",
                    link=work.get("id"),
                )
            )
        return publications

    def cached_get_json(
        self,
        url: str,
        params: dict[str, object] | None,
        cache_bucket: str,
        cache_key: str,
    ) -> dict[str, object]:
        cache_path = self.get_cache_path(cache_bucket, cache_key)
        if cache_path is not None and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        response = self.session.get(url, params=params, timeout=self.timeout)
        payload = response.json()
        if cache_path is not None:
            cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.05)
        return payload

    def cached_get_text(
        self,
        url: str,
        params: dict[str, object] | None,
        cache_bucket: str,
        cache_key: str,
    ) -> str:
        cache_path = self.get_cache_path(cache_bucket, cache_key)
        if cache_path is not None and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        response = self.session.get(url, params=params, timeout=self.timeout)
        text = response.text
        if cache_path is not None:
            cache_path.write_text(text, encoding="utf-8")
        time.sleep(0.05)
        return text

    def get_cache_path(self, cache_bucket: str, cache_key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()
        return self.cache_dir / cache_bucket / f"{digest}.json"

    def build_author_queries(self, name: str) -> list[str]:
        romanized = self.romanize(name)
        parts = romanized.split()
        queries = [romanized]
        if len(parts) >= 2:
            queries.append(f"{parts[-1]} {' '.join(parts[:-1])}")
            queries.append(f"{' '.join(parts[:-1])} {parts[-1]}")
        return list(dict.fromkeys([query.strip() for query in queries if query.strip()]))

    @staticmethod
    def romanize(name: str) -> str:
        return " ".join(part.capitalize() for part in lazy_pinyin(name))

    @staticmethod
    def normalize_name(text: str) -> str:
        return re.sub(r"[^a-z]", "", text.casefold())

    @staticmethod
    def canonicalize_teacher_name(name: str, school: str) -> str:
        text = (name or "").strip()
        if not text:
            return text
        text = re.split(r"[-–—|｜,，(（]", text, maxsplit=1)[0].strip()
        for token in [school, *SCHOOL_ALIASES.get(school, [])]:
            if token:
                text = text.replace(token, "").strip()
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def extract_year(text: str) -> int | None:
        match = re.search(r"(19|20)\d{2}", text or "")
        if not match:
            return None
        try:
            return int(match.group(0))
        except ValueError:
            return None

    @staticmethod
    def element_text(node: ET.Element | None) -> str:
        if node is None:
            return ""
        return " ".join(part.strip() for part in node.itertext() if part and part.strip())

    @staticmethod
    def clean_publication_title(text: str) -> str:
        cleaned = re.sub(r"\[[^\]]+\]", "", text)
        return re.sub(r"\s+", " ", cleaned).strip(" .")

    @staticmethod
    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()
