import os
import re
import subprocess
import threading
from typing import List, Tuple

from tkinter import scrolledtext, ttk
import tkinter as tk

from ..core.config import (
    SEGMENT_NAME_MAPPINGS,
    SEGMENT_OUTPUT_DIR,
    MONO_FONT_FAMILY,
)
from ..core.subprocess_util import tracked_popen


class SegmentMixin:
    """多段截取模块。"""

    def _apply_name_mappings(self, name: str) -> str:
        """应用文件名字符映射转换。

        将配置中定义的简写替换为对应字符。
        安全规则：
        1. 忽略纯数字的映射键（防止时间戳被篡改）
        2. 按键长度降序匹配，避免部分匹配问题
        3. 转换后的结果仍需通过文件名安全检查
        """
        if not SEGMENT_NAME_MAPPINGS:
            return name

        # 过滤掉纯数字的键（安全保护：禁止映射数字）
        valid_mappings = {
            k: v for k, v in SEGMENT_NAME_MAPPINGS.items()
            if k and not k.isdigit()
        }

        if not valid_mappings:
            return name

        # 按键长度降序排序，优先匹配长键（如先匹配 "mt" 再匹配 "m"）
        sorted_keys = sorted(valid_mappings.keys(), key=len, reverse=True)

        result = name
        for key in sorted_keys:
            value = valid_mappings[key]
            # 检查替换值是否包含危险的文件名字符
            if re.search(r'[\\/:*?"<>|]', value):
                continue  # 跳过包含非法字符的映射
            result = result.replace(key, value)

        return result

    def _is_safe_filename(self, name: str) -> bool:
        r"""检查文件名是否安全（防止命令行注入）。

        禁止的字符：\ / : * ? " < > | 以及控制字符
        禁止以 - 开头（可能被解析为命令行选项）
        """
        if not name:
            return False
        # 检查是否包含 Windows 文件名非法字符
        if re.search(r'[\\/:*?"<>|\x00-\x1f]', name):
            return False
        # 检查是否以 - 开头（防止被解析为命令行选项）
        if name.startswith('-'):
            return False
        # 检查是否包含命令行注入字符
        if re.search(r'[;&|`$()]', name):
            return False
        # 检查 . 和 .. 等特殊目录名
        if name in ('.', '..', '...'):
            return False
        return True

    def _create_segment_widgets(self) -> None:
        self.segment_video_label = ttk.Label(
            self.segment_frame, text="请拖入一个视频文件", foreground="grey"
        )
        self.segment_video_label.pack(pady=3)

        ttk.Label(self.segment_frame, text="批量截取:").pack(anchor="w", padx=10)
        self.segment_text = scrolledtext.ScrolledText(
            self.segment_frame, width=60, height=8, font=(MONO_FONT_FAMILY, 9)
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
        if not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[-1].lower()
        if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
            return
        self._resolve_paths_for_use_async(
            [path], self._on_segment_video_loaded
        )

    def _on_segment_video_loaded(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if resolved is None or not original_paths:
            return
        path = self._pick_usable_path(original_paths[0], resolved[0])
        if not path:
            return
        self.video_path = path
        SEGMENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.segment_video_label.config(
            text=f"已载入:  {os.path.basename(self.video_path)}", foreground="black"
        )

    def run_segment_batch(self) -> None:
        """解析输入文本并批量截取视频。"""
        if self._batch_in_progress or self._repair_in_progress:
            self.status_label.config(text="已有任务在处理中，请等待完成", foreground="red")
            return
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

        self._batch_in_progress = True
        original_paths = [self.video_path]
        self._resolve_paths_for_use_async(
            original_paths,
            lambda resolved, originals: self._start_segment_batch(
                resolved, originals, tasks
            ),
        )

    def _start_segment_batch(
        self,
        resolved: List[str] | None,
        original_paths: List[str],
        tasks: List[Tuple[str, str, str]],
    ) -> None:
        if resolved is None or not original_paths:
            self._batch_in_progress = False
            return
        path = self._pick_usable_path(original_paths[0], resolved[0])
        if not path:
            self._batch_in_progress = False
            return
        self.video_path = path
        self.segment_video_label.config(
            text=f"已载入:  {os.path.basename(self.video_path)}", foreground="black"
        )
        self.segment_run_btn.config(state="disabled", text="处理中")
        # 处理中期间禁用右箭头，避免中途跳转
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
        self._clear_log()
        # 快照输入（视频路径 + 精确裁剪开关），运行期间改输入不影响本次任务
        threading.Thread(
            target=self._segment_batch_thread,
            args=(tasks, path, self.precise_crop_var.get()),
            daemon=True,
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

        # 应用字符映射转换
        name = self._apply_name_mappings(name)

        # 安全检查：验证文件名是否合法
        base_name = name
        if '.' in name:
            base_name = name.rsplit('.', 1)[0]
        if not self._is_safe_filename(name) or not self._is_safe_filename(base_name):
            return False, "文件名包含非法字符或命令行注入风险"

        lower = name.lower()
        if not lower.endswith((".mp4", ".mkv", ".mov", ".avi")):
            name += ".mp4"

        return True, (start, end, name)

    def _segment_batch_thread(
        self,
        tasks: List[Tuple[str, str, str]],
        video_path: str,
        precise_crop: bool,
    ) -> None:
        success: List[str] = []
        fail: List[str] = []

        SEGMENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 记录本次截取产生的输出文件完整路径，供跨页签传递使用
        produced_paths: List[str] = []

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
            # FFmpeg 只接受 ASCII 冒号，需将全角冒号（：）转为半角（:）
            start_normalized = start.replace("\uFF1A", ":")

            if precise_crop:
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-ss",
                    start_normalized,
                    "-i",
                    video_path,
                    "-t",
                    str(duration_sec),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
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
                    start_normalized,
                    "-i",
                    video_path,
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
                    self._append_log_line(line.rstrip("\n"))
                proc.wait()
                if proc.returncode == 0:
                    success.append(out_name)
                    produced_paths.append(str(out_path))
                else:
                    fail.append(f"{out_name}  (返回码 {proc.returncode})")
            except Exception as e:
                fail.append(f"{out_name}  ({e})")

        # 将成功产生的输出记录到主实例属性中，便于右箭头传递
        try:
            self.segment_last_output_files = [os.path.basename(p) for p in produced_paths]
        except Exception:
            pass

        self.after(0, self._on_segment_batch_done, success, fail)

    def _on_segment_batch_done(self, success: List[str], fail: List[str]) -> None:
        self._on_batch_done(
            self.segment_run_btn,
            "开始截取",
            "视频批量截取",
            success,
            fail,
            msg_format="成功 {ok} 段，失败 {bad} 段",
        )


__all__ = ["SegmentMixin"]
