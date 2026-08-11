"""下载引擎抽象与结果约定。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EpisodeItem:
    """一个分P/选集条目。"""

    index: int
    title: str


def snapshot_files(dest: Path) -> dict[str, int]:
    """记录目录内所有文件（含子目录）的 (路径, mtime_ns)，用于检测下载产出。"""
    result: dict[str, int] = {}
    if not dest.exists():
        return result
    for path in dest.rglob("*"):
        if path.is_file():
            try:
                result[str(path)] = path.stat().st_mtime_ns
            except OSError:
                pass
    return result


def new_files(dest: Path, before: dict[str, int]) -> list[Path]:
    """对比快照，返回本次新增或更新的文件。"""
    after = snapshot_files(dest)
    return [Path(name) for name, mtime in after.items() if name not in before or before[name] != mtime]


@dataclass
class DownloadResult:
    success: bool
    engine: str
    message: str = ""
    files: list[Path] = field(default_factory=list)


class EngineUnavailableError(RuntimeError):
    """引擎依赖缺失或不可用。"""


class DownloadEngine(ABC):
    name: str = "base"
    display_name: str = "基础引擎"

    @abstractmethod
    def available(self) -> bool:
        """依赖是否齐全。"""

    @abstractmethod
    def download(
        self,
        url: str,
        dest: Path,
        audio_only: bool = False,
        danmaku: bool = False,
        selection: str = "",
        quality: str = "",
        output_format: str = "",
        audio_format: str = "",
    ) -> DownloadResult:
        """下载 url 到 dest；依赖缺失时抛 EngineUnavailableError。

        danmaku: 同时下载弹幕（仅支持的引擎）
        selection: 分P/选集范围，如 "1,2" / "3-5" / "ALL"
        quality: 画质标签，如 "1080P" / "4K"
        output_format: 视频封装，如 "mp4" / "mkv" / "webm"
        audio_format: 仅音频时的输出格式，如 "mp3" / "m4a"
        """

    def list_items(self, url: str) -> list[EpisodeItem] | None:
        """返回可下载的分P/选集列表；不支持或失败返回 None（调用方退化为语法校验）。"""
        return None

    def list_qualities(self, url: str) -> list[str] | None:
        """返回该内容实际可用的清晰度标签（如 360P/480P/1080P/4K）；失败返回 None。"""
        return None
