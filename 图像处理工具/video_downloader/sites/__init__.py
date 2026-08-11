"""站点注册表：识别 → 解析 两段式。

新增站点 = 在 sites/ 下加模块，提供 match(url)/parse(url)/engines 并注册。
识别负责路由，解析负责把 URL 变成干净的 SiteEntity。
"""

from . import bilibili, generic
from .entity import SiteEntity

SITES = [bilibili.SITE, generic.SITE]


def detect_site(url: str) -> dict:
    """按注册顺序匹配第一个站点；都不匹配时归为通用。"""
    for site in SITES:
        if site["match"](url):
            return site
    return generic.SITE


def parse_url(url: str) -> SiteEntity:
    """一站式：识别站点并解析 URL。"""
    return detect_site(url)["parse"](url)
