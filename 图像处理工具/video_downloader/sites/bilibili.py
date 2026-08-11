"""哔哩哔哩站点：识别 + 引擎偏好。"""

BILIBILI_DOMAINS = ("bilibili.com", "b23.tv", "bili2233.cn", "biliintl.com")


def match(url: str) -> bool:
    return any(domain in url.lower() for domain in BILIBILI_DOMAINS)


SITE = {
    "name": "bilibili",
    "display": "哔哩哔哩",
    "match": match,
    # B 站优先 BBDown（多P/合集/可登录高画质），缺失或失败时回退 yt-dlp
    "engines": ["bbdown", "yt-dlp"],
}
