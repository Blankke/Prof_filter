from __future__ import annotations

from crawler.spiders.base import BaseSchoolSpider
from crawler.spiders.fudan import FudanSpider
from crawler.spiders.nju import NjuSpider
from crawler.spiders.pku import PkuSpider
from crawler.spiders.ruc import RucSpider
from crawler.spiders.sjtu import SjtuSpider
from crawler.spiders.tsinghua import TsinghuaSpider
from crawler.spiders.zju import ZjuSpider


SPIDER_REGISTRY: dict[str, type[BaseSchoolSpider]] = {
    "fudan": FudanSpider,
    "nju": NjuSpider,
    "pku": PkuSpider,
    "ruc": RucSpider,
    "sjtu": SjtuSpider,
    "tsinghua": TsinghuaSpider,
    "zju": ZjuSpider,
}
