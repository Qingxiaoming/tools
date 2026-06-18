import os
import sys
import subprocess

import tkinter as tk
import tkinterdnd2 as tkdnd
from tkinter import scrolledtext, ttk

from .config import (
    ensure_dirs_exist,
    SEGMENT_OUTPUT_DIR,
    CROP_OUTPUT_DIR,
    MERGE_OUTPUT_DIR,
    DOC_OUTPUT_DIR,
    WEEKLY_OUTPUT_DIR,
    CROSS_TAB_TRANSFER_MODE,
    MAIN_WINDOW_GEOMETRY,
)
from .subprocess_util import init_process_job, terminate_all_tracked_processes
from ..services.repair import RepairMixin
from ..tabs.crop import CropMixin
from ..tabs.doc import DocMixin
from ..tabs.merge import MergeMixin
from ..tabs.segment import SegmentMixin
from ..tabs.weekly import WeeklyMixin


class VideoTools(
    tkdnd.Tk,
    RepairMixin,
    SegmentMixin,
    CropMixin,
    MergeMixin,
    DocMixin,
    WeeklyMixin,
):
    """视频工具箱主窗体。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("视频工具箱")
        self.geometry(MAIN_WINDOW_GEOMETRY)

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

        # 录屏整理相关 (path, basename) 与 weekly.py 中 _handle_drop_weekly 一致
        self.weekly_video_list: list[tuple[str, str]] = []

        self._repair_in_progress = False

        init_process_job()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        self._create_widgets()
        self.drop_target_register(tkdnd.DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop_files)

    def _on_app_close(self) -> None:
        """关闭窗口时结束所有 ffmpeg 子进程，释放对视频文件的占用。"""
        # 设置关闭标志，通知后台线程退出
        self._repair_shutdown = True

        if getattr(self, "repair_overlay", None) and self.repair_overlay.winfo_ismapped():
            self._hide_repair_overlay()
            if hasattr(self, "_repair_dialog_var"):
                self._repair_dialog_var.set(1)
        active_roi = getattr(self, "_active_roi_selector", None)
        if active_roi is not None:
            active_roi._on_cancel()
        elif getattr(self, "roi_overlay", None) and self.roi_overlay.winfo_ismapped():
            self._hide_upper_overlay(self.roi_overlay)
        terminate_all_tracked_processes()
        self.quit()  # 退出 mainloop，必须先于 destroy
        self.destroy()

    def _create_widgets(self) -> None:
        """创建主界面与各页签。"""
        # 上半区容器：页签 + 可覆盖的修复多选层（不遮挡底部状态栏与日志）
        self.upper_shell = ttk.Frame(self)
        self.upper_shell.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.notebook = ttk.Notebook(self.upper_shell)
        self.notebook.pack(fill="both", expand=True)

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

        self._init_repair_overlay_shell()

        # 公共状态栏与日志
        self._create_common_widgets()

    def _create_common_widgets(self) -> None:
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=(5, 0))

        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="待机中", foreground="blue")
        self.status_label.pack(side="left")

        # 右箭头：跨标签页传递输入 / 输出
        self.jump_btn = ttk.Button(
            status_frame,
            text="➡",
            width=3,
            command=self._jump_next_step,
        )
        self.jump_btn.pack(side="right")

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

    def _set_jump_enabled(self, enabled: bool) -> None:
        """供各功能模块在处理期间禁用/启用右箭头按钮。"""
        btn = getattr(self, "jump_btn", None)
        if btn is None:
            return
        state = "normal" if enabled else "disabled"
        try:
            btn.config(state=state)
        except Exception:
            pass

    # ------------------------- 跨标签页跳转 -------------------------
    def _jump_next_step(self) -> None:
        """根据当前标签页，将输入/输出传递给下一步，并切换标签页。"""
        try:
            current_tab = self.notebook.index(self.notebook.select())
        except Exception:
            return

        try:
            if current_tab == 0:
                self._jump_segment_to_crop()
            elif current_tab == 1:
                self._jump_crop_to_merge_and_doc()
            elif current_tab == 2:
                # 视频合并只切换到文档生成标签页
                self.notebook.select(self.doc_frame)
                self.status_label.config(text="已切换到文档生成", foreground="blue")
            elif current_tab == 3:
                # 文档生成标签页：右箭头等价于触发转运逻辑
                try:
                    self.run_doc_transfer()
                except Exception as e:
                    self.status_label.config(
                        text=f"转运失败: {e}", foreground="red"
                    )
            else:
                self.status_label.config(text="当前标签不支持跳转操作", foreground="red")
        except Exception as e:
            self.status_label.config(text=f"跳转失败: {e}", foreground="red")

    def _jump_segment_to_crop(self) -> None:
        """多段截取 -> 画幅裁剪."""
        # 若当前没有输入视频，直接报错
        if not getattr(self, "video_path", ""):
            self.status_label.config(text="当前没有可传递的视频输入", foreground="red")
            return

        # 优先尝试使用多段截取输出列表（由 SegmentMixin 在完成时更新）
        output_names = getattr(self, "segment_last_output_files", None)
        candidate_paths: list[str] = []

        if output_names:
            candidate_paths = [
                os.path.join(str(SEGMENT_OUTPUT_DIR), name) for name in output_names
            ]
            # 校验所有输出文件是否都仍然存在
            missing = [p for p in candidate_paths if not os.path.isfile(p)]
            if missing:
                self.status_label.config(
                    text="多段截取输出文件缺失，无法传递，请检查输出目录",
                    foreground="red",
                )
                return
        else:
            # 未执行“开始截取”：直接传递当前输入视频
            if not os.path.isfile(self.video_path):
                self.status_label.config(
                    text="多段截取输入视频已不存在，无法传递", foreground="red"
                )
                return
            candidate_paths = [self.video_path]

        # 根据配置决定覆盖或追加
        overwrite = CROSS_TAB_TRANSFER_MODE != "append"

        def on_transferred(ok: bool) -> None:
            if ok:
                self.notebook.select(self.crop_frame)
                self.status_label.config(
                    text="已将视频传递到画幅裁剪", foreground="blue"
                )

        try:
            self._set_crop_videos_from_paths(
                candidate_paths, overwrite=overwrite, on_done=on_transferred
            )
        except Exception as e:
            self.status_label.config(text=f"传递到画幅裁剪失败: {e}", foreground="red")

    def _jump_crop_to_merge_and_doc(self) -> None:
        """画幅裁剪 -> 视频合并 & 文档生成."""
        # 若当前没有任何输入，直接报错
        if not getattr(self, "video_list", []):
            self.status_label.config(text="当前没有可传递的视频列表", foreground="red")
            return

        # 优先尝试使用画幅裁剪输出（由 CropMixin 在完成时更新）
        crop_outputs = getattr(self, "crop_last_output_files", None)
        candidate_paths: list[str] = []

        if crop_outputs:
            candidate_paths = [p for p in crop_outputs]
            missing = [p for p in candidate_paths if not os.path.isfile(p)]
            if missing:
                self.status_label.config(
                    text="画幅裁剪输出文件缺失，无法传递，请检查输出目录",
                    foreground="red",
                )
                return
        else:
            # 未执行“开始裁剪”：使用当前输入列表
            candidate_paths = [path for path, _ in self.video_list]
            missing = [p for p in candidate_paths if not os.path.isfile(p)]
            if missing:
                self.status_label.config(
                    text="画幅裁剪输入视频已不存在，无法传递", foreground="red"
                )
                return

        overwrite = CROSS_TAB_TRANSFER_MODE != "append"

        def on_transferred(ok: bool) -> None:
            if ok:
                self.notebook.select(self.merge_frame)
                self.status_label.config(
                    text="已将视频传递到合并与文档生成", foreground="blue"
                )

        try:
            self._resolve_paths_for_use_async(
                candidate_paths,
                lambda resolved, originals: self._apply_jump_crop_to_merge_doc(
                    resolved, originals, overwrite, on_transferred
                ),
            )
        except Exception as e:
            self.status_label.config(text=f"传递到后续步骤失败: {e}", foreground="red")

    def _apply_jump_crop_to_merge_doc(
        self,
        resolved: list[str] | None,
        original_paths: list[str],
        overwrite: bool,
        on_done,
    ) -> None:
        try:
            ok_merge = self._apply_merge_videos_resolved(
                resolved, original_paths, overwrite=overwrite
            )
            ok_doc = self._apply_doc_videos_resolved(
                resolved, original_paths, overwrite=overwrite
            )
            on_done(ok_merge and ok_doc)
        except Exception as e:
            self.status_label.config(text=f"传递到后续步骤失败: {e}", foreground="red")
            on_done(False)

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
