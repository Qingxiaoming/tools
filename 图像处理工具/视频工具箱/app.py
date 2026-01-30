import os

import tkinter as tk
import tkinterdnd2 as tkdnd
from tkinter import scrolledtext, ttk

try:  # 作为包导入时
    from .config import ensure_dirs_exist
    from .segment import SegmentMixin
    from .crop import CropMixin
    from .merge import MergeMixin
    from .doc import DocMixin
except ImportError:  # 直接在目录中运行 main.pyw 时
    from config import ensure_dirs_exist
    from segment import SegmentMixin
    from crop import CropMixin
    from merge import MergeMixin
    from doc import DocMixin


class VideoTools(tkdnd.Tk, SegmentMixin, CropMixin, MergeMixin, DocMixin):
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

        ttk.Label(self, text="实时日志:").pack(anchor="w", padx=10, pady=(5, 0))
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


__all__ = ["VideoTools"]

