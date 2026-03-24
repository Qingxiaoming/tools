import os
import math
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import tkinter as tk
from tkinter import ttk

try:
    from .config import (
        ENABLE_NOTIFICATION,
        notification,
        SUBPROCESS_CREATE_NO_WINDOW,
        WEEKLY_OUTPUT_DIR,
        WEEKLY_PREFIX_TEMPLATE,
    )
except ImportError:  # 兼容直接运行 src 下脚本的情况
    from config import (  # type: ignore
        ENABLE_NOTIFICATION,
        notification,
        SUBPROCESS_CREATE_NO_WINDOW,
        WEEKLY_OUTPUT_DIR,
        WEEKLY_PREFIX_TEMPLATE,
    )


class WeeklyMixin:
    """录屏整理模块（按时间轴分段导出）。"""

    SEGMENT_SECONDS: int = 24 * 60 * 60  # 24小时的原始内容，60倍速后=24分钟输出

    def _create_weekly_widgets(self) -> None:
        """创建「录屏整理」页签 UI。"""
        frame = self.weekly_frame

        self.weekly_video_label = ttk.Label(
            frame, text="请拖入一个或多个视频文件", foreground="grey"
        )
        self.weekly_video_label.pack(pady=3)

        ttk.Label(frame, text="视频文件列表（按顺序组成一周时间轴）:").pack(anchor="w", padx=10)

        main_frame = ttk.Frame(frame)
        main_frame.pack(fill="x", padx=10, pady=2)

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(side="left", fill="x", expand=True)

        self.weekly_listbox = tk.Listbox(list_frame, height=10, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.weekly_listbox.yview
        )
        self.weekly_listbox.configure(yscrollcommand=scrollbar.set)

        self.weekly_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.weekly_listbox.bind("<Button-1>", self._on_weekly_listbox_click)
        self.weekly_listbox.bind("<B1-Motion>", self._on_weekly_listbox_drag)
        self.weekly_listbox.bind("<ButtonRelease-1>", self._on_weekly_listbox_release)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side="right", padx=(10, 0), fill="y")

        ttk.Button(btn_frame, text="清空列表", command=self.clear_weekly_list).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="删除选中", command=self.remove_selected_weekly).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="上移", command=self.move_up_weekly).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="下移", command=self.move_down_weekly).pack(
            fill="x", pady=2
        )

        self.weekly_run_btn = ttk.Button(
            btn_frame, text="开始整理", command=self.run_weekly_process
        )
        self.weekly_run_btn.pack(fill="x", pady=(8, 0))

        self.weekly_drag_start: int | None = None

    # ------------------------- 拖拽与列表操作 -------------------------
    def _handle_drop_weekly(self, files: List[str]) -> None:
        """在「录屏整理」页签上拖入视频文件。"""
        added_files: List[str] = []
        for f in files:
            if not os.path.isfile(f):
                continue
            ext = os.path.splitext(f)[-1].lower()
            if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
                continue
            item = (f, os.path.basename(f))
            if item not in self.weekly_video_list:
                self.weekly_video_list.append(item)
                added_files.append(item[1])

        if added_files:
            self._update_weekly_listbox()
            self.weekly_video_label.config(
                text=f"已载入 {len(self.weekly_video_list)} 个视频文件", foreground="black"
            )

    def _update_weekly_listbox(self) -> None:
        self.weekly_listbox.delete(0, tk.END)
        for i, (_, name) in enumerate(self.weekly_video_list):
            self.weekly_listbox.insert(tk.END, f"{i + 1}. {name}")

    def clear_weekly_list(self) -> None:
        self.weekly_video_list.clear()
        self._update_weekly_listbox()
        self.weekly_video_label.config(text="请拖入一个或多个视频文件", foreground="grey")

    def remove_selected_weekly(self) -> None:
        selection = self.weekly_listbox.curselection()
        if not selection:
            self.status_label.config(text="请先选择要删除的视频", foreground="red")
            return
        index = selection[0]
        if 0 <= index < len(self.weekly_video_list):
            del self.weekly_video_list[index]
            self._update_weekly_listbox()
            self.weekly_video_label.config(
                text=f"已载入 {len(self.weekly_video_list)} 个视频文件", foreground="black"
            )

    def move_up_weekly(self) -> None:
        selection = self.weekly_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        index = selection[0]
        if index > 0:
            self.weekly_video_list[index], self.weekly_video_list[index - 1] = (
                self.weekly_video_list[index - 1],
                self.weekly_video_list[index],
            )
            self._update_weekly_listbox()
            self.weekly_listbox.selection_set(index - 1)

    def move_down_weekly(self) -> None:
        selection = self.weekly_listbox.curselection()
        if not selection or selection[0] == len(self.weekly_video_list) - 1:
            return
        index = selection[0]
        if index < len(self.weekly_video_list) - 1:
            self.weekly_video_list[index], self.weekly_video_list[index + 1] = (
                self.weekly_video_list[index + 1],
                self.weekly_video_list[index],
            )
            self._update_weekly_listbox()
            self.weekly_listbox.selection_set(index + 1)

    def _on_weekly_listbox_click(self, event) -> None:
        self.weekly_drag_start = event.y

    def _on_weekly_listbox_drag(self, event) -> None:
        if self.weekly_drag_start is None:
            return
        current_index = self.weekly_listbox.nearest(event.y)
        if current_index != -1:
            self.weekly_listbox.selection_clear(0, tk.END)
            self.weekly_listbox.selection_set(current_index)

    def _on_weekly_listbox_release(self, event) -> None:
        if self.weekly_drag_start is None:
            return

        start_index = self.weekly_listbox.nearest(self.weekly_drag_start)
        end_index = self.weekly_listbox.nearest(event.y)

        if (
            start_index != end_index
            and 0 <= start_index < len(self.weekly_video_list)
            and 0 <= end_index < len(self.weekly_video_list)
        ):
            item = self.weekly_video_list.pop(start_index)
            self.weekly_video_list.insert(end_index, item)
            self._update_weekly_listbox()
            self.weekly_listbox.selection_set(end_index)

        self.weekly_drag_start = None

    # ------------------------- 运行入口 -------------------------
    def run_weekly_process(self) -> None:
        """入口：检查参数后启动后台线程。"""
        if not self.weekly_video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return

        WEEKLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.weekly_run_btn.config(state="disabled", text="处理中")
        # 录屏整理处理中也禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
        self._clear_log()

        thread = threading.Thread(
            target=self._weekly_process_thread,
            args=(list(self.weekly_video_list),),
            daemon=True,
        )
        thread.start()

    # ------------------------- 具体处理逻辑 -------------------------
    def _get_media_duration(self, path: str) -> float | None:
        """使用 ffprobe 获取媒体时长（秒）。"""
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True,
                text=True,
                creationflags=SUBPROCESS_CREATE_NO_WINDOW,
            )
            return float(proc.stdout.strip())
        except Exception:
            return None

    def _make_unique_path(self, directory: Path, filename: str) -> Path:
        """在目录下生成不重名的文件路径，规则与其它模块保持一致。"""
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            name = f"{base}{'' if counter == 1 else f'({counter})'}{ext}"
            path = directory / name
            if not path.exists():
                return path
            counter += 1

    def _weekly_process_thread(self, video_list: List[Tuple[str, str]]) -> None:
        success: List[str] = []
        fail: List[str] = []

        # 构建整体时间轴
        timeline: List[Tuple[str, str, float, float]] = []  # (path, name, start, end)
        current_start = 0.0
        for vpath, vname in video_list:
            duration = self._get_media_duration(vpath)
            if duration is None or duration <= 0:
                fail.append(f"{vname}  (无法获取时长)")
                continue
            start = current_start
            end = start + duration
            timeline.append((vpath, vname, start, end))
            current_start = end

        if not timeline:
            self.after(0, self._on_weekly_done, success, fail)
            return

        total_duration = timeline[-1][3]
        total_parts = max(1, math.ceil(total_duration / self.SEGMENT_SECONDS))

        # 生成前缀
        iso = datetime.today().isocalendar()
        year = iso.year
        week = iso.week
        base_prefix = WEEKLY_PREFIX_TEMPLATE.format(year=year, week=week)

        tmp_root = WEEKLY_OUTPUT_DIR / "_tmp_weekly"
        tmp_root.mkdir(parents=True, exist_ok=True)

        try:
            for part_idx in range(total_parts):
                part_start = part_idx * self.SEGMENT_SECONDS
                part_end = min(total_duration, (part_idx + 1) * self.SEGMENT_SECONDS)
                if part_end <= part_start:
                    continue

                # 找出该段对应到每个源视频上的局部片段
                segments: List[Tuple[str, str, float, float]] = []  # (path, name, local_start, dur)
                for vpath, vname, v_start, v_end in timeline:
                    overlap_start = max(part_start, v_start)
                    overlap_end = min(part_end, v_end)
                    if overlap_end <= overlap_start:
                        continue
                    local_start = overlap_start - v_start
                    local_dur = overlap_end - overlap_start
                    segments.append((vpath, vname, local_start, local_dur))

                if not segments:
                    continue

                # 为该 24 小时段创建临时目录
                part_tag = f"part{part_idx + 1:02d}"
                part_tmp_dir = tmp_root / part_tag
                part_tmp_dir.mkdir(parents=True, exist_ok=True)

                # ---------------- 音频：分段提取 + concat ----------------
                audio_chunk_paths: List[Path] = []

                for seg_idx, (vpath, vname, local_start, local_dur) in enumerate(
                    segments, start=1
                ):
                    self.status_label.config(
                        text=f"提取音频：{base_prefix} {part_tag} - {vname}",
                        foreground="blue",
                    )
                    chunk_audio = part_tmp_dir / f"{base_prefix}_{part_tag}_a_{seg_idx:02d}.m4a"
                    if chunk_audio.exists():
                        try:
                            chunk_audio.unlink()
                        except Exception:
                            pass
                    segment_end = local_start + local_dur
                    audio_cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-ss",
                        str(local_start),
                        "-i",
                        vpath,
                        "-to",
                        str(segment_end),
                        "-vn",
                        "-c:a",
                        "aac",
                        "-y",
                        str(chunk_audio),
                    ]
                    if not self._run_ffmpeg_with_log(audio_cmd):
                        fail.append(f"{base_prefix} {part_tag}  (音频片段提取失败: {vname})")
                        break
                    audio_chunk_paths.append(chunk_audio)

                if not audio_chunk_paths:
                    continue

                # 合并音频片段
                audio_list_file = part_tmp_dir / f"{base_prefix}_{part_tag}_audio_list.txt"
                with open(audio_list_file, "w", encoding="utf-8") as f:
                    for p in audio_chunk_paths:
                        f.write(f"file '{str(p).replace(os.sep, '/')}'\n")

                audio_final_name = f"{base_prefix}_{part_tag}_audio.m4a"
                audio_out_path = self._make_unique_path(WEEKLY_OUTPUT_DIR, audio_final_name)

                self.status_label.config(
                    text=f"合并音频：{base_prefix} {part_tag}", foreground="blue"
                )
                audio_concat_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(audio_list_file),
                    "-c:a",
                    "aac",
                    "-y",
                    str(audio_out_path),
                ]
                if not self._run_ffmpeg_with_log(audio_concat_cmd):
                    fail.append(f"{audio_out_path.name}  (音频合并失败)")
                    continue

                # ---------------- 视频：分段加速 + concat ----------------
                video_chunk_paths: List[Path] = []

                for seg_idx, (vpath, vname, local_start, local_dur) in enumerate(
                    segments, start=1
                ):
                    self.status_label.config(
                        text=f"处理视频：{base_prefix} {part_tag} - {vname}（60 倍速）",
                        foreground="blue",
                    )
                    chunk_video = part_tmp_dir / f"{base_prefix}_{part_tag}_v_{seg_idx:02d}.mp4"
                    if chunk_video.exists():
                        try:
                            chunk_video.unlink()
                        except Exception:
                            pass
                    segment_end = local_start + local_dur
                    video_cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-ss",
                        str(local_start),
                        "-i",
                        vpath,
                        "-to",
                        str(segment_end),
                        "-an",
                        "-filter:v",
                        "setpts=PTS/60",
                        "-c:v",
                        "libx264",
                        "-y",
                        str(chunk_video),
                    ]
                    if not self._run_ffmpeg_with_log(video_cmd):
                        fail.append(f"{base_prefix} {part_tag}  (视频片段处理失败: {vname})")
                        break
                    video_chunk_paths.append(chunk_video)

                if not video_chunk_paths:
                    continue

                video_list_file = part_tmp_dir / f"{base_prefix}_{part_tag}_video_list.txt"
                with open(video_list_file, "w", encoding="utf-8") as f:
                    for p in video_chunk_paths:
                        f.write(f"file '{str(p).replace(os.sep, '/')}'\n")

                video_final_name = f"{base_prefix}_{part_tag}_x60.mp4"
                video_out_path = self._make_unique_path(WEEKLY_OUTPUT_DIR, video_final_name)

                self.status_label.config(
                    text=f"合并视频：{base_prefix} {part_tag}", foreground="blue"
                )
                video_concat_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(video_list_file),
                    "-c",
                    "copy",
                    "-y",
                    str(video_out_path),
                ]
                if not self._run_ffmpeg_with_log(video_concat_cmd):
                    fail.append(f"{video_out_path.name}  (视频合并失败)")
                    continue

                success.append(f"{base_prefix} {part_tag}")

                # 清理该段的临时文件
                for p in audio_chunk_paths + video_chunk_paths:
                    try:
                        p.unlink()
                    except Exception:
                        pass
                try:
                    audio_list_file.unlink()
                except Exception:
                    pass
                try:
                    video_list_file.unlink()
                except Exception:
                    pass
                try:
                    part_tmp_dir.rmdir()
                except Exception:
                    # 若目录未能删除（可能有残留文件），忽略
                    pass

        finally:
            # 尝试清理根临时目录
            try:
                tmp_root.rmdir()
            except Exception:
                pass

        self.after(0, self._on_weekly_done, success, fail)

    def _run_ffmpeg_with_log(self, cmd: List[str]) -> bool:
        """运行 ffmpeg 命令，并实时刷新日志窗口。返回是否成功。"""
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                creationflags=SUBPROCESS_CREATE_NO_WINDOW,
            )
            for line in iter(proc.stdout.readline, ""):
                self._append_log_line(line.rstrip("\n"))
            rc = proc.wait()
            return rc == 0
        except Exception as e:
            self._append_log_line(f"命令执行出错: {e}")
            return False

    def _on_weekly_done(self, success: List[str], fail: List[str]) -> None:
        self.weekly_run_btn.config(state="normal", text="开始整理")
        self.status_label.config(text="待机中", foreground="blue")
        # 录屏整理结束后恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)  # type: ignore[call-arg]

        msg = f"已完成：成功 {len(success)} 段，失败 {len(fail)} 段"
        if ENABLE_NOTIFICATION and notification:
            try:
                notification.notify(
                    title="录屏整理",
                    message=msg,
                    timeout=4,
                    app_name="VideoTools",
                )
            except Exception:
                # 通知失败时不影响主流程
                self.status_label.config(text=msg)
        else:
            self.status_label.config(text=msg)

        if fail:
            self._append_log_line("失败列表：")
            for item in fail:
                self._append_log_line("  " + item)


__all__ = ["WeeklyMixin"]

