import os
import subprocess
import threading
from typing import List, Tuple

import tkinter as tk
from tkinter import ttk

try:
    from .config import MERGE_OUTPUT_DIR, ENABLE_NOTIFICATION, notification, SUBPROCESS_CREATE_NO_WINDOW
except ImportError:
    from config import MERGE_OUTPUT_DIR, ENABLE_NOTIFICATION, notification, SUBPROCESS_CREATE_NO_WINDOW


class MergeMixin:
    """视频合并相关 UI 与业务逻辑。"""

    # 依赖主类提供：
    # - self.merge_frame, self.status_label, self.log
    # - self.merge_video_list, self.merge_audio_file
    # - self._append_log_line, self._clear_log

    def _create_merge_widgets(self) -> None:
        self.merge_video_label = ttk.Label(
            self.merge_frame, text="请拖入多个视频文件", foreground="grey"
        )
        self.merge_video_label.pack(pady=3)

        ttk.Label(self.merge_frame, text="视频文件列表:").pack(anchor="w", padx=10)

        main_frame = ttk.Frame(self.merge_frame)
        main_frame.pack(fill="x", padx=10, pady=2)

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(side="left", fill="x", expand=True)

        self.merge_listbox = tk.Listbox(list_frame, height=10, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.merge_listbox.yview
        )
        self.merge_listbox.configure(yscrollcommand=scrollbar.set)

        self.merge_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.merge_listbox.bind("<Button-1>", self._on_merge_listbox_click)
        self.merge_listbox.bind("<B1-Motion>", self._on_merge_listbox_drag)
        self.merge_listbox.bind("<ButtonRelease-1>", self._on_merge_listbox_release)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side="right", padx=(10, 0), fill="y")

        ttk.Button(btn_frame, text="清空列表", command=self.clear_merge_list).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="删除选中", command=self.remove_selected_merge).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="上移", command=self.move_up_merge).pack(
            fill="x", pady=2
        )
        ttk.Button(btn_frame, text="下移", command=self.move_down_merge).pack(
            fill="x", pady=2
        )
        # 与原版一致：将"开始合并"按钮放在右侧竖排按钮的最下方
        self.merge_run_btn = ttk.Button(
            btn_frame, text="开始合并", command=self.run_merge_batch
        )
        self.merge_run_btn.pack(fill="x", pady=(8, 0))

        audio_frame = ttk.Frame(self.merge_frame)
        audio_frame.pack(fill="x", padx=10, pady=2)

        self.merge_audio_label = ttk.Label(
            audio_frame, text="拖入音频文件（可选）", foreground="grey"
        )
        self.merge_audio_label.pack(side="left")

        ttk.Label(audio_frame, text="音频模式:").pack(side="left", padx=(20, 5))
        self.audio_mode_var = tk.StringVar(value="保持原音频")
        audio_combo = ttk.Combobox(
            audio_frame, textvariable=self.audio_mode_var, width=12, state="readonly"
        )
        audio_combo["values"] = ("保持原音频", "替换音频", "叠加音频")
        audio_combo.pack(side="left", padx=5)

        output_frame = ttk.Frame(self.merge_frame)
        output_frame.pack(fill="x", padx=10, pady=1)

        ttk.Label(output_frame, text="输出文件名:").pack(side="left")
        self.merge_output_name = tk.StringVar(value="合并视频")
        output_entry = ttk.Entry(output_frame, textvariable=self.merge_output_name, width=15)
        output_entry.pack(side="left", padx=10)

        ttk.Label(output_frame, text="倍速:").pack(side="left", padx=(20, 5))
        self.merge_speed = tk.StringVar(value="1.0")
        speed_combo = ttk.Combobox(
            output_frame, textvariable=self.merge_speed, width=12
        )
        speed_combo["values"] = ("1.0", "0.5", "0.25", "2.0", "到音乐放完")
        speed_combo.pack(side="left", padx=5)

        self.merge_drag_start: int | None = None

    def _handle_drop_merge_videos(self, files: List[str]) -> None:
        added_files: List[str] = []
        for f in files:
            if not os.path.isfile(f):
                continue
            ext = os.path.splitext(f)[-1].lower()
            if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
                continue
            item = (f, os.path.basename(f))
            if item not in self.merge_video_list:
                self.merge_video_list.append(item)
                added_files.append(item[1])

        if added_files:
            self._update_merge_listbox()
            self.merge_video_label.config(
                text=f"已载入 {len(self.merge_video_list)} 个视频文件", foreground="black"
            )

    def _handle_drop_merge_audio(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[-1].lower()
        if ext not in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
            self.status_label.config(text="不支持的音频格式", foreground="red")
            return

        self.merge_audio_file = path
        self.merge_audio_label.config(
            text=f"已载入音频: {os.path.basename(path)}", foreground="black"
        )
        self.status_label.config(
            text=f"已载入音频文件: {os.path.basename(path)}", foreground="blue"
        )

    def _update_merge_listbox(self) -> None:
        self.merge_listbox.delete(0, tk.END)
        for i, (_, name) in enumerate(self.merge_video_list):
            self.merge_listbox.insert(tk.END, f"{i + 1}. {name}")

    def clear_merge_list(self) -> None:
        self.merge_video_list.clear()
        self._update_merge_listbox()
        self.merge_video_label.config(text="请拖入多个视频文件", foreground="grey")

    # 供主程序通过右箭头传递视频列表时调用
    def _set_merge_videos_from_paths(self, files: List[str], overwrite: bool = True) -> None:
        """根据给定路径列表更新合并输入列表。"""
        if overwrite:
            self.merge_video_list.clear()
        for f in files:
            if not os.path.isfile(f):
                continue
            item = (f, os.path.basename(f))
            if item not in self.merge_video_list:
                self.merge_video_list.append(item)
        self._update_merge_listbox()
        if self.merge_video_list:
            self.merge_video_label.config(
                text=f"已载入 {len(self.merge_video_list)} 个视频文件", foreground="black"
            )

    def remove_selected_merge(self) -> None:
        selection = self.merge_listbox.curselection()
        if not selection:
            self.status_label.config(text="请先选择要删除的视频", foreground="red")
            return
        index = selection[0]
        if 0 <= index < len(self.merge_video_list):
            del self.merge_video_list[index]
            self._update_merge_listbox()
            self.merge_video_label.config(
                text=f"已载入 {len(self.merge_video_list)} 个视频文件", foreground="black"
            )

    def move_up_merge(self) -> None:
        selection = self.merge_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        index = selection[0]
        if index > 0:
            self.merge_video_list[index], self.merge_video_list[index - 1] = (
                self.merge_video_list[index - 1],
                self.merge_video_list[index],
            )
            self._update_merge_listbox()
            self.merge_listbox.selection_set(index - 1)

    def move_down_merge(self) -> None:
        selection = self.merge_listbox.curselection()
        if not selection or selection[0] == len(self.merge_video_list) - 1:
            return
        index = selection[0]
        if index < len(self.merge_video_list) - 1:
            self.merge_video_list[index], self.merge_video_list[index + 1] = (
                self.merge_video_list[index + 1],
                self.merge_video_list[index],
            )
            self._update_merge_listbox()
            self.merge_listbox.selection_set(index + 1)

    def _on_merge_listbox_click(self, event) -> None:
        self.merge_drag_start = event.y

    def _on_merge_listbox_drag(self, event) -> None:
        if self.merge_drag_start is None:
            return
        current_index = self.merge_listbox.nearest(event.y)
        if current_index != -1:
            self.merge_listbox.selection_clear(0, tk.END)
            self.merge_listbox.selection_set(current_index)

    def _on_merge_listbox_release(self, event) -> None:
        if self.merge_drag_start is None:
            return

        start_index = self.merge_listbox.nearest(self.merge_drag_start)
        end_index = self.merge_listbox.nearest(event.y)

        if (
            start_index != end_index
            and 0 <= start_index < len(self.merge_video_list)
            and 0 <= end_index < len(self.merge_video_list)
        ):
            item = self.merge_video_list.pop(start_index)
            self.merge_video_list.insert(end_index, item)
            self._update_merge_listbox()
            self.merge_listbox.selection_set(end_index)

        self.merge_drag_start = None

    def run_merge_batch(self) -> None:
        if not self.merge_video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return

        audio_mode_text = self.audio_mode_var.get()
        audio_mode_map = {"保持原音频": "none", "替换音频": "replace", "叠加音频": "mix"}
        audio_mode = audio_mode_map.get(audio_mode_text, "none")

        if audio_mode in ("replace", "mix") and not self.merge_audio_file:
            self.status_label.config(
                text="选择了音频处理模式但未载入音频文件！", foreground="red"
            )
            return

        output_name = self.merge_output_name.get().strip()
        if not output_name:
            self.status_label.config(text="请输入输出文件名！", foreground="red")
            return

        speed_str = self.merge_speed.get().strip()
        if speed_str != "到音乐放完":
            try:
                speed = float(speed_str)
                if speed <= 0:
                    self.status_label.config(text="倍速必须大于0！", foreground="red")
                    return
            except ValueError:
                self.status_label.config(
                    text="倍速必须是数字或选择「到音乐放完」！", foreground="red"
                )
                return

        self.merge_run_btn.config(state="disabled", text="合并中")
        # 合并处理中禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
        self._clear_log()
        threading.Thread(target=self._merge_batch_thread, daemon=True).start()

    def _get_media_duration(self, path: str) -> float | None:
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
        try:
            return float(proc.stdout.strip())
        except Exception:
            return None

    def _merge_batch_thread(self) -> None:
        try:
            MERGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            base_name = self.merge_output_name.get().strip()
            counter = 1
            while True:
                output_path = MERGE_OUTPUT_DIR / (
                    f"{base_name}{'' if counter == 1 else f'({counter})'}.mp4"
                )
                if not output_path.exists():
                    break
                counter += 1

            list_file = MERGE_OUTPUT_DIR / "filelist.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for path, _ in self.merge_video_list:
                    f.write(f"file '{path.replace(os.sep, '/')}'\n")

            speed_str = self.merge_speed.get().strip()
            audio_mode_text = self.audio_mode_var.get()
            audio_mode_map = {"保持原音频": "none", "替换音频": "replace", "叠加音频": "mix"}
            audio_mode = audio_mode_map.get(audio_mode_text, "none")

            use_music_finish = (
                speed_str == "到音乐放完"
                and audio_mode in ("replace", "mix")
                and self.merge_audio_file
            )

            if use_music_finish:
                temp_merged = MERGE_OUTPUT_DIR / "temp_merge_for_music.mp4"
                cmd_concat = [
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
                    str(list_file),
                    "-c",
                    "copy",
                    "-y",
                    str(temp_merged),
                ]
                self.status_label.config(text="正在合并视频（第一步）...", foreground="blue")
                proc = subprocess.Popen(
                    cmd_concat,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=SUBPROCESS_CREATE_NO_WINDOW,
                )
                for line in iter(proc.stdout.readline, ""):
                    self._append_log_line(line.rstrip())
                rc = proc.wait()
                try:
                    list_file.unlink(missing_ok=True)
                except Exception:
                    pass
                if rc != 0:
                    self.after(
                        0, self._on_merge_batch_done, False, "合并临时视频失败"
                    )
                    return
                video_dur = self._get_media_duration(str(temp_merged))
                audio_dur = self._get_media_duration(self.merge_audio_file)
                if video_dur is None or audio_dur is None or audio_dur <= 0:
                    speed = 1.0
                    self._append_log_line("无法获取合并视频或音频时长，按 1 倍速输出。")
                else:
                    speed = video_dur / audio_dur
                    if speed > 5 or speed < 1:
                        self._append_log_line(
                            f"警告：到音乐放完倍速为 {speed:.2f}，超出建议范围 [1, 5]，仍继续处理。"
                        )
                self.status_label.config(
                    text="正在合并视频（第二步，到音乐放完）...", foreground="blue"
                )
                if audio_mode == "replace":
                    # 视频加速以适配音乐时长，音乐保持原速
                    cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-i",
                        str(temp_merged),
                        "-i",
                        self.merge_audio_file,
                        "-filter_complex",
                        f"[0:v]setpts={1/speed}*PTS[v];[1:a]anull[a]",
                        "-map",
                        "[v]",
                        "-map",
                        "[a]",
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-shortest",
                        "-y",
                        str(output_path),
                    ]
                else:
                    # 视频加速，视频原声也加速以同步，音乐保持原速后混合
                    cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-i",
                        str(temp_merged),
                        "-i",
                        self.merge_audio_file,
                        "-filter_complex",
                        f"[0:v]setpts={1/speed}*PTS[v];"
                        f"[0:a]atempo={speed}[a0];"
                        "[a0][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]",
                        "-map",
                        "[v]",
                        "-map",
                        "[a]",
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-y",
                        str(output_path),
                    ]
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
                    self._append_log_line(line.rstrip())
                rc = proc.wait()
                try:
                    temp_merged.unlink(missing_ok=True)
                except Exception:
                    pass
                if rc == 0:
                    self.after(0, self._on_merge_batch_done, True, str(output_path))
                else:
                    self.after(
                        0,
                        self._on_merge_batch_done,
                        False,
                        f"合并失败 (返回码 {rc})",
                    )
                return

            speed = float(speed_str) if speed_str != "到音乐放完" else 1.0

            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-stats"]

            if audio_mode == "none":
                if speed == 1.0:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-c",
                            "copy",
                            "-y",
                            str(output_path),
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-filter_complex",
                            f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={speed}[a]",
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-y",
                            str(output_path),
                        ]
                    )
            elif audio_mode == "replace":
                if speed == 1.0:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-i",
                            self.merge_audio_file,
                            "-c:v",
                            "copy",
                            "-c:a",
                            "aac",
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-shortest",
                            "-y",
                            str(output_path),
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-i",
                            self.merge_audio_file,
                            "-filter_complex",
                            f"[0:v]setpts={1/speed}*PTS[v];[1:a]atempo={speed}[a]",
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-shortest",
                            "-y",
                            str(output_path),
                        ]
                    )
            elif audio_mode == "mix":
                if speed == 1.0:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-i",
                            self.merge_audio_file,
                            "-filter_complex",
                            "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                            "-c:v",
                            "copy",
                            "-map",
                            "0:v:0",
                            "-map",
                            "[aout]",
                            "-c:a",
                            "aac",
                            "-y",
                            str(output_path),
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            str(list_file),
                            "-i",
                            self.merge_audio_file,
                            "-filter_complex",
                            f"[0:v]setpts={1/speed}*PTS[v];"
                            "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout];"
                            f"[aout]atempo={speed}[a]",
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-y",
                            str(output_path),
                        ]
                    )

            self.status_label.config(text="正在合并视频...", foreground="blue")
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
                self._append_log_line(line.rstrip())
            rc = proc.wait()

            try:
                list_file.unlink(missing_ok=True)
            except Exception:
                pass

            if rc == 0:
                self.after(0, self._on_merge_batch_done, True, str(output_path))
            else:
                self.after(
                    0,
                    self._on_merge_batch_done,
                    False,
                    f"合并失败 (返回码 {rc})",
                )

        except Exception as e:
            self.after(0, self._on_merge_batch_done, False, str(e))

    def _on_merge_batch_done(self, success: bool, result: str) -> None:
        self.merge_run_btn.config(state="normal", text="开始合并")
        self.status_label.config(text="待机中", foreground="blue")
        # 恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)  # type: ignore[call-arg]

        if success:
            msg = f"合并成功: {os.path.basename(result)}"
            if ENABLE_NOTIFICATION and notification:
                notification.notify(
                    title="视频合并",
                    message=msg,
                    timeout=4,
                    app_name="VideoTools",
                )
            else:
                self.status_label.config(text=msg)
        else:
            self.status_label.config(text=f"合并失败: {result}", foreground="red")


__all__ = ["MergeMixin"]
