import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Windows 下隐藏 FFmpeg 子进程黑框
SUBPROCESS_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# 基础输出目录（按需自行修改）
TOOLBOX_OUTPUT_ROOT: Path = Path(r"E:\toolbox输出")

SEGMENT_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "多段截取"
CROP_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "画幅裁剪"
MERGE_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "合并输出"
DOC_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "文档生成"

DOC_TRANSFER_DOC_DIR: Path = Path(
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~"
)
DOC_TRANSFER_MEDIA_DIR: Path = Path(
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~\附件"
)

# 录屏整理根目录（每周一个子文件夹）
WEEKLY_OUTPUT_ROOT: Path = Path(r"E:\录屏整理")


STANDARD_VIDEO_PATTERN = re.compile(r'^[^\\/:*?"<>|\s]+\.mp4$')
VIDEO_NATURE_LIST = ['突袭', '无解', '待压', '剧情', '他人记录', '剿灭', '沙盘', '普通']

# 录屏整理前缀模板，支持 {year} / {week}
WEEKLY_PREFIX_TEMPLATE: str = "{year}-{week:02d}w"

_iso = datetime.today().isocalendar()
WEEKLY_YEAR: int = _iso.year
WEEKLY_WEEK: int = _iso.week
WEEKLY_SUBDIR_NAME: str = f"{WEEKLY_YEAR}_{WEEKLY_WEEK:02d}"

WEEKLY_OUTPUT_DIR: Path = WEEKLY_OUTPUT_ROOT / WEEKLY_SUBDIR_NAME


# 跨标签视频传递模式："overwrite" 或 "append"
CROSS_TAB_TRANSFER_MODE: str = "overwrite"


try:
    from plyer import notification  # type: ignore
    ENABLE_NOTIFICATION = True
except Exception:
    notification = None  # type: ignore
    ENABLE_NOTIFICATION = False


def ensure_dirs_exist() -> None:
    """确保所有输出目录存在。"""
    for path in (
        TOOLBOX_OUTPUT_ROOT,
        SEGMENT_OUTPUT_DIR,
        CROP_OUTPUT_DIR,
        MERGE_OUTPUT_DIR,
        DOC_OUTPUT_DIR,
        DOC_TRANSFER_DOC_DIR,
        DOC_TRANSFER_MEDIA_DIR,
        WEEKLY_OUTPUT_ROOT,
        WEEKLY_OUTPUT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
