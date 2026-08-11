"""通用站点：YouTube 等一切 yt-dlp 支持的网站。

通用站点依赖 query 参数（如 YouTube 的 v=），因此解析层只去掉 fragment，
不清洗 query；后续可对具体站点加专属解析模块。
"""

from urllib.parse import urlparse, urlunparse

from .entity import SiteEntity


def match(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def parse(url: str) -> SiteEntity:
    parsed = urlparse(url)
    clean_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, "")
    )
    return SiteEntity(
        site="generic",
        display="通用视频网站",
        type="unknown",
        clean_url=clean_url,
        raw_url=url,
    )


SITE = {
    "name": "generic",
    "display": "通用视频网站",
    "match": match,
    "parse": parse,
    "engines": ["yt-dlp"],
}
