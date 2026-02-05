import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Windows 下隐藏 FFmpeg 子进程的黑框
SUBPROCESS_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ------------------ 基础配置（可自行修改）------------------
# 建议将这些目录改成你自己的磁盘路径

# 视频工具箱主输出根目录（多段截取 / 画幅裁剪 / 合并输出 / 文档生成）
TOOLBOX_OUTPUT_ROOT: Path = Path(r"E:\toolbox输出")

# 多段截取输出目录
SEGMENT_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "多段截取"

# 画幅裁剪输出目录
CROP_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "画幅裁剪"

# 视频合并输出目录
MERGE_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "合并输出"

# 文档生成输出目录（存放 md 文档）
DOC_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / "文档生成"

# 文档转运目标目录（生成后的 md 将被剪切到此处）
DOC_TRANSFER_DOC_DIR: Path = Path(
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~"
)

# 文档对应视频转运目标目录（引用的视频文件将被剪切到此处）
DOC_TRANSFER_MEDIA_DIR: Path = Path(
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~\附件"
)

# 录屏整理根目录（每周会在此目录下创建一个子文件夹）
WEEKLY_OUTPUT_ROOT: Path = Path(r"E:\录屏整理")


# ------------------ 业务常量 ------------------
# 标准视频文件名正则
STANDARD_VIDEO_PATTERN = re.compile(r'^[^\\/:*?"<>|\s]+\.mp4$')

# 关卡性质列表
VIDEO_NATURE_LIST = ['突袭', '无解', '待压', '剧情', '他人记录', '剿灭', '沙盘', '普通']

# 录屏整理输出文件前缀模板
# 可使用占位符:
# - {year}: 年份, 例如 2026
# - {week}: ISO 周数, 例如 6, 可在模板中写成 {week:02d} 变成 06
WEEKLY_PREFIX_TEMPLATE: str = "{year}-{week:02d}w"

# 录屏整理当前周的输出子目录名，例如 "2026_06"
_iso = datetime.today().isocalendar()
WEEKLY_YEAR: int = _iso.year
WEEKLY_WEEK: int = _iso.week
WEEKLY_SUBDIR_NAME: str = f"{WEEKLY_YEAR}_{WEEKLY_WEEK:02d}"

# 录屏整理实际输出目录：E:\录屏整理\2026_06 这种形式
WEEKLY_OUTPUT_DIR: Path = WEEKLY_OUTPUT_ROOT / WEEKLY_SUBDIR_NAME


# 跨标签视频传递模式：
# - "overwrite": 右箭头传递时覆盖目标页签现有输入列表（默认）
# - "append": 右箭头传递时在目标页签原有列表后追加
CROSS_TAB_TRANSFER_MODE: str = "overwrite"


# ------------------ 系统通知 ------------------
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
