"""站点注册表：新增站点 = 在 sites/ 下加模块并在 SITES 注册。"""

from . import bilibili, generic

SITES = [bilibili.SITE, generic.SITE]


def detect_site(url: str) -> dict:
    """按注册顺序匹配第一个站点；都不匹配时归为通用。"""
    for site in SITES:
        if site["match"](url):
            return site
    return generic.SITE
