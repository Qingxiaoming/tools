"""未正常结束的流式录屏（如 OBS 崩溃后的 MKV）检测与修复。"""

import os
import subprocess
import threading
from typing import Callable, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from ..core.common_mixins import VIDEO_EXTENSIONS
from ..core.config import SUBPROCESS_CREATE_NO_WINDOW, UI_FONT_FAMILY
from ..core.file_lock import exclusive_file_lock
from ..core.overlay import OverlayMixin
from ..core.subprocess_util import get_media_duration, tracked_popen

def has_video_stream(path: str) -> bool:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=SUBPROCESS_CREATE_NO_WINDOW,
            timeout=30,
        )
        return proc.returncode == 0 and "video" in (proc.stdout or "")
    except Exception:
        return False


def is_corrupted_streaming_video(path: str) -> bool:
    """是否为未正常封尾的流式录屏（典型：ffprobe 时长为 N/A）。"""
    if not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return False
    if get_media_duration(path) is not None:
        return False
    if not has_video_stream(path):
        return False
    # 有视频流但拿不到时长 → 判定为疑似未封尾（无需再解析 ffprobe 错误文本）
    return True


def repaired_output_path(src: str) -> str:
    base, ext = os.path.splitext(src)
    if base.endswith("_repaired"):
        return src
    return f"{base}_repaired{ext}"


def repair_streaming_video(
    src: str,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """重封装修复；成功返回输出路径，失败返回 None。可在后台线程调用。"""
    dst = repaired_output_path(src)
    lock_path = dst + ".lock"
    try:
        with exclusive_file_lock(lock_path):
            # 等锁期间另一个实例可能已完成修复，重新检查
            if os.path.isfile(dst) and get_media_duration(dst) is not None:
                if log_fn:
                    log_fn(f"已存在可用修复文件，跳过转码: {dst}")
                return dst

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "info",
                "-stats",
                "-err_detect",
                "ignore_err",
                "-i",
                src,
                "-map",
                "0",
                "-c",
                "copy",
                "-y",
                dst,
            ]
            try:
                proc = tracked_popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert proc.stdout is not None
                for line in iter(proc.stdout.readline, ""):
                    if log_fn:
                        log_fn(line.rstrip())
                rc = proc.wait()
                if rc != 0:
                    return None
                if get_media_duration(dst) is None:
                    return None
                return dst
            except Exception:
                return None
    except TimeoutError:
        if log_fn:
            log_fn(f"修复被其他实例占用，本次跳过: {dst}")
        return None


ResolveDoneCallback = Callable[[Optional[List[str]], List[str]], None]


class RepairMixin(OverlayMixin):
    """损坏流式视频检测、多选修复对话框（后台修复，不阻塞界面）。"""

    def _pick_usable_path(self, original: str, resolved: str) -> Optional[str]:
        """优先使用修复后路径，否则退回原路径。"""
        if resolved and os.path.isfile(resolved):
            return resolved
        if original and os.path.isfile(original):
            return original
        return None

    def _apply_ordered_paths_to_video_list(
        self,
        video_list: List[Tuple[str, str]],
        original_paths: List[str],
        resolved_paths: Optional[List[str]],
        *,
        overwrite: bool,
    ) -> bool:
        """
        按拖入时的顺序（original_paths 为临时数组快照）写入列表。
        修复成功的项用修复后路径原位替代，不保留原损坏路径。
        """
        if resolved_paths is None:
            return False

        n = len(original_paths)
        if len(resolved_paths) < n:
            resolved_paths = resolved_paths + original_paths[len(resolved_paths) :]
        elif len(resolved_paths) > n:
            resolved_paths = resolved_paths[:n]

        if overwrite:
            video_list.clear()

        for orig, final in zip(original_paths, resolved_paths):
            use = self._pick_usable_path(orig, final)
            if not use:
                continue
            if overwrite:
                video_list.append((use, os.path.basename(use)))
            else:
                # 追加拖入：去掉列表中同批原路径/旧修复路径，再按顺序追加
                stale = {orig, final, repaired_output_path(orig)}
                video_list[:] = [(p, name) for p, name in video_list if p not in stale]
                video_list.append((use, os.path.basename(use)))

        return True

    def _init_repair_state(self) -> None:
        if not hasattr(self, "_repair_in_progress"):
            self._repair_in_progress = False
        if not hasattr(self, "_repair_shutdown"):
            self._repair_shutdown = False

    def _append_log_line_ui(self, msg: str) -> None:
        """线程安全：将一行日志投递到主线程底部输出区。"""
        self._post_ui(lambda m=msg: self._append_log_line(m))

    def _set_status_ui(self, text: str, foreground: str = "blue") -> None:
        """线程安全：设置状态栏文本。"""
        self._post_ui(lambda: self.status_label.config(text=text, foreground=foreground))

    def _init_repair_overlay_shell(self) -> None:
        """在主窗口上半区创建修复多选覆盖层（首次调用）。"""
        if getattr(self, "_repair_overlay_ready", False):
            return

        self.repair_overlay = self._create_upper_overlay_frame("repair_overlay")

        header = ttk.Frame(self.repair_overlay)
        header.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(
            header,
            text="检测到未正常结束的录屏",
            font=(UI_FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="以下视频可能因录屏异常中断而未写入文件尾（仅有头无尾）。"
            "可重封装修复后再继续；修复在后台进行。请勾选需要修复的文件：",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self._repair_overlay_list_frame = ttk.Frame(self.repair_overlay)
        self._repair_overlay_list_frame.pack(
            fill="both", expand=True, padx=12, pady=6
        )

        footer = ttk.Frame(self.repair_overlay)
        footer.pack(fill="x", padx=12, pady=(0, 10))
        # 确保 footer 不会被压缩
        footer.pack_configure(fill="x")

        self._repair_overlay_tool_row = ttk.Frame(footer)
        self._repair_overlay_tool_row.pack(fill="x", pady=(0, 6))

        self._repair_overlay_btn_row = ttk.Frame(footer)
        self._repair_overlay_btn_row.pack(fill="x", pady=(4, 0))

        self._repair_overlay_ready = True

    def _show_repair_overlay(self) -> None:
        self._init_repair_overlay_shell()
        self._show_upper_overlay(self.repair_overlay)

    def _hide_repair_overlay(self) -> None:
        if getattr(self, "repair_overlay", None):
            self._hide_upper_overlay(self.repair_overlay)

    def _ask_repair_selection(self, corrupted_paths: List[str]) -> Optional[List[str]]:
        if not corrupted_paths:
            return []

        self._init_repair_overlay_shell()
        result_holder: list[Optional[List[str]]] = [[]]

        # 确保按钮容器存在且可见
        if not hasattr(self, '_repair_overlay_btn_row') or not self._repair_overlay_btn_row.winfo_exists():
            # 如果按钮行不存在，重新创建 footer 和按钮行
            footer = ttk.Frame(self.repair_overlay)
            footer.pack(fill="x", padx=12, pady=(0, 10))
            self._repair_overlay_tool_row = ttk.Frame(footer)
            self._repair_overlay_tool_row.pack(fill="x", pady=(0, 6))
            self._repair_overlay_btn_row = ttk.Frame(footer)
            self._repair_overlay_btn_row.pack(fill="x")
        else:
            # 确保按钮行已 pack
            if not self._repair_overlay_btn_row.winfo_ismapped():
                self._repair_overlay_btn_row.pack(fill="x")

        # 清空之前的控件
        for child in self._repair_overlay_list_frame.winfo_children():
            child.destroy()
        for child in self._repair_overlay_tool_row.winfo_children():
            child.destroy()
        for child in self._repair_overlay_btn_row.winfo_children():
            child.destroy()

        list_frame = ttk.Frame(self._repair_overlay_list_frame)
        list_frame.pack(fill="both", expand=True)

        # 设置 Canvas 高度，避免列表占满所有空间导致按钮被挤出
        canvas = tk.Canvas(list_frame, highlightthickness=0, height=80)
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=canvas.yview
        )
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 使用 lambda 避免嵌套函数命名问题
        canvas.bind("<Configure>", lambda e, cvs=canvas, wid=win_id: cvs.itemconfig(wid, width=e.width))

        vars_map: dict[str, tk.BooleanVar] = {}
        for p in corrupted_paths:
            var = tk.BooleanVar(value=True)
            vars_map[p] = var
            ttk.Checkbutton(
                inner,
                text=os.path.basename(p),
                variable=var,
            ).pack(anchor="w", pady=1)

        # 使用类级别的回调避免嵌套函数命名问题
        self._repair_vars_map = vars_map
        self._repair_result_holder = result_holder

        def finish_repair(value: Optional[List[str]]) -> None:
            result_holder[0] = value
            self._hide_repair_overlay()
            if hasattr(self, "_repair_dialog_var"):
                self._repair_dialog_var.set(1)

        ttk.Button(
            self._repair_overlay_tool_row,
            text="全选",
            command=lambda: [v.set(True) for v in vars_map.values()],
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            self._repair_overlay_tool_row,
            text="全不选",
            command=lambda: [v.set(False) for v in vars_map.values()],
        ).pack(side="left")

        # 修复按钮行
        btn_frame = self._repair_overlay_btn_row
        ttk.Button(
            btn_frame,
            text="修复选中",
            command=lambda: finish_repair([p for p, v in vars_map.items() if v.get()]),
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            btn_frame,
            text="全部跳过",
            command=lambda: finish_repair([]),
        ).pack(side="right", padx=6)
        ttk.Button(
            btn_frame,
            text="取消",
            command=lambda: finish_repair(None),
        ).pack(side="right")

        self._repair_dialog_var = tk.IntVar(self, 0)
        self._show_repair_overlay()
        self.update_idletasks()
        self.wait_variable(self._repair_dialog_var)

        # 清理临时属性
        self._repair_vars_map = None
        self._repair_result_holder = None

        return result_holder[0]

    def _repair_paths_worker(
        self,
        to_repair: List[str],
        mapping: dict[str, str],
    ) -> None:
        """后台线程：执行修复并把 ffmpeg 输出写入日志区。"""
        for src in to_repair:
            name = os.path.basename(src)
            self._set_status_ui(f"正在修复录屏: {name}", "blue")
            self._append_log_line_ui(f"开始修复: {src}")
            fixed = repair_streaming_video(src, self._append_log_line_ui)
            if fixed:
                mapping[src] = fixed
                self._append_log_line_ui(f"修复完成: {fixed}")
            else:
                self._append_log_line_ui(f"修复失败: {src}（将仍使用原文件）")
                self._set_status_ui(f"修复失败: {name}（将仍使用原文件）", "red")

    def _resolve_paths_for_use_async(
        self,
        paths: List[str],
        on_done: ResolveDoneCallback,
    ) -> None:
        """
        检测并可选修复；完成后在主线程调用 on_done(resolved_paths, original_paths)。
        original_paths 为拖入/传入时的顺序快照；resolved 中修复项已原位替换路径。
        resolved_paths 为 None 表示用户取消。
        """
        self._init_repair_state()
        original_paths = list(paths)

        if self._repair_in_progress:
            # 修复进行中：允许拖入/传递，直接加入列表并跳过新一轮损坏检测，
            # 避免修复弹窗与正在进行的修复任务重叠
            self.status_label.config(
                text="修复进行中，文件将直接加入（跳过损坏检测）", foreground="blue"
            )
            on_done(list(paths), original_paths)
            return

        if not paths:
            on_done([], original_paths)
            return

        # 在后台线程执行损坏检测，避免阻塞主线程
        self.status_label.config(text="正在检测视频文件…", foreground="blue")
        self._clear_log()
        self._append_log_line(f"=== 开始检测 {len(original_paths)} 个视频文件 ===")

        def detect_worker() -> None:
            corrupted = []
            failed = []
            total = len(original_paths)
            for i, path in enumerate(original_paths, 1):
                # 检查是否需要关闭
                if getattr(self, "_repair_shutdown", False):
                    return

                name = os.path.basename(path)

                self._post_ui(
                    lambda idx=i, fname=name: self._append_log_line(f"[{idx}/{total}] 检测: {fname}")
                )

                try:
                    if is_corrupted_streaming_video(path):
                        corrupted.append(path)
                        self._post_ui(
                            lambda fname=name: self._append_log_line(f"  ⚠️ 检测到损坏: {fname}")
                        )
                except Exception as e:
                    failed.append((path, str(e)))
                    self._post_ui(
                        lambda fname=name, err=str(e): self._append_log_line(f"  ❌ 检测失败: {fname} ({err})")
                    )

            # 检查是否需要关闭
            if getattr(self, "_repair_shutdown", False):
                return

            # 使用线程安全的方式调度到主线程
            def schedule_done():
                try:
                    self._on_detect_done_impl(corrupted, failed, original_paths, total, on_done)
                except Exception as e:
                    import traceback
                    self._append_log_line(f"[ERROR] 检测完成处理失败: {e}")
                    self._append_log_line(traceback.format_exc())

            # 投递到主线程执行
            self._post_ui(schedule_done)

        threading.Thread(target=detect_worker, daemon=True).start()

    def _on_detect_done_impl(self, corrupted: List[str], failed: List[tuple], original_paths: List[str], total: int, on_done: ResolveDoneCallback) -> None:
        """检测完成后在主线程执行的处理（避免嵌套函数）。"""
        try:
            self._do_on_detect_done_impl(corrupted, failed, original_paths, total, on_done)
        except Exception as e:
            import traceback
            self._append_log_line(f"[ERROR] _on_detect_done_impl 异常: {e}")
            self._append_log_line(traceback.format_exc())

    def _do_on_detect_done_impl(self, corrupted: List[str], failed: List[tuple], original_paths: List[str], total: int, on_done: ResolveDoneCallback) -> None:
        """检测完成后在主线程执行的处理（实际实现）。"""
        if getattr(self, "_repair_shutdown", False):
            return

        if not corrupted:
            self._append_log_line(f"=== 检测完成，全部 {total} 个文件正常 ===")
            self.status_label.config(text="待机中", foreground="blue")
            on_done(list(original_paths), original_paths)
            return

        self._append_log_line(f"=== 检测到 {len(corrupted)} 个损坏文件 ===")

        to_repair = self._ask_repair_selection(corrupted)
        if to_repair is None:
            on_done(None, original_paths)
            return

        mapping = {p: p for p in original_paths}
        if not to_repair:
            on_done([mapping.get(p, p) for p in original_paths], original_paths)
            return

        self._repair_in_progress = True
        self._clear_log()
        self._append_log_line("=== 开始修复未正常结束的录屏（后台） ===")
        self.status_label.config(text="正在后台修复录屏…", foreground="blue")

        self._start_repair_worker(to_repair, mapping, original_paths, on_done)

    def _start_repair_worker(self, to_repair: List[str], mapping: dict, original_paths: List[str], on_done: ResolveDoneCallback) -> None:
        """启动修复工作线程（避免嵌套函数）。"""
        def repair_worker() -> None:
            try:
                self._repair_paths_worker(to_repair, mapping)
            finally:
                result = [mapping.get(p, p) for p in original_paths]
                # 投递到主线程执行
                self._post_ui(lambda: self._on_repair_finish(result, original_paths, on_done))

        threading.Thread(target=repair_worker, daemon=True).start()

    def _on_repair_finish(self, result: List[str], original_paths: List[str], on_done: ResolveDoneCallback) -> None:
        """修复完成后在主线程执行的处理。"""
        try:
            self._repair_in_progress = False
            self.status_label.config(text="录屏修复完成", foreground="blue")
            on_done(result, original_paths)
        except Exception as e:
            import traceback
            self._append_log_line(f"[ERROR] _on_repair_finish 异常: {e}")
            self._append_log_line(traceback.format_exc())


__all__ = [
    "RepairMixin",
    "is_corrupted_streaming_video",
    "repair_streaming_video",
    "repaired_output_path",
]
