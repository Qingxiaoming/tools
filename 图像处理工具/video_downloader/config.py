"""跨平台配置：保存目录（可持久化）、工具探测。"""

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "video_downloader"


def default_save_dir() -> Path:
    """Windows 沿用原桌面路径；其他平台用 ~/Videos/未分类。"""
    if sys.platform == "win32":
        return Path(r"D:\Users\Windows10\Desktop\0V0_燕小重的知识库\视频\未分类")
    return Path.home() / "Videos" / "未分类"


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


CONFIG_FILE = _config_dir() / "config.json"


def load_save_dir() -> Path:
    """优先级：环境变量 > 配置文件 > 平台默认值。"""
    env = os.environ.get("VIDEO_DOWNLOAD_DIR")
    if env:
        return Path(env).expanduser()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if data.get("save_dir"):
            return Path(data["save_dir"]).expanduser()
    except Exception:
        pass
    return default_save_dir()


def save_dir_to_config(path: Path) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    data["save_dir"] = str(path)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find_tool(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None
