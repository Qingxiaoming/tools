"""哔哩哔哩站点：识别 + 解析 + 引擎偏好。

解析层职责：
- 清洗追踪参数（spm_id_from / vd_source 等），保留功能参数（p 分P / t 起始时间）
- 提取实体：video(BV/av)、bangumi(ep/ss)、collection(/list/)、favorite(/medialist/)
- b23.tv 短链展开（网络请求，5s 超时，失败回退原样）

解析按"URL 类型分发表"组织：每种类型一个短函数，注册进 _PATH_PARSERS。
新增类型 = 写一个 (segments) -> (type, id) 函数并注册，无需改 parse 主流程。

规模控制：本文件超过约 250 行时，拆为 sites/bilibili/ 子包
（video.py / bangumi.py / collection.py / shortlink.py + __init__ 分发）。
注册表接口不依赖文件布局，拆分不影响 cli / engines。
"""

import re
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .entity import SiteEntity

BILIBILI_DOMAINS = ("bilibili.com", "b23.tv", "bili2233.cn", "biliintl.com")
# 仅保留的功能参数；其余视为追踪参数一律丢弃
_KEEP_QUERY_KEYS = ("p", "t")
_BARE_ID_RE = re.compile(r"^(BV[0-9A-Za-z]{10}|av\d+)$")


def _expand_shortlink(url: str) -> str:
    """跟随 b23.tv 302 重定向返回最终 URL；失败返回原样。"""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.geturl()
    except Exception:
        return url


def _parse_video(segments: list[str]) -> tuple[str, str]:
    return "video", segments[1] if len(segments) > 1 else ""


def _parse_bangumi(segments: list[str]) -> tuple[str, str]:
    if len(segments) >= 3 and segments[1] == "play":
        return "bangumi", segments[2]  # ep123456 / ss12345
    return "unknown", ""


def _parse_list(segments: list[str]) -> tuple[str, str]:
    return "collection", segments[1] if len(segments) > 1 else ""


def _parse_medialist(segments: list[str]) -> tuple[str, str]:
    return "favorite", segments[2] if len(segments) > 2 else (segments[1] if len(segments) > 1 else "")


# URL 类型分发表：新增类型 = 写一个解析函数 + 在这里注册
_PATH_PARSERS = {
    "video": _parse_video,
    "bangumi": _parse_bangumi,
    "list": _parse_list,
    "medialist": _parse_medialist,
}


def _classify(parsed) -> tuple[str, str]:
    """返回 (type, id)；裸 BV/av ID 归为 video。"""
    segments = [seg for seg in parsed.path.split("/") if seg]
    if not segments:
        return "unknown", ""
    parser = _PATH_PARSERS.get(segments[0])
    if parser:
        return parser(segments)
    if not parsed.scheme and _BARE_ID_RE.match(parsed.path):
        # BBDown/yt-dlp 也支持直接传裸 ID
        return "video", parsed.path
    return "unknown", ""


def _parse_bilibili_url(url: str) -> SiteEntity:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    entity_type, entity_id = _classify(parsed)

    keep = {}
    for key in _KEEP_QUERY_KEYS:
        value = query.get(key, [""])[0]
        if value:
            keep[key] = value
    page = keep.get("p", "")
    clean_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            urlencode(keep) if keep else "",
            "",
        )
    )
    return SiteEntity(
        site="bilibili",
        display="哔哩哔哩",
        type=entity_type,
        id=entity_id,
        clean_url=clean_url,
        raw_url=url,
        p=page,
    )


def parse(url: str) -> SiteEntity:
    if "b23.tv" in url.lower():
        expanded = _expand_shortlink(url)
        if expanded != url:
            entity = _parse_bilibili_url(expanded)
            entity.raw_url = url
            entity.note = f"短链已展开: {expanded}"
            return entity
        return SiteEntity(
            site="bilibili",
            display="哔哩哔哩",
            type="shortlink",
            clean_url=url,
            raw_url=url,
            note="短链展开失败，将原样传给下载引擎",
        )
    return _parse_bilibili_url(url)


def match(url: str) -> bool:
    """域名命中，或裸 BV/av ID（BBDown/yt-dlp 也接受）。"""
    return any(domain in url.lower() for domain in BILIBILI_DOMAINS) or bool(
        _BARE_ID_RE.match(url.strip())
    )


SITE = {
    "name": "bilibili",
    "display": "哔哩哔哩",
    "match": match,
    "parse": parse,
    # B 站优先 BBDown（多P/合集/可登录高画质），缺失或失败时回退 yt-dlp
    "engines": ["bbdown", "yt-dlp"],
}
