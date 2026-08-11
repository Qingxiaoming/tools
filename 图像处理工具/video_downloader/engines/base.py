"""下载引擎抽象与结果约定。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


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
    def download(self, url: str, dest: Path, audio_only: bool = False) -> DownloadResult:
        """下载 url 到 dest；依赖缺失时抛 EngineUnavailableError。"""
