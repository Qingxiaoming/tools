import os
import subprocess
import threading
from typing import List, Tuple

import cv2
import tkinter as tk
from tkinter import scrolledtext, ttk

try:
    from .config import CROP_OUTPUT_DIR, ENABLE_NOTIFICATION, notification
    from .roi_selector import ROISelector
except ImportError:
    from config import CROP_OUTPUT_DIR, ENABLE_NOTIFICATION, notification
    from roi_selector import ROISelector


class CropMixin:
    """画幅裁剪相关 UI 与业务逻辑。"""

    # 依赖主类提供：
    # - self.crop_frame, self.status_label, self.log
    # - self.video_list, self.roi, self.crop_run_btn
    # - self._append_log_line, self._clear_log

    def _create_crop_widgets(self) -> None:
        self.crop_video_label = ttk.Label(
            self.crop_frame, text="请拖入一个或多个视频文件", foreground="grey"
        )
        self.crop_video_label.pack(pady=3)

        ttk.Label(self.crop_frame, text="视频文件列表:").pack(anchor="w", padx=10)
        self.crop_text = scrolledtext.ScrolledText(
            self.crop_frame, width=60, height=12, font=("Consolas", 9)
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
        added_files: List[str] = []
        for f in files:
            if not os.path.isfile(f):
                continue
            ext = os.path.splitext(f)[-1].lower()
            if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
                continue
            item = (f, os.path.basename(f))
            if item not in self.video_list:
                self.video_list.append(item)
                added_files.append(item[1])

        if added_files:
            self.crop_text.config(state="normal")
            for filename in added_files:
                self.crop_text.insert("end", filename + "\n")
            self.crop_text.config(state="disabled")
            self.crop_video_label.config(
                text=f"已载入 {len(self.video_list)} 个视频文件", foreground="black"
            )

    def clear_crop_list(self) -> None:
        """清空裁剪视频列表。"""
        self.video_list.clear()
        self.crop_text.config(state="normal")
        self.crop_text.delete("1.0", "end")
        self.crop_text.config(state="disabled")
        self.crop_video_label.config(
            text="请拖入一个或多个视频文件", foreground="grey"
        )

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
        self.wait_window(selector)
        if selector.roi is None:
            return
        self.roi = selector.roi
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
        self.crop_run_btn.config(state="disabled", text="处理中")
        self._clear_log()
        threading.Thread(target=self._crop_batch_thread, daemon=True).start()

    def _crop_batch_thread(self) -> None:
        success: List[str] = []
        fail: List[str] = []
        x, y, w, h = self.roi  # type: ignore[misc]

        CROP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
                proc = subprocess.Popen(
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
                else:
                    fail.append(f"{vname}  (返回码 {rc})")
            except Exception as e:
                fail.append(f"{vname}  ({e})")

        self.after(0, self._on_crop_batch_done, success, fail)

    def _on_crop_batch_done(self, success: List[str], fail: List[str]) -> None:
        self.crop_run_btn.config(state="normal", text="开始裁剪")
        self.status_label.config(text="待机中", foreground="blue")
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

