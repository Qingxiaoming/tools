import os
import re
import subprocess
import threading
from typing import List, Tuple

from tkinter import scrolledtext, ttk
import tkinter as tk

try:
    from .config import SEGMENT_OUTPUT_DIR, ENABLE_NOTIFICATION, notification
except ImportError:
    from config import SEGMENT_OUTPUT_DIR, ENABLE_NOTIFICATION, notification


class SegmentMixin:
    """多段截取相关 UI 与业务逻辑。"""

    # 这些属性与方法在主类 VideoTools 中定义 / 提供：
    # - self.segment_frame
    # - self.status_label, self.log, self._time_to_seconds, self._append_log_line, self._clear_log
    # - self.video_path, self.segment_run_btn, self.precise_crop_var

    def _create_segment_widgets(self) -> None:
        self.segment_video_label = ttk.Label(
            self.segment_frame, text="请拖入一个视频文件", foreground="grey"
        )
        self.segment_video_label.pack(pady=3)

        ttk.Label(self.segment_frame, text="批量截取:").pack(anchor="w", padx=10)
        self.segment_text = scrolledtext.ScrolledText(
            self.segment_frame, width=60, height=12, font=("Consolas", 9)
        )
        self.segment_text.pack(padx=10, pady=2)
        self.segment_text.insert(
            "end", "00:00:01 01:00:02 test1\nclipA 00:00:03 00:00:08\n00:00:11 my clip 00:00:20\n"
        )

        options_frame = ttk.Frame(self.segment_frame)
        options_frame.pack(fill="x", padx=10, pady=2)

        self.precise_crop_var = tk.BooleanVar(value=False)
        precise_check = ttk.Checkbutton(
            options_frame,
            text="精确裁剪（解决前几秒静止问题，但处理速度较慢）",
            variable=self.precise_crop_var,
        )
        precise_check.pack(anchor="w")

        btn_frame = ttk.Frame(self.segment_frame)
        btn_frame.pack(fill="x", padx=10, pady=4)
        self.segment_run_btn = ttk.Button(
            btn_frame, text="开始截取", command=self.run_segment_batch
        )
        self.segment_run_btn.pack(side="right", padx=4)

    def _handle_drop_segment(self, path: str) -> None:
        """拖入单个视频用于多段截取。"""
        if not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[-1].lower()
        if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
            return
        self.video_path = path
        SEGMENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.segment_video_label.config(
            text=f"已载入:  {os.path.basename(path)}", foreground="black"
        )

    def run_segment_batch(self) -> None:
        """解析输入文本并批量截取视频。"""
        if not self.video_path:
            self.status_label.config(text="请先拖入视频文件", foreground="red")
            return
        lines = self.segment_text.get("1.0", "end").strip().splitlines()
        tasks: List[Tuple[str, str, str]] = []
        errors: List[str] = []
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            ok, result = self._parse_segment_line(line)
            if not ok:
                errors.append(f"第{idx}行: {result}")
                continue
            start, end, name = result  # type: ignore[misc]
            tasks.append((start, end, name))

        if errors:
            self.log.config(state="normal")
            self.log.delete("1.0", "end")
            for msg in errors:
                self.log.insert("end", msg + "\n")
            self.log.config(state="disabled")
            self.status_label.config(text="发现输入错误，请修正后重试", foreground="red")
            return
        if not tasks:
            return

        self.segment_run_btn.config(state="disabled", text="处理中")
        self._clear_log()
        threading.Thread(
            target=self._segment_batch_thread, args=(tasks,), daemon=True
        ).start()

    def _parse_segment_line(self, line: str):
        """解析一行多段截取输入，返回 (ok, (start, end, name)) 或 (False, 错误信息)。"""
        time_pattern_colon = r"\b\d{1,2}[:\uFF1A]\d{2}[:\uFF1A]\d{2}(?:\.\d{1,3})?\b"
        time_pattern_6 = r"\b\d{6}\b"
        matches_colon = list(re.finditer(time_pattern_colon, line))
        matches_6 = list(re.finditer(time_pattern_6, line))

        def norm_6(m):
            g = m.group(0)
            return g[:2] + ":" + g[2:4] + ":" + g[4:6]

        all_matches = []
        for m in matches_colon:
            all_matches.append((m.start(), m.end(), m.group(0)))
        for m in matches_6:
            if not any(m.start() < e and m.end() > s for s, e, _ in all_matches):
                all_matches.append((m.start(), m.end(), norm_6(m)))
        all_matches.sort(key=lambda x: x[0])

        if len(all_matches) == 0:
            return False, "未检测到时间（格式示例：00:01:02 或 010205、005959）"
        if len(all_matches) == 1:
            return False, "仅检测到一个时间，需提供开始与结束两个时间"
        if len(all_matches) > 2:
            return False, "检测到超过两个时间，其中一个疑似作为文件名，文件名不能是时间格式"

        t1 = all_matches[0][2]
        t2 = all_matches[1][2]
        s1 = self._time_to_seconds(t1)
        s2 = self._time_to_seconds(t2)
        if s1 is None or s2 is None:
            return False, "时间格式不合法（应为 H:MM:SS[.ms] 或 HHMMSS）"
        if s1 == s2:
            return False, "开始与结束时间不能相同"
        start, end = (t1, t2) if s1 < s2 else (t2, t1)

        a0, a1 = all_matches[0][0], all_matches[0][1]
        b0, b1 = all_matches[1][0], all_matches[1][1]
        name = (line[:a0] + line[a1:b0] + line[b1:]).strip()
        if (name.startswith('"') and name.endswith('"')) or (
            name.startswith("'") and name.endswith("'")
        ):
            name = name[1:-1].strip()
        if not name:
            return False, "缺少文件名"

        if re.fullmatch(time_pattern_colon, name) or re.fullmatch(time_pattern_6, name):
            return False, "文件名不能是时间格式"

        lower = name.lower()
        if not lower.endswith((".mp4", ".mkv", ".mov", ".avi")):
            name += ".mp4"

        return True, (start, end, name)

    def _segment_batch_thread(self, tasks: List[Tuple[str, str, str]]) -> None:
        success: List[str] = []
        fail: List[str] = []

        SEGMENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for start, end, name in tasks:
            base, ext = os.path.splitext(name)
            counter = 1
            while True:
                out_name = f"{base}{'' if counter == 1 else f'({counter})'}{ext}"
                out_path = SEGMENT_OUTPUT_DIR / out_name
                if not out_path.exists():
                    break
                counter += 1

            duration_sec = self._time_to_seconds(end) - self._time_to_seconds(start)  # type: ignore[arg-type]

            if self.precise_crop_var.get():
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-ss",
                    start,
                    "-i",
                    self.video_path,
                    "-t",
                    str(duration_sec),
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-y",
                    str(out_path),
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-ss",
                    start,
                    "-i",
                    self.video_path,
                    "-ss",
                    "0",
                    "-t",
                    str(duration_sec),
                    "-c",
                    "copy",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-y",
                    str(out_path),
                ]

            self.status_label.config(text=f"正在处理：{out_name}")
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
                    self._append_log_line(line.rstrip("\n"))
                proc.wait()
                if proc.returncode == 0:
                    success.append(out_name)
                else:
                    fail.append(f"{out_name}  (返回码 {proc.returncode})")
            except Exception as e:
                fail.append(f"{out_name}  ({e})")

        self.after(0, self._on_segment_batch_done, success, fail)

    def _on_segment_batch_done(self, success: List[str], fail: List[str]) -> None:
        self.segment_run_btn.config(state="normal", text="开始截取")
        self.status_label.config(text="待机中", foreground="blue")
        msg = f"成功 {len(success)} 段，失败 {len(fail)} 段"
        if ENABLE_NOTIFICATION and notification:
            notification.notify(
                title="视频批量截取",
                message=msg,
                timeout=4,
                app_name="VideoTools",
            )
        else:
            self.status_label.config(text=msg)


__all__ = ["SegmentMixin"]

