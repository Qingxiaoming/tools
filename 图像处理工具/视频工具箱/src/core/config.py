import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Windows 下隐藏 FFmpeg 子进程黑框
SUBPROCESS_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _get_project_root() -> Path:
    """获取项目根目录，兼容开发模式和 PyInstaller 打包模式。"""
    # PyInstaller 打包后，exe 运行时 sys.frozen 为 True
    if getattr(sys, 'frozen', False):
        # 打包模式：exe 所在目录即为项目根目录
        return Path(sys.executable).parent
    else:
        # 开发模式：config.py 位于 src/core/，项目根目录是上上级
        return Path(__file__).parent.parent.parent


def _load_config() -> dict:
    """加载 JSON 配置文件，如果失败则返回空字典。"""
    # 配置文件路径：项目根目录下的 config.json
    config_path = _get_project_root() / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, IOError) as e:
            print(f"警告: 配置文件读取失败，使用默认配置: {e}", file=sys.stderr)
    return {}


# 加载用户配置
_USER_CONFIG = _load_config()


# 辅助函数：从配置中获取值，如果不存在则使用默认值
def _get_config(path: str, default):
    """通过点分隔路径获取配置值，如 'output_directories.root'。"""
    keys = path.split('.')
    value = _USER_CONFIG
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


# 基础输出目录（按需自行修改）
_TOOLBOX_OUTPUT_ROOT_STR: str = _get_config('output_directories.root', r"E:\toolbox输出")
TOOLBOX_OUTPUT_ROOT: Path = Path(_TOOLBOX_OUTPUT_ROOT_STR)

# 各功能输出子目录（相对于 root 或绝对路径）
_SEGMENT_SUBDIR: str = _get_config('output_directories.segment', "多段截取")
_CROP_SUBDIR: str = _get_config('output_directories.crop', "画幅裁剪")
_MERGE_SUBDIR: str = _get_config('output_directories.merge', "合并输出")
_DOC_SUBDIR: str = _get_config('output_directories.doc', "文档生成")

# 如果配置的是相对路径，则基于 root 构建；否则使用绝对路径
SEGMENT_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / _SEGMENT_SUBDIR if not Path(_SEGMENT_SUBDIR).is_absolute() else Path(_SEGMENT_SUBDIR)
CROP_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / _CROP_SUBDIR if not Path(_CROP_SUBDIR).is_absolute() else Path(_CROP_SUBDIR)
MERGE_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / _MERGE_SUBDIR if not Path(_MERGE_SUBDIR).is_absolute() else Path(_MERGE_SUBDIR)
DOC_OUTPUT_DIR: Path = TOOLBOX_OUTPUT_ROOT / _DOC_SUBDIR if not Path(_DOC_SUBDIR).is_absolute() else Path(_DOC_SUBDIR)

# 主窗口几何参数：宽x高+左上角X+左上角Y
MAIN_WINDOW_GEOMETRY: str = _get_config('window.geometry', "420x460+3132+920")

# 文档转运目标路径
_DOC_TRANSFER_DOC_STR: str = _get_config(
    'doc_transfer.doc_dir',
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~"
)
_DOC_TRANSFER_MEDIA_STR: str = _get_config(
    'doc_transfer.media_dir',
    r"D:\Users\Windows10\Desktop\0V0燕小重的文库\姑且算作我的\打穿泰拉~\附件"
)
DOC_TRANSFER_DOC_DIR: Path = Path(_DOC_TRANSFER_DOC_STR)
DOC_TRANSFER_MEDIA_DIR: Path = Path(_DOC_TRANSFER_MEDIA_STR)

# 录屏整理根目录（每周一个子文件夹）
_WEEKLY_ROOT_STR: str = _get_config('weekly.root', r"I:\录屏")
WEEKLY_OUTPUT_ROOT: Path = Path(_WEEKLY_ROOT_STR)

# 录屏整理前缀模板，支持 {year} / {week}
WEEKLY_PREFIX_TEMPLATE: str = _get_config('weekly.prefix_template', "{year}-{week:02d}w")

_iso = datetime.today().isocalendar()
WEEKLY_YEAR: int = _iso.year
WEEKLY_WEEK: int = _iso.week
WEEKLY_SUBDIR_NAME: str = f"{WEEKLY_YEAR}_{WEEKLY_WEEK:02d}"

WEEKLY_OUTPUT_DIR: Path = WEEKLY_OUTPUT_ROOT / WEEKLY_SUBDIR_NAME


STANDARD_VIDEO_PATTERN = re.compile(r'^[^\\/:*?"<>|\s]+\.mp4$')
VIDEO_NATURE_LIST: list[str] = _get_config(
    'video_nature_list',
    ['突袭', '无解', '待压', '剧情', '他人记录', '剿灭', '沙盘', '普通']
)

# 跨标签视频传递模式："overwrite" 或 "append"
CROSS_TAB_TRANSFER_MODE: str = _get_config('cross_tab_transfer_mode', "overwrite")

# 多段截取文件名字符映射配置
# 键为输入的简写，值为转换后的字符
# 安全规则：键不能是纯数字，值不能包含文件名非法字符 / \ : * ? " < > |
_SEGMENT_MAPPINGS_RAW: dict = _get_config('segment_name_mappings', {})
# 过滤掉以 _ 开头的内部键（如 _comment）
SEGMENT_NAME_MAPPINGS: dict[str, str] = {
    k: v for k, v in _SEGMENT_MAPPINGS_RAW.items()
    if not k.startswith('_') and isinstance(v, str)
}


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
