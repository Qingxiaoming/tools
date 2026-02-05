import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import tkinter as tk
from tkinter import scrolledtext, ttk

try:
    from .config import (
        DOC_OUTPUT_DIR,
        DOC_TRANSFER_DOC_DIR,
        DOC_TRANSFER_MEDIA_DIR,
        VIDEO_NATURE_LIST,
        ENABLE_NOTIFICATION,
        notification,
    )
except ImportError:
    from config import (  # type: ignore
        DOC_OUTPUT_DIR,
        DOC_TRANSFER_DOC_DIR,
        DOC_TRANSFER_MEDIA_DIR,
        VIDEO_NATURE_LIST,
        ENABLE_NOTIFICATION,
        notification,
    )


class DocMixin:
    """文档生成与转运模块。"""

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

        # 记录“本次文档生成”产生的 md 文件名集合，用于限制转运范围
        self.doc_generated_md_names: set[str] = set()

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

    # 供主程序通过右箭头传递视频列表时调用
    def _set_doc_videos_from_paths(self, files: List[str], overwrite: bool = True) -> None:
        """根据给定路径列表更新文档生成输入列表。"""
        if overwrite:
            self.doc_video_list.clear()
            self.doc_text.config(state="normal")
            self.doc_text.delete("1.0", "end")
        added_files: List[str] = []
        for f in files:
            if not os.path.isfile(f):
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
        # 开始新一轮文档生成前，清空“本次生成”的文档记录
        self.doc_generated_md_names.clear()
        # 文档生成期间禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
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

                # 记录本次生成的 md 文件名，用于后续“转运”过滤
                try:
                    self.doc_generated_md_names.add(md_path.name)
                except Exception:
                    # 若属性不存在或类型异常，不影响主流程
                    pass

                success.append(f"{video_name} -> {stage}.md")
                self._append_log_line(f"已生成: {stage}.md")

            except Exception as e:
                fail.append(f"{video_name} ({str(e)})")

        self.after(0, self._on_doc_generation_done, success, fail)

    def _on_doc_generation_done(self, success: List[str], fail: List[str]) -> None:
        self.doc_run_btn.config(state="normal", text="生成文档")
        self.status_label.config(text="待机中", foreground="blue")
        # 文档生成结束后恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)  # type: ignore[call-arg]

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

    # ------------------------- 文档与视频转运 -------------------------
    def run_doc_transfer(self) -> None:
        """将 DOC_OUTPUT_DIR 中的文档及其引用的视频剪切到 config 指定目录。"""
        md_files = list(Path(DOC_OUTPUT_DIR).glob("*.md"))
        # 只允许转运“本次文档生成”产生的文档，避免误操作历史文件
        generated_names = getattr(self, "doc_generated_md_names", set())
        if generated_names:
            md_files = [p for p in md_files if p.name in generated_names]
            # 若记录的文档与实际文件不一致，则报错并终止本次转运
            missing_docs = [name for name in generated_names if not (DOC_OUTPUT_DIR / name).is_file()]
            if missing_docs:
                self.status_label.config(
                    text=f"本轮生成的文档缺失，无法转运: {', '.join(missing_docs)}",
                    foreground="red",
                )
                return
        if not md_files:
            self.status_label.config(
                text="当前没有本次生成的可转运文档", foreground="red"
            )
            return

        # 转运期间禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)  # type: ignore[call-arg]
        self._clear_log()
        threading.Thread(
            target=self._doc_transfer_thread, args=(md_files,), daemon=True
        ).start()

    def _doc_transfer_thread(self, md_files: List[Path]) -> None:
        DOC_TRANSFER_DOC_DIR.mkdir(parents=True, exist_ok=True)
        DOC_TRANSFER_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

        # 载入视频列表：按文件名可反查完整路径（转运时若输出目录没有该视频则从这里取）
        video_path_by_name = {
            name: Path(path) for path, name in getattr(self, "doc_video_list", [])
        }

        moved_docs = 0
        moved_videos = 0
        skipped = 0

        for md_path in md_files:
            try:
                text = md_path.read_text(encoding="utf-8")
            except Exception as e:
                skipped += 1
                self._append_log_line(f"{md_path.name}  (读取失败: {e})")
                continue

            # 提取所有 ![[...]] 引用，允许多个
            refs = list({m.group(1).strip() for m in re.finditer(r"!\[\[(.+?)\]\]", text)})

            doc_target = DOC_TRANSFER_DOC_DIR / md_path.name

            # 若目标文档目录已存在同名 md，则整组跳过
            if doc_target.exists():
                skipped += 1
                self._append_log_line(
                    f"{md_path.name}  (目标文档目录已存在同名文件，已跳过文档及其视频)"
                )
                continue

            # 没有任何视频引用：仅转运 md
            if not refs:
                try:
                    shutil.move(str(md_path), str(doc_target))
                    moved_docs += 1
                    self._append_log_line(f"已转运文档: {md_path.name}")
                except Exception as e:
                    skipped += 1
                    self._append_log_line(f"{md_path.name}  (转运文档失败: {e})")
                continue

            missing_refs: List[str] = []
            conflict_refs: List[str] = []
            # 每个引用的解析结果：(引用名, 源文件路径)。源优先在文档输出目录，否则从载入视频列表按文件名取
            ref_src_list: List[Tuple[str, Path]] = []

            for ref in refs:
                src = DOC_OUTPUT_DIR / ref
                if not src.is_file():
                    src = video_path_by_name.get(ref)
                    if src is None or not src.is_file():
                        missing_refs.append(ref)
                        continue
                ref_src_list.append((ref, Path(src)))
                target = DOC_TRANSFER_MEDIA_DIR / ref
                if target.exists():
                    conflict_refs.append(ref)

            # 若有缺失或同名冲突：视频和 md 都不剪切，仅记录日志
            if missing_refs or conflict_refs:
                skipped += 1
                if missing_refs:
                    self._append_log_line(
                        f"{md_path.name}  (引用视频缺失: {', '.join(missing_refs)})"
                    )
                if conflict_refs:
                    self._append_log_line(
                        f"{md_path.name}  (目标视频目录已存在同名文件: {', '.join(conflict_refs)})"
                    )
                continue

            # 可以安全转运：将同组的文档和所有引用视频作为一个事务处理
            moves_done: List[tuple[Path, Path]] = []
            group_failed = False

            # 先移动 md
            try:
                shutil.move(str(md_path), str(doc_target))
                moves_done.append((doc_target, md_path))  # 记录为 (当前路径, 回滚目标)
                self._append_log_line(f"已转运文档: {md_path.name}")
            except Exception as e:
                skipped += 1
                self._append_log_line(f"{md_path.name}  (转运文档失败: {e})")
                group_failed = True

            # 再移动所有引用的视频（使用已解析的源路径：输出目录或载入列表）
            if not group_failed:
                for ref, src in ref_src_list:
                    target = DOC_TRANSFER_MEDIA_DIR / ref
                    try:
                        shutil.move(str(src), str(target))
                        moves_done.append((target, src))  # 记录为 (当前路径, 回滚目标)
                        self._append_log_line(f"已转运视频: {ref}")
                    except Exception as e:
                        self._append_log_line(f"{ref}  (转运视频失败: {e})")
                        group_failed = True
                        break

            # 如有任何一步失败，回滚本组已移动的所有文件
            if group_failed:
                for current, original in reversed(moves_done):
                    try:
                        if current.exists():
                            shutil.move(str(current), str(original))
                    except Exception as e:
                        self._append_log_line(
                            f"{current.name}  (回滚失败，请手动检查位置: {e})"
                        )
                skipped += 1
            else:
                moved_docs += 1
                moved_videos += len(ref_src_list)

        self.after(0, self._on_doc_transfer_done, moved_docs, moved_videos, skipped)

    def _on_doc_transfer_done(
        self, moved_docs: int, moved_videos: int, skipped: int
    ) -> None:
        self.status_label.config(text="待机中", foreground="blue")
        # 转运结束后恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)  # type: ignore[call-arg]

        msg = (
            f"转运完成：文档 {moved_docs} 个，视频 {moved_videos} 个，"
            f"跳过 {skipped} 个文档"
        )
        if ENABLE_NOTIFICATION and notification:
            try:
                notification.notify(
                    title="文档转运",
                    message=msg,
                    timeout=4,
                    app_name="VideoTools",
                )
            except Exception:
                self.status_label.config(text=msg)
        else:
            self.status_label.config(text=msg)


__all__ = ["DocMixin"]
