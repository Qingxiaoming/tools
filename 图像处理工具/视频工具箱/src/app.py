import os
import sys
import subprocess

import tkinter as tk
import tkinterdnd2 as tkdnd
from tkinter import scrolledtext, ttk

try:  # 作为包导入时
    from .config import (
        ensure_dirs_exist,
        SEGMENT_OUTPUT_DIR,
        CROP_OUTPUT_DIR,
        MERGE_OUTPUT_DIR,
        DOC_OUTPUT_DIR,
        WEEKLY_OUTPUT_DIR,
    )
    from .segment import SegmentMixin
    from .crop import CropMixin
    from .merge import MergeMixin
    from .doc import DocMixin
    from .weekly import WeeklyMixin
except ImportError:  # 直接在目录中运行 main.pyw 时
    from config import (
        ensure_dirs_exist,
        SEGMENT_OUTPUT_DIR,
        CROP_OUTPUT_DIR,
        MERGE_OUTPUT_DIR,
        DOC_OUTPUT_DIR,
        WEEKLY_OUTPUT_DIR,
    )
    from segment import SegmentMixin
    from crop import CropMixin
    from merge import MergeMixin
    from doc import DocMixin
    from weekly import WeeklyMixin


class VideoTools(tkdnd.Tk, SegmentMixin, CropMixin, MergeMixin, DocMixin, WeeklyMixin):
    """视频工具箱主程序。

    功能模块：
    - 多段截取
    - 画幅裁剪
    - 视频合并
    - 文档生成
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("视频工具箱")
        self.geometry("420x460+2532+1050")

        ensure_dirs_exist()

        # 多段截取相关
        self.video_path: str = ""

        # 画幅裁剪相关
        self.video_list: list[tuple[str, str]] = []
        self.roi: tuple[int, int, int, int] | None = None

        # 视频合并相关
        self.merge_video_list: list[tuple[str, str]] = []
        self.merge_audio_file: str = ""
        self.merge_audio_mode: str = "none"  # none, replace, mix

        # 文档生成相关
        self.doc_video_list: list[tuple[str, str]] = []

        # 录屏整理相关
        self.weekly_video_files: list[str] = []

        self._create_widgets()
        self.drop_target_register(tkdnd.DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop_files)

    # ------------------------- UI 构建 -------------------------
    def _create_widgets(self) -> None:
        """创建主界面和各个功能页签。"""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # 多段截取
        self.segment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.segment_frame, text="多段截取")
        self._create_segment_widgets()

        # 画幅裁剪
        self.crop_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.crop_frame, text="画幅裁剪")
        self._create_crop_widgets()

        # 视频合并
        self.merge_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.merge_frame, text="视频合并")
        self._create_merge_widgets()

        # 文档生成
        self.doc_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.doc_frame, text="文档生成")
        self._create_doc_widgets()

        # 录屏整理
        self.weekly_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.weekly_frame, text="录屏整理")
        self._create_weekly_widgets()

        # 公共状态栏与日志
        self._create_common_widgets()

    def _create_common_widgets(self) -> None:
        """底部状态栏与实时日志区域。"""
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=(5, 0))

        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="待机中", foreground="blue")
        self.status_label.pack(side="left")

        # 打开当前标签页对应输出目录的按钮，放在状态栏右侧
        open_btn = ttk.Button(
            status_frame,
            text="📂",
            width=3,
            command=self._open_current_tab_folder,
        )
        open_btn.pack(side="right")

        self.log = scrolledtext.ScrolledText(
            self, width=80, height=6, state="disabled", font=("Consolas", 8)
        )
        self.log.pack(padx=10, pady=(0, 10), fill="both", expand=True)

    # ------------------------- 通用工具方法 -------------------------
    def _time_to_seconds(self, t: str) -> float | None:
        """将时间字符串转换为秒，支持 HH:MM:SS[.ms] 与 HHMMSS 形式。"""
        try:
            if len(t) == 6 and t.isdigit():
                t = t[:2] + ":" + t[2:4] + ":" + t[4:6]
            t = t.replace("\uFF1A", ":")  # 兼容中文冒号
            if "." in t:
                hhmmss, ms = t.split(".", 1)
                ms_val = float("0." + ms)
            else:
                hhmmss, ms_val = t, 0.0
            parts = hhmmss.split(":")
            if len(parts) != 3:
                return None
            h, m, s = [int(parts[0]), int(parts[1]), int(parts[2])]
            if not (0 <= m < 60 and 0 <= s < 60):
                return None
            return h * 3600 + m * 60 + s + ms_val
        except Exception:
            return None

    def _append_log_line(self, msg: str) -> None:
        """向日志窗口追加一行文本。"""
        if "\r" in msg:
            self.log.config(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("end", msg.split("\r")[-1])
            self.log.config(state="disabled")
        else:
            self.log.config(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.config(state="disabled")
        self.log.see("end")

    def _clear_log(self) -> None:
        """清空日志。"""
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _open_folder(self, path: str) -> None:
        """在文件资源管理器中打开指定目录。"""
        if not os.path.isdir(path):
            self.status_label.config(text="目标文件夹不存在或不可用", foreground="red")
            return

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.status_label.config(text=f"打开文件夹失败: {e}", foreground="red")

    def _open_current_tab_folder(self) -> None:
        """根据当前标签页，打开对应的目标输出文件夹。"""
        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 0:
            # 多段截取输出目录
            path = str(SEGMENT_OUTPUT_DIR)
        elif current_tab == 1:
            # 画幅裁剪输出目录
            path = str(CROP_OUTPUT_DIR)
        elif current_tab == 2:
            # 视频合并输出目录
            path = str(MERGE_OUTPUT_DIR)
        elif current_tab == 3:
            # 文档生成输出目录
            path = str(DOC_OUTPUT_DIR)
        elif current_tab == 4:
            # 录屏整理输出目录
            path = str(WEEKLY_OUTPUT_DIR)
        else:
            self.status_label.config(text="当前标签不支持打开目标文件夹", foreground="red")
            return

        self._open_folder(path)

    # ------------------------- 拖拽入口 -------------------------
    def drop_files(self, event) -> None:
        """处理拖拽进入窗口的文件。"""
        files = self.tk.splitlist(event.data)
        if not files:
            return

        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 0:
            self._handle_drop_segment(files[0])
        elif current_tab == 1:
            self._handle_drop_crop(files)
        elif current_tab == 2:
            # 若拖入的是单个音频文件则走音频逻辑
            if len(files) == 1:
                ext = os.path.splitext(files[0])[-1].lower()
                if ext in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
                    self._handle_drop_merge_audio(files[0])
                    return
            self._handle_drop_merge_videos(files)
        elif current_tab == 3:
            self._handle_drop_doc(files)
        elif current_tab == 4:
            self._handle_drop_weekly(files)


__all__ = ["VideoTools"]
