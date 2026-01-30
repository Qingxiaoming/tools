import os
import threading
from datetime import datetime
from typing import List, Tuple

import tkinter as tk
from tkinter import scrolledtext, ttk

try:
    from .config import DOC_OUTPUT_DIR, VIDEO_NATURE_LIST, ENABLE_NOTIFICATION, notification
except ImportError:
    from config import DOC_OUTPUT_DIR, VIDEO_NATURE_LIST, ENABLE_NOTIFICATION, notification


class DocMixin:
    """文档生成相关 UI 与业务逻辑。"""

    # 依赖主类提供：
    # - self.doc_frame, self.status_label, self.log
    # - self.doc_video_list
    # - self._append_log_line, self._clear_log

    def _create_doc_widgets(self) -> None:
        self.doc_video_label = ttk.Label(
            self.doc_frame, text="请拖入一个或多个视频文件", foreground="grey"
        )
        self.doc_video_label.pack(pady=3)

        ttk.Label(self.doc_frame, text="视频文件列表:").pack(anchor="w", padx=10)
        self.doc_text = scrolledtext.ScrolledText(
            self.doc_frame, width=60, height=9, font=("Consolas", 9)
        )
        self.doc_text.pack(padx=10, pady=2)
        self.doc_text.config(state="disabled")

        input_frame = ttk.Frame(self.doc_frame)
        input_frame.pack(fill="x", padx=10, pady=2)

        ttk.Label(input_frame, text="属于活动:").pack(side="left")
        self.doc_activity = tk.StringVar()
        activity_entry = ttk.Entry(
            input_frame, textvariable=self.doc_activity, width=15
        )
        activity_entry.pack(side="left", padx=10)

        ttk.Label(input_frame, text="BV号:").pack(side="left", padx=(20, 5))
        self.doc_bv = tk.StringVar()
        bv_entry = ttk.Entry(input_frame, textvariable=self.doc_bv, width=15)
        bv_entry.pack(side="left", padx=5)

        btn_frame = ttk.Frame(self.doc_frame)
        btn_frame.pack(fill="x", padx=10, pady=4)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_doc_list).pack(
            side="left", padx=4
        )
        self.doc_run_btn = ttk.Button(
            btn_frame, text="生成文档", command=self.run_doc_generation
        )
        self.doc_run_btn.pack(side="right", padx=4)

    def _handle_drop_doc(self, files: List[str]) -> None:
        added_files: List[str] = []
        for f in files:
            if not os.path.isfile(f):
                continue
            ext = os.path.splitext(f)[-1].lower()
            if ext not in (".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"):
                continue
            item = (f, os.path.basename(f))
            if item not in self.doc_video_list:
                self.doc_video_list.append(item)
                added_files.append(item[1])

        if added_files:
            self.doc_text.config(state="normal")
            for filename in added_files:
                self.doc_text.insert("end", filename + "\n")
            self.doc_text.config(state="disabled")
            self.doc_video_label.config(
                text=f"已载入 {len(self.doc_video_list)} 个视频文件", foreground="black"
            )

    def clear_doc_list(self) -> None:
        self.doc_video_list.clear()
        self.doc_text.config(state="normal")
        self.doc_text.delete("1.0", "end")
        self.doc_text.config(state="disabled")
        self.doc_video_label.config(
            text="请拖入一个或多个视频文件", foreground="grey"
        )

    def _extract_operator_list(self, filename: str) -> List[str]:
        base = os.path.splitext(filename)[0]
        if "_" not in base:
            return ["未知"]
        op_field = base.split("_")[-1]
        return [op.strip() for op in op_field.split("+") if op.strip()]

    def _extract_nature(self, filename: str) -> str:
        for n in VIDEO_NATURE_LIST:
            if n in filename:
                return n
        return "普通"

    def _extract_stage_name(self, filename: str) -> str:
        base, _ = os.path.splitext(filename)
        part = base.split("_")[0] if "_" in base else base
        raw = part
        for n in VIDEO_NATURE_LIST:
            part = part.replace(n, "")
        part = part.strip("_- ")
        return part if part else raw

    def run_doc_generation(self) -> None:
        if not self.doc_video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return

        activity = self.doc_activity.get().strip()
        bv = self.doc_bv.get().strip()
        self.doc_run_btn.config(state="disabled", text="生成中")
        self._clear_log()
        threading.Thread(
            target=self._doc_generation_thread, args=(activity, bv), daemon=True
        ).start()

    def _doc_generation_thread(self, activity: str, bv: str) -> None:
        success: List[str] = []
        fail: List[str] = []

        DOC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for video_path, video_name in self.doc_video_list:
            try:
                ops = self._extract_operator_list(video_name)
                nature = self._extract_nature(video_name)
                stage = self._extract_stage_name(video_name)

                md_path = DOC_OUTPUT_DIR / f"{stage}.md"

                ops_yaml = "\n".join(f"  - {op}" for op in ops)
                content = f"""---
属于活动:
  - {activity}
是否完成: true
bv号: {bv}
关卡难度:
  - {nature}
备注: 无
参战干员:
{ops_yaml}
攻略者: 项泓小时候/
创建时间: {datetime.today().strftime('%Y/%m/%d')}
---
# 本地视频
![[{video_name}]]
"""

                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(content)

                success.append(f"{video_name} -> {stage}.md")
                self._append_log_line(f"已生成: {stage}.md")

            except Exception as e:
                fail.append(f"{video_name} ({str(e)})")

        self.after(0, self._on_doc_generation_done, success, fail)

    def _on_doc_generation_done(self, success: List[str], fail: List[str]) -> None:
        self.doc_run_btn.config(state="normal", text="生成文档")
        self.status_label.config(text="待机中", foreground="blue")

        msg = f"成功生成 {len(success)} 个文档，失败 {len(fail)} 个"
        if ENABLE_NOTIFICATION and notification:
            notification.notify(
                title="文档生成",
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


__all__ = ["DocMixin"]
