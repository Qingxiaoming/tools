import os
import subprocess
import threading
from typing import Callable, List, Optional, Tuple

import cv2
import tkinter as tk
from tkinter import scrolledtext, ttk

from ..core.config import (
    CROP_OUTPUT_DIR,
    MONO_FONT_FAMILY,
    ENABLE_NOTIFICATION,
    notification,
    SUBPROCESS_CREATE_NO_WINDOW,
)
from ..core.subprocess_util import tracked_popen
from .roi import ROISelector


class CropMixin:
    """画幅裁剪模块。"""

    def _create_crop_widgets(self) -> None:
        self.crop_video_label = ttk.Label(
            self.crop_frame, text="请拖入一个或多个视频文件", foreground="grey"
        )
        self.crop_video_label.pack(pady=3)

        ttk.Label(self.crop_frame, text="视频文件列表:").pack(anchor="w", padx=10)
        self.crop_text = scrolledtext.ScrolledText(
            self.crop_frame, width=60, height=8, font=(MONO_FONT_FAMILY, 9)
        )
        self.crop_text.pack(padx=10, pady=2)
        self.crop_text.config(state="disabled")

        btn_frame = ttk.Frame(self.crop_frame)
        btn_frame.pack(fill="x", padx=10, pady=4)
        ttk.Button(btn_frame, text="选定画幅", command=self.select_roi).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="清空列表", command=self.clear_crop_list).pack(
            side="left", padx=4
        )
        self.crop_run_btn = ttk.Button(
            btn_frame, text="开始裁剪", command=self.run_crop_batch
        )
        self.crop_run_btn.pack(side="right", padx=4)

    def _handle_drop_crop(self, files: List[str]) -> None:
        candidates = [
            f
            for f in files
            if os.path.isfile(f)
            and os.path.splitext(f)[-1].lower()
            in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts")
        ]
        if not candidates:
            return
        self._resolve_paths_for_use_async(
            candidates, self._apply_crop_drop_resolved
        )

    def _rebuild_crop_list_ui(self) -> None:
        self.crop_text.config(state="normal")
        self.crop_text.delete("1.0", "end")
        for _, name in self.video_list:
            self.crop_text.insert("end", name + "\n")
        self.crop_text.config(state="disabled")
        if self.video_list:
            self.crop_video_label.config(
                text=f"已载入 {len(self.video_list)} 个视频文件", foreground="black"
            )

    def _apply_crop_drop_resolved(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if not self._apply_ordered_paths_to_video_list(
            self.video_list, original_paths, resolved, overwrite=False
        ):
            return
        self._rebuild_crop_list_ui()

    def _apply_crop_videos_resolved(
        self,
        resolved: List[str] | None,
        original_paths: List[str],
        *,
        overwrite: bool = False,
    ) -> bool:
        if not self._apply_ordered_paths_to_video_list(
            self.video_list, original_paths, resolved, overwrite=overwrite
        ):
            return False
        self._rebuild_crop_list_ui()
        return True

    def clear_crop_list(self) -> None:
        self.video_list.clear()
        self.crop_text.config(state="normal")
        self.crop_text.delete("1.0", "end")
        self.crop_text.config(state="disabled")
        self.crop_video_label.config(
            text="请拖入一个或多个视频文件", foreground="grey"
        )

    # 供主程序通过右箭头传递视频列表时调用
    def _set_crop_videos_from_paths(
        self,
        files: List[str],
        overwrite: bool = True,
        on_done: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """根据给定路径列表更新裁剪输入列表（含可选异步修复）。"""
        if not files:
            if on_done:
                on_done(True)
            return

        def finish(resolved: List[str] | None, original_paths: List[str]) -> None:
            ok = self._apply_crop_videos_resolved(
                resolved, original_paths, overwrite=overwrite
            )
            if on_done:
                on_done(ok)

        self._resolve_paths_for_use_async(files, finish)

    def select_roi(self) -> None:
        """弹出 ROI 选择窗口，从第一段视频读取首帧。"""
        if not self.video_list:
            self.status_label.config(text="请先拖入视频文件", foreground="red")
            return
        first_video = self.video_list[0][0]
        cap = cv2.VideoCapture(first_video)
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            self.status_label.config(text="无法读取视频第一帧", foreground="red")
            return
        selector = ROISelector(self, frame, orig_w, orig_h)
        roi = selector.run()
        if roi is None:
            return
        self.roi = roi
        self.status_label.config(
            text=f"已选择区域: x={self.roi[0]}, y={self.roi[1]}, w={self.roi[2]}, h={self.roi[3]}",
            foreground="blue",
        )

    def run_crop_batch(self) -> None:
        """按选定的 ROI 批量裁剪画幅。"""
        if not self.video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return
        if self.roi is None:
            self.status_label.config(
                text="请先点击'选定画幅'选择保留区域！", foreground="red"
            )
            return
        original_paths = [p for p, _ in self.video_list]
        self._resolve_paths_for_use_async(original_paths, self._start_crop_batch)

    def _start_crop_batch(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if not self._apply_crop_videos_resolved(
            resolved, original_paths, overwrite=True
        ):
            return
        self.crop_run_btn.config(state="disabled", text="处理中")
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
        self._clear_log()
        threading.Thread(target=self._crop_batch_thread, daemon=True).start()

    def _crop_batch_thread(self) -> None:
        success: List[str] = []
        fail: List[str] = []
        x, y, w, h = self.roi  # type: ignore[misc]

        CROP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 记录本次裁剪产生的输出文件路径，供跨页签传递使用
        produced_paths: List[str] = []

        for vpath, vname in self.video_list:
            base, ext = os.path.splitext(vname)
            out_path = CROP_OUTPUT_DIR / f"{base}{ext}"

            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=p=0",
                    vpath,
                ],
                capture_output=True,
                text=True,
                creationflags=SUBPROCESS_CREATE_NO_WINDOW,
            )
            try:
                orig_w, orig_h = map(int, probe.stdout.strip().split(","))
            except Exception:
                fail.append(f"{vname}  (无法获取分辨率)")
                continue

            if h != orig_h:
                new_h = orig_h
                new_w = int(round(w * orig_h / h))
                if new_w > orig_w:
                    new_w2 = orig_w
                    new_h2 = int(round(h * orig_w / w))
                    filter_complex = (
                        f"crop={w}:{h}:{x}:{y},"
                        f"scale={new_w2}:{new_h2},"
                        f"pad={orig_w}:{orig_h}:0:(oh-ih)/2:black"
                    )
                else:
                    filter_complex = (
                        f"crop={w}:{h}:{x}:{y},"
                        f"scale={new_w}:{new_h},"
                        f"pad={orig_w}:{orig_h}:(ow-iw)/2:0:black"
                    )
            else:
                filter_complex = (
                    f"crop={w}:{h}:{x}:{y},"
                    f"pad={orig_w}:{orig_h}:({orig_w}-{w})/2:({orig_h}-{h})/2:black"
                )

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "info",
                "-stats",
                "-i",
                vpath,
                "-vf",
                filter_complex,
                "-c:a",
                "copy",
                "-y",
                str(out_path),
            ]

            self.status_label.config(text=f"正在处理：{vname}", foreground="blue")
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
                for line in iter(proc.stdout.readline, ""):
                    self._append_log_line(line.rstrip())
                rc = proc.wait()
                if rc == 0:
                    success.append(vname)
                    produced_paths.append(str(out_path))
                else:
                    fail.append(f"{vname}  (返回码 {rc})")
            except Exception as e:
                fail.append(f"{vname}  ({e})")

        # 记录到主实例属性中，供右箭头使用
        try:
            self.crop_last_output_files = produced_paths
        except Exception:
            pass

        self.after(0, self._on_crop_batch_done, success, fail)

    def _on_crop_batch_done(self, success: List[str], fail: List[str]) -> None:
        self.crop_run_btn.config(state="normal", text="开始裁剪")
        self.status_label.config(text="待机中", foreground="blue")
        # 恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)  # type: ignore[call-arg]
        msg = f"成功 {len(success)} 个，失败 {len(fail)} 个"
        if ENABLE_NOTIFICATION and notification:
            notification.notify(
                title="视频批量裁剪",
                message=msg,
                timeout=4,
                app_name="VideoTools",
            )
        else:
            self.status_label.config(text=msg)
        if fail:
            self._append_log_line("失败列表：")
            for f in fail:
                self._append_log_line("  " + f)


__all__ = ["CropMixin"]
