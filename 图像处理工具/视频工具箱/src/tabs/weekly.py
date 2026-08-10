import os
import math
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import tkinter as tk
from tkinter import ttk

from ..core.config import (
    MONO_FONT_FAMILY,
    WEEKLY_OUTPUT_DIR,
    WEEKLY_PREFIX_TEMPLATE,
)
from ..core.subprocess_util import get_media_duration, tracked_popen


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

        self.weekly_listbox = tk.Listbox(list_frame, height=8, font=(MONO_FONT_FAMILY, 9))
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.weekly_listbox.yview
        )
        self.weekly_listbox.configure(yscrollcommand=scrollbar.set)

        self.weekly_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._listbox_bind_drag(self.weekly_listbox, self.weekly_video_list)

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

    # ------------------------- 拖拽与列表操作 -------------------------
    def _apply_weekly_drop_resolved(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if not self._apply_ordered_paths_to_video_list(
            self.weekly_video_list, original_paths, resolved, overwrite=False
        ):
            return
        self._update_weekly_listbox()
        if self.weekly_video_list:
            self.weekly_video_label.config(
                text=f"已载入 {len(self.weekly_video_list)} 个视频文件", foreground="black"
            )

    def _update_weekly_listbox(self) -> None:
        self._listbox_update(self.weekly_listbox, self.weekly_video_list)

    def clear_weekly_list(self) -> None:
        self._listbox_clear(
            self.weekly_listbox, self.weekly_video_list, "请拖入一个或多个视频文件", self.weekly_video_label
        )

    def remove_selected_weekly(self) -> None:
        self._listbox_remove_selected(
            self.weekly_listbox, self.weekly_video_list, self.weekly_video_label
        )

    def move_up_weekly(self) -> None:
        self._listbox_move(self.weekly_listbox, self.weekly_video_list, -1)

    def move_down_weekly(self) -> None:
        self._listbox_move(self.weekly_listbox, self.weekly_video_list, 1)

    # ------------------------- 运行入口 -------------------------
    def run_weekly_process(self) -> None:
        """入口：检查参数后启动后台线程。"""
        if self._batch_in_progress or self._repair_in_progress:
            self.status_label.config(text="已有任务在处理中，请等待完成", foreground="red")
            return
        if not self.weekly_video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return
        self._batch_in_progress = True
        original_paths = [p for p, _ in self.weekly_video_list]
        self._resolve_paths_for_use_async(original_paths, self._start_weekly_process)

    def _start_weekly_process(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if not self._apply_ordered_paths_to_video_list(
            self.weekly_video_list, original_paths, resolved, overwrite=True
        ):
            self._batch_in_progress = False
            return
        self._update_weekly_listbox()

        WEEKLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.weekly_run_btn.config(state="disabled", text="处理中")
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
            duration = get_media_duration(vpath)
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
                    # 片段时长用 -t 明确指定，不依赖输出时间戳是否保留绝对值；
                    # 若出现片段边界/时长异常，可改回旧写法：
                    # "-to", str(local_start + local_dur)
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
                        "-t",
                        str(local_dur),
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
                    # 与音频片段同理，用 -t <时长> 而非 -to <绝对结束时间戳>
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
                        "-t",
                        str(local_dur),
                        "-an",
                        "-filter:v",
                        "setpts=PTS/60",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "23",
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
            rc = proc.wait()
            return rc == 0
        except Exception as e:
            self._append_log_line(f"命令执行出错: {e}")
            return False

    def _on_weekly_done(self, success: List[str], fail: List[str]) -> None:
        self._on_batch_done(
            self.weekly_run_btn,
            "开始整理",
            "录屏整理",
            success,
            fail,
            msg_format="已完成：成功 {ok} 段，失败 {bad} 段",
            log_fail=True,
        )


__all__ = ["WeeklyMixin"]
