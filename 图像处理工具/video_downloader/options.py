"""下载选项：UI 无关的单一事实来源。

新增下载选项 = DownloadOptions 加一个字段 + FORM_FIELDS 加一行。
CLI 的 argparse 参数和 TUI 的表单控件都由 FORM_FIELDS 自动生成，
因此新增选项时两个界面同时出现对应输入，无需手改两处。
"""

from dataclasses import dataclass, fields
import re

_SELECTION_RE = re.compile(r"^((\d+(-\d+)?)(,\d+(-\d+)?)*|ALL|LAST)$", re.IGNORECASE)
AUDIO_FORMATS = {"mp3", "m4a", "flac", "wav"}
VIDEO_FORMATS = {"mp4", "mkv", "webm"}


def validate_selection(selection: str) -> bool:
    """校验分P/选集范围：1,2 / 3-5 / ALL / LAST；空视为合法。"""
    return not selection or bool(_SELECTION_RE.match(selection.strip()))


def selection_within(items_count: int, selection: str) -> bool:
    """校验选择是否在 1..items_count 内；支持 1,2 / 3-5 / ALL / LAST。"""
    sel = selection.strip().upper()
    if sel in ("", "ALL", "LAST"):
        return True
    for part in sel.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            if not (start.isdigit() and end.isdigit()):
                return False
            start, end = int(start), int(end)
            if not (1 <= start <= end <= items_count):
                return False
        elif not part.isdigit() or not (1 <= int(part) <= items_count):
            return False
    return True


@dataclass
class DownloadOptions:
    audio: bool = False  # 仅下载音频
    danmaku: bool = False  # 同时下载弹幕（BBDown）
    selection: str = ""  # 分P/选集范围：1,2 / 3-5 / ALL
    audio_format: str = ""  # 音频格式：mp3/m4a/flac/wav（空=默认）
    quality: str = ""  # 画质：360P/480P/720P/1080P/4K（空=默认）
    output_format: str = ""  # 视频封装：mp4/mkv/webm（空=默认）
    save_dir: str = ""  # 空 = 使用配置默认


def normalize_output(options: DownloadOptions) -> None:
    """统一"输出格式"语义：音频格式 => 仅音频；视频格式 => 视频封装。"""
    fmt = (options.output_format or "").strip().lower()
    if fmt in AUDIO_FORMATS:
        options.audio = True
        options.audio_format = fmt
        options.output_format = ""
    elif fmt in VIDEO_FORMATS:
        options.audio = False
        options.audio_format = ""
        options.output_format = fmt


# (dest, label, kind, cli_flags, help, placeholder)
FORM_FIELDS = [
    ("audio", "仅音频", "bool", ("-a", "--audio"), "仅下载音频", None),
    ("danmaku", "下载弹幕", "bool", ("-d", "--danmaku"), "同时下载弹幕（BBDown，输出 XML/ASS）", None),
    ("selection", "选集范围", "str", ("-p", "--items"), "分P/选集范围（番剧/合集/多P）", "1,2 / 3-5 / ALL"),
    ("quality", "清晰度", "str", ("-q", "--quality"), "画质：360P/480P/720P/1080P/4K", "360P~4K"),
    ("output_format", "输出格式", "str", ("-f", "--output-format"), "输出格式：视频 mp4/mkv/webm；音频 mp3/m4a/flac/wav（音频即仅音频）", "mp4/mkv/webm/mp3/m4a/flac/wav"),
    ("save_dir", "保存目录", "str", ("-o", "--dir"), "保存目录（默认见设置）", "~/Videos/未分类"),
]


def options_from_args(args) -> DownloadOptions:
    """从 argparse 结果构造 DownloadOptions。"""
    options = DownloadOptions()
    for field in fields(options):
        value = getattr(args, field.name, None)
        setattr(options, field.name, value if value is not None else "")
    return options
