"""合并/录屏整理等页签共用的列表管理、拖拽排序与批量任务收尾逻辑。"""

from __future__ import annotations

import os
from typing import List, Tuple

import tkinter as tk

from .config import ENABLE_NOTIFICATION, notification

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts")


class ListboxMixin:
    """视频列表（Listbox）的刷新、增删、上下移与拖拽排序。"""

    def _listbox_update(self, listbox: tk.Listbox, video_list: List[Tuple[str, str]]) -> None:
        listbox.delete(0, tk.END)
        for i, (_, name) in enumerate(video_list):
            listbox.insert(tk.END, f"{i + 1}. {name}")

    def _listbox_clear(self, listbox, video_list, empty_text: str, label) -> None:
        video_list.clear()
        self._listbox_update(listbox, video_list)
        label.config(text=empty_text, foreground="grey")

    def _listbox_remove_selected(self, listbox, video_list, label) -> None:
        selection = listbox.curselection()
        if not selection:
            self.status_label.config(text="请先选择要删除的视频", foreground="red")
            return
        index = selection[0]
        if 0 <= index < len(video_list):
            del video_list[index]
            self._listbox_update(listbox, video_list)
            label.config(text=f"已载入 {len(video_list)} 个视频文件", foreground="black")

    def _listbox_move(self, listbox, video_list, delta: int) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        target = index + delta
        if target < 0 or target >= len(video_list):
            return
        video_list[index], video_list[target] = video_list[target], video_list[index]
        self._listbox_update(listbox, video_list)
        listbox.selection_set(target)

    def _listbox_bind_drag(self, listbox: tk.Listbox, video_list) -> None:
        """绑定 Listbox 拖拽排序事件（共用单一拖拽状态）。"""
        self._listbox_drag_start: int | None = None
        listbox.bind("<Button-1>", self._listbox_on_drag_click)
        listbox.bind("<B1-Motion>", lambda e: self._listbox_on_drag_motion(e, listbox))
        listbox.bind(
            "<ButtonRelease-1>",
            lambda e: self._listbox_on_drag_release(e, listbox, video_list),
        )

    def _listbox_on_drag_click(self, event) -> None:
        self._listbox_drag_start = event.y

    def _listbox_on_drag_motion(self, event, listbox) -> None:
        if self._listbox_drag_start is None:
            return
        current_index = listbox.nearest(event.y)
        if current_index != -1:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(current_index)

    def _listbox_on_drag_release(self, event, listbox, video_list) -> None:
        if self._listbox_drag_start is None:
            return
        start_index = listbox.nearest(self._listbox_drag_start)
        end_index = listbox.nearest(event.y)
        if (
            start_index != end_index
            and 0 <= start_index < len(video_list)
            and 0 <= end_index < len(video_list)
        ):
            item = video_list.pop(start_index)
            video_list.insert(end_index, item)
            self._listbox_update(listbox, video_list)
            listbox.selection_set(end_index)
        self._listbox_drag_start = None


class DropMixin:
    """各页签共用的拖入过滤与批量任务收尾。"""

    def _handle_drop_video_files(self, files, apply_callback) -> None:
        """过滤视频扩展名后交给异步路径检测回调。"""
        candidates = [
            f
            for f in files
            if os.path.isfile(f)
            and os.path.splitext(f)[-1].lower() in VIDEO_EXTENSIONS
        ]
        if not candidates:
            return
        self._resolve_paths_for_use_async(candidates, apply_callback)

    def _on_batch_done(
        self,
        run_btn,
        btn_text: str,
        title: str,
        success,
        fail,
        msg_format: str = "成功 {ok} 个，失败 {bad} 个",
        log_fail: bool = False,
    ) -> None:
        """批量任务收尾：恢复按钮、状态栏、系统通知、失败列表日志。"""
        self._batch_in_progress = False
        run_btn.config(state="normal", text=btn_text)
        self.status_label.config(text="待机中", foreground="blue")
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)
        msg = msg_format.format(ok=len(success), bad=len(fail))
        if ENABLE_NOTIFICATION and notification:
            try:
                notification.notify(
                    title=title, message=msg, timeout=4, app_name="VideoTools"
                )
            except Exception:
                self.status_label.config(text=msg)
        else:
            self.status_label.config(text=msg)
        if log_fail and fail:
            self._append_log_line("失败列表：")
            for f in fail:
                self._append_log_line("  " + f)
