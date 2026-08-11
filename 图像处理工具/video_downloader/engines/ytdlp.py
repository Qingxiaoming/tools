"""yt-dlp 通用引擎：支持 B 站及 YouTube 等 1000+ 网站。"""

import glob
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from ..config import find_tool, load_cookie
from ..console import dim, error, info, ok, warn
from .base import (
    DownloadEngine,
    DownloadResult,
    EngineUnavailableError,
    EpisodeItem,
    new_files,
    snapshot_files,
)


class YtDlpEngine(DownloadEngine):
    name = "yt-dlp"
    display_name = "yt-dlp（通用）"
    _QUALITY_FORMATS = {
        "360P": "best[height<=360]/bestvideo[height<=360]+bestaudio/best",
        "480P": "best[height<=480]/bestvideo[height<=480]+bestaudio/best",
        "720P": "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
        "1080P": "best[height<=1080]/bestvideo[height<=1080]+bestaudio/best",
        "4K": "bestvideo[height<=2160]+bestaudio/best",
    }
    _HEIGHT_TO_QUALITY = {
        360: "360P",
        480: "480P",
        720: "720P",
        1080: "1080P",
        2160: "4K",
        4320: "8K",
    }

    def available(self) -> bool:
        return find_tool("yt-dlp") is not None

    def _cookie_args(self) -> list[str]:
        cookie = load_cookie()
        return ["--add-header", f"Cookie: {cookie}"] if cookie else []

    def list_items(self, url: str) -> list[EpisodeItem] | None:
        """用 yt-dlp flat-playlist 元数据枚举分P/选集（多P/番剧/合集/普通播放列表）。"""
        try:
            result = subprocess.run(
                ["yt-dlp", *self._cookie_args(), "--flat-playlist", "--dump-json", "--no-warnings", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        items: list[EpisodeItem] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                info = json.loads(line)
            except Exception:
                continue
            index = info.get("playlist_index") or len(items) + 1
            title = info.get("title") or info.get("id") or f"#{index}"
            items.append(EpisodeItem(index=int(index), title=str(title)))
        return items or None

    def list_qualities(self, url: str) -> list[str] | None:
        """解析 yt-dlp -F 的分辨率，返回实际可用的清晰度标签。"""
        try:
            result = subprocess.run(
                ["yt-dlp", *self._cookie_args(), "-F", "--no-warnings", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        found: set[str] = set()
        for line in result.stdout.splitlines():
            for token in line.split():
                match = re.match(r"(\d{3,4})x(\d{3,4})$", token)
                if match:
                    for number in (int(match.group(1)), int(match.group(2))):
                        quality = self._HEIGHT_TO_QUALITY.get(number)
                        if quality:
                            found.add(quality)
        order = ["360P", "480P", "720P", "1080P", "4K", "8K"]
        return [q for q in order if q in found] or None

    # ---- 工具方法 ----

    def _stream(self, command: list[str]) -> int:
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
        return process.returncode

    def _fetch_info(self, url: str) -> dict | None:
        info("正在获取视频信息...")
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-playlist", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as e:
            warn(f"获取视频信息失败: {e}")
            return None
        if result.returncode != 0:
            warn("无法获取视频信息")
            return None
        try:
            return json.loads(result.stdout)
        except Exception as e:
            warn(f"解析视频信息失败: {e}")
            return None

    @staticmethod
    def _valid_date(date_str: str) -> bool:
        if not date_str or date_str == "未知" or len(date_str) != 8:
            return False
        try:
            year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            return 1900 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False

    def _filename_template(self, video_info: dict | None) -> str:
        """上传日期+时间 > 日期+系统时间 > 纯系统时间。"""
        current = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not video_info:
            warn(f"无视频信息，使用系统时间: {current}")
            return current
        upload_date = video_info.get("upload_date")
        if not self._valid_date(upload_date):
            warn(f"无有效上传日期，使用系统时间: {current}")
            return current
        upload_time = video_info.get("upload_time")
        if upload_time and upload_time != "未知":
            template = f"{upload_date}_{upload_time}"
            ok(f"使用视频元数据: {template}")
            return template
        template = f"{upload_date}_{current.split('_')[1]}"
        ok(f"使用视频日期+系统时间: {template}")
        return template

    @staticmethod
    def _cleanup_temp(dest: Path, template: str) -> None:
        patterns = (
            f"{template}*.part",
            f"{template}*.part*",
            f"{template}*.ytdl",
            f"{template}*.ytdl*",
            f"{template}*.aria2",
            f"{template}*.aria2*",
            f"{template}*.temp",
            f"{template}*.tmp",
        )
        removed = False
        for pattern in patterns:
            for temp_path in glob.glob(str(dest / pattern)):
                if any(marker in temp_path for marker in (".part", ".ytdl", ".aria2", ".temp", ".tmp")):
                    try:
                        Path(temp_path).unlink()
                        removed = True
                    except Exception:
                        pass
        if removed:
            ok("已清理临时文件")

    # ---- 主流程 ----

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
        yt_dlp = find_tool("yt-dlp")
        if not yt_dlp:
            raise EngineUnavailableError("未找到 yt-dlp，请先安装：pip install -U yt-dlp")

        dest.mkdir(parents=True, exist_ok=True)
        before = snapshot_files(dest)
        template = self._filename_template(self._fetch_info(url))

        command = [str(yt_dlp), *self._cookie_args()]
        if audio_only:
            command += ["-x", "--audio-format", audio_format or "mp3"]
        if quality:
            command += ["-f", self._QUALITY_FORMATS.get(quality.upper(), quality)]
        if output_format:
            command += ["--merge-output-format", output_format]
        if selection and selection.lower() != "all":
            command += ["--playlist-items", selection]
        else:
            command += ["--no-playlist"]
        command += ["-P", str(dest), "-o", f"{template}.%(ext)s", url]

        info(f"使用 {self.display_name} 下载" + ("（仅音频 MP3）" if audio_only else ""))
        code = self._stream(command)
        if code != 0:
            error(f"下载失败，返回码: {code}")
            return DownloadResult(False, self.name, message=f"yt-dlp 返回码 {code}")

        self._cleanup_temp(dest, template)

        produced = new_files(dest, before)
        if not produced:
            error("未产生任何文件（链接可能无效，或内容不可下载）")
            return DownloadResult(False, self.name, message="无文件产出")

        ok("下载完成！")
        return DownloadResult(True, self.name, files=produced)
