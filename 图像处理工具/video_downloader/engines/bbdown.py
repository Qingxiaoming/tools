"""BBDown 引擎：B 站专用（多P/合集、可扫码登录高画质）。"""

import subprocess
from pathlib import Path

from ..config import find_tool
from ..console import dim, error, info, ok
from .base import DownloadEngine, DownloadResult, EngineUnavailableError


class BBDownEngine(DownloadEngine):
    name = "bbdown"
    display_name = "BBDown（B 站专用）"

    def available(self) -> bool:
        return find_tool("BBDown") is not None

    def download(self, url: str, dest: Path, audio_only: bool = False) -> DownloadResult:
        bbdown = find_tool("BBDown")
        if not bbdown:
            raise EngineUnavailableError(
                "未找到 BBDown。安装方式：dotnet tool install --global BBDown，"
                "或从 GitHub releases 下载二进制放到 PATH。"
            )

        dest.mkdir(parents=True, exist_ok=True)
        command = [str(bbdown)]
        if audio_only:
            command.append("--audio-only")
        command += ["--work-dir", str(dest), "--skip-cover", "--skip-subtitle", url]

        info(f"使用 {self.display_name} 下载" + ("（仅音频，保留原始格式）" if audio_only else ""))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        for line in process.stdout:
            dim(line.rstrip())
        process.wait()

        if process.returncode != 0:
            error(f"BBDown 下载失败，返回码: {process.returncode}")
            return DownloadResult(False, self.name, message=f"BBDown 返回码 {process.returncode}")

        ok("下载完成！")
        return DownloadResult(True, self.name)
