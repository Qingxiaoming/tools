"""下载引擎注册表：新增引擎 = 在 engines/ 加实现并在此注册。"""

from .base import DownloadEngine, DownloadResult, EngineUnavailableError
from .bbdown import BBDownEngine
from .ytdlp import YtDlpEngine

ENGINES: dict[str, DownloadEngine] = {
    engine.name: engine for engine in (YtDlpEngine(), BBDownEngine())
}


def resolve_engine(site: dict) -> DownloadEngine | None:
    """按站点的引擎偏好顺序，返回第一个可用的引擎。"""
    for name in site.get("engines", []):
        engine = ENGINES.get(name)
        if engine and engine.available():
            return engine
    return None


def describe_engines() -> list[tuple[str, str, bool]]:
    return [(name, engine.display_name, engine.available()) for name, engine in ENGINES.items()]
