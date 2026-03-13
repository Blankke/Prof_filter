from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET

from app.models import Teacher
from crawler.core.models import FetchedPage
from crawler.spiders.base import BaseSchoolSpider


class ZjuSpider(BaseSchoolSpider):
    school_id = "zju"
    display_name = "浙江大学"
    default_roster_url = "http://www.cs.zju.edu.cn/_upload/article/files/ce/9d/5b7a5fba4904a1b7e5e8b1d11ad9/440fa093-de6f-41e1-a80b-dd65a34167d2.xlsx"

    def normalize_profile_links(self, page: FetchedPage) -> list[str]:
        return [self.seed.faculty_entry or self.default_roster_url]

    def crawl_teachers(self, limit: int | None = None) -> list[Teacher]:
        roster_url = self.seed.faculty_entry or self.default_roster_url
        names = self.load_names_from_xlsx(roster_url)
        if limit is not None:
            names = names[:limit]

        teachers: list[Teacher] = []
        for index, name in enumerate(names, start=1):
            teachers.append(
                Teacher(
                    id=f"zju-{name}-{index}",
                    school_id=self.school_id,
                    school=self.display_name,
                    faculty="计算机科学与技术学院",
                    name=name,
                    title="",
                    lab=None,
                    lab_status="not_mentioned",
                    homepage=None,
                    research_areas=[],
                    recent_publications=[],
                    summary="名单来源：浙江大学计算机学院博导/硕导名录 xlsx",
                )
            )
        return teachers

    def load_names_from_xlsx(self, url: str) -> list[str]:
        response = self.fetcher.session.get(url, timeout=self.fetcher.timeout_seconds, allow_redirects=True)
        workbook = zipfile.ZipFile(io.BytesIO(response.content))
        shared_strings = self.read_shared_strings(workbook)
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in workbook.namelist():
            for candidate in workbook.namelist():
                if candidate.startswith("xl/worksheets/sheet") and candidate.endswith(".xml"):
                    sheet_name = candidate
                    break

        root = ET.fromstring(workbook.read(sheet_name))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        names: list[str] = []
        seen: set[str] = set()
        for row in root.findall(".//x:sheetData/x:row", namespace):
            for cell in row.findall("x:c", namespace):
                value = self.read_cell_value(cell, namespace, shared_strings)
                candidate = self.normalize_name(value)
                if not candidate:
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                names.append(candidate)
        return names

    @staticmethod
    def read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in workbook.namelist():
            return []
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        strings: list[str] = []
        for item in root.findall("x:si", namespace):
            text = "".join(node.text or "" for node in item.findall(".//x:t", namespace))
            strings.append(text)
        return strings

    @staticmethod
    def read_cell_value(cell: ET.Element, namespace: dict[str, str], shared_strings: list[str]) -> str:
        value_node = cell.find("x:v", namespace)
        if value_node is None:
            return ""
        value = value_node.text or ""
        if cell.get("t") == "s":
            try:
                return shared_strings[int(value)]
            except Exception:
                return ""
        return value

    @staticmethod
    def normalize_name(value: str) -> str | None:
        text = re.sub(r"\s+", "", value or "")
        if not text:
            return None
        if re.search(r"\d", text):
            return None
        blocked_tokens = {
            "学术学位",
            "专业学位",
            "序号",
            "博导",
            "硕导",
            "院外",
            "非全职在岗",
        }
        if text in blocked_tokens:
            return None
        if len(text) < 2 or len(text) > 4:
            return None
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text):
            return None
        return text
