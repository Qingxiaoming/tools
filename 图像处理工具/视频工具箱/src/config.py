import re
import subprocess
import sys
from pathlib import Path

# Windows 下隐藏 FFmpeg 子进程的黑框
SUBPROCESS_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ------------------ 基础配置（可自行修改）------------------
# 建议将这些目录改成你自己的磁盘路径，例如：
# SEGMENT_OUTPUT_DIR = Path(r"E:\多段截取")

# 多段截取输出目录
SEGMENT_OUTPUT_DIR: Path = Path(r"E:\toolbox输出\多段截取")

# 画幅裁剪输出目录
CROP_OUTPUT_DIR: Path = Path(r"E:\toolbox输出\画幅裁剪")

# 视频合并输出目录
MERGE_OUTPUT_DIR: Path = Path(r"E:\toolbox输出\合并输出")

# 文档生成输出目录（存放 md 文档）
DOC_OUTPUT_DIR: Path = Path(r"E:\toolbox输出\文档生成")


# ------------------ 业务常量 ------------------
# 标准视频文件名正则
STANDARD_VIDEO_PATTERN = re.compile(r'^[^\\/:*?"<>|\s]+\.mp4$')

# 关卡性质列表
VIDEO_NATURE_LIST = ['突袭', '无解', '待压', '剧情', '他人记录', '剿灭', '沙盘', '普通']


# ------------------ 系统通知 ------------------
try:
    from plyer import notification  # type: ignore
    ENABLE_NOTIFICATION = True
except Exception:
    notification = None  # type: ignore
    ENABLE_NOTIFICATION = False


def ensure_dirs_exist() -> None:
    """确保所有输出目录存在。"""
    for path in (SEGMENT_OUTPUT_DIR, CROP_OUTPUT_DIR, MERGE_OUTPUT_DIR, DOC_OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
