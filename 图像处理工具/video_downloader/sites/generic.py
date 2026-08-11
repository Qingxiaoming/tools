"""通用站点：YouTube 等一切 yt-dlp 支持的网站。"""


def match(url: str) -> bool:
    return url.startswith(("http://", "https://"))


SITE = {
    "name": "generic",
    "display": "通用视频网站",
    "match": match,
    "engines": ["yt-dlp"],
}
