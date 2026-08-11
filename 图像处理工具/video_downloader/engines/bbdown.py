"""BBDown 引擎：B 站专用（多P/合集、可扫码登录高画质）。"""

import re
import subprocess
from pathlib import Path

from ..config import find_tool, load_cookie
from ..console import dim, error, info, ok
from .base import (
    DownloadEngine,
    DownloadResult,
    EngineUnavailableError,
    EpisodeItem,
    new_files,
    snapshot_files,
)

_AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "flac": ["-c:a", "flac"],
    "wav": ["-c:a", "pcm_s16le"],
}
_PAGE_LINE_RE = re.compile(r"P(\d+):\s*\[\d+\]\s*\[([^\]]*)\]")
_QUALITY_LINE_RE = re.compile(r"\[((?:\d{3,4}P|\dK)[^\]]*)\]")
_QUALITY_ORDER = ["360P", "480P", "720P", "1080P", "4K", "8K"]


class BBDownEngine(DownloadEngine):
    name = "bbdown"
    display_name = "BBDown（B 站专用）"

    def available(self) -> bool:
        return find_tool("BBDown") is not None

    def _cookie_args(self) -> list[str]:
        cookie = load_cookie()
        return ["-c", cookie] if cookie else []

    def list_items(self, url: str) -> list[EpisodeItem] | None:
        """解析 BBDown -info 输出的 P 行，枚举分P/选集（含番剧 ss）。"""
        bbdown = find_tool("BBDown")
        if not bbdown:
            return None
        try:
            result = subprocess.run(
                [str(bbdown), *self._cookie_args(), "-info", "--show-all", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        items: list[EpisodeItem] = []
        for line in result.stdout.splitlines():
            match = _PAGE_LINE_RE.search(line)
            if match:
                items.append(EpisodeItem(index=int(match.group(1)), title=match.group(2).strip()))
        return items or None

    def list_qualities(self, url: str) -> list[str] | None:
        """解析 BBDown -info 的流信息，返回实际可用的清晰度标签。"""
        bbdown = find_tool("BBDown")
        if not bbdown:
            return None
        try:
            result = subprocess.run(
                [str(bbdown), *self._cookie_args(), "-info", "--show-all", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        found: set[str] = set()
        for line in result.stdout.splitlines():
            for match in _QUALITY_LINE_RE.finditer(line):
                tag = match.group(1).split()[0]
                found.add(tag)
        ordered = [q for q in _QUALITY_ORDER if q in found]
        return ordered or None

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
        bbdown = find_tool("BBDown")
        if not bbdown:
            raise EngineUnavailableError(
                "未找到 BBDown。安装方式：dotnet tool install --global BBDown，"
                "或从 GitHub releases 下载二进制放到 PATH。"
            )

        dest.mkdir(parents=True, exist_ok=True)
        before = snapshot_files(dest)
        command = [str(bbdown), *self._cookie_args()]
        if audio_only:
            command.append("--audio-only")
        if danmaku:
            command.append("--download-danmaku")
        if selection:
            command += ["-p", selection]
        if quality:
            command += ["-q", quality]
        command += ["--work-dir", str(dest), "--skip-cover", "--skip-subtitle", url]

        extras = []
        if audio_only:
            extras.append("仅音频")
        if danmaku:
            extras.append("含弹幕")
        if selection:
            extras.append(f"选集 {selection}")
        if quality:
            extras.append(f"画质 {quality}")
        if output_format and output_format.lower() != "mp4":
            warn("BBDown 固定输出 mp4/m4a 封装，封装选项仅对 yt-dlp 生效")
        info(f"使用 {self.display_name} 下载" + (f"（{'，'.join(extras)}）" if extras else ""))
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

        if audio_only and audio_format and not self._convert_audio(dest, audio_format):
            warn(f"音频转码为 {audio_format} 失败（已保留原始格式）")

        produced = new_files(dest, before)
        if not produced:
            error("未产生任何文件（选集可能无效，或内容不可下载）")
            return DownloadResult(False, self.name, message="无文件产出")

        ok("下载完成！")
        return DownloadResult(True, self.name, files=produced)

    @staticmethod
    def _convert_audio(dest: Path, audio_format: str) -> bool:
        """把刚下载的音频（通常是 m4a）转成目标格式；找不到/失败返回 False。"""
        codec = _AUDIO_CODECS.get(audio_format.lower())
        ffmpeg = find_tool("ffmpeg")
        if not codec or not ffmpeg:
            return False
        candidates = sorted(
            (p for p in dest.iterdir() if p.suffix.lower() in (".m4a", ".aac", ".flac", ".wav", ".mp3", ".m4s")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return False
        source = candidates[0]
        target = source.with_suffix(f".{audio_format.lower()}")
        try:
            result = subprocess.run(
                [str(ffmpeg), "-y", "-i", str(source), *codec, str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                return False
            if target.exists() and target != source:
                source.unlink()
            return True
        except Exception:
            return False
