import os
import re
import shutil
import threading
from pathlib import Path
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox

from ..core.config import (
    DOC_OUTPUT_DIR,
    DOC_TRANSFER_DOC_DIR,
    DOC_TRANSFER_MEDIA_DIR,
    ENABLE_NOTIFICATION,
    UI_FONT_FAMILY,
    MONO_FONT_FAMILY,
    notification,
)
from ..services.md_templates import get_template_manager, MdTemplate


class DocMixin:
    """文档生成与转运模块（表格形式视频列表）。"""

    def _create_doc_widgets(self) -> None:
        # 初始化模板管理器
        self._template_manager = get_template_manager()
        # 每个视频的状态：{video_name: {"content": str, "template_name": str}}
        self._video_state: dict[str, dict] = {}
        # 上次注入的值：{var_name: value}
        self._last_inject_values: dict[str, str] = {}

        # ===== 顶部：拖入提示 =====
        self.doc_video_label = ttk.Label(
            self.doc_frame, text="请拖入一个或多个视频文件", foreground="grey"
        )
        self.doc_video_label.pack(pady=(5, 3))

        # ===== 视频列表区（表格形式） =====
        list_frame = ttk.LabelFrame(self.doc_frame, text="视频文件列表", padding=(5, 5))
        list_frame.pack(fill="both", expand=True, padx=10, pady=2)

        # 列表框（使用 Treeview 实现表格）
        self.doc_tree = ttk.Treeview(
            list_frame,
            columns=("name", "template"),
            show="headings",
            height=6,
        )
        self.doc_tree.heading("name", text="视频名称")
        self.doc_tree.heading("template", text="模板")
        self.doc_tree.column("name", width=240)
        self.doc_tree.column("template", width=80, anchor="center")
        self.doc_tree.pack(fill="both", expand=True, pady=(5, 0))

        # 绑定双击编辑事件
        self.doc_tree.bind("<Double-1>", self._on_tree_double_click)

        # 创建右键菜单
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(
            label="✏️ 编辑", command=lambda: self._on_context_action("edit")
        )
        self._context_menu.add_command(
            label="🗑️ 删除", command=lambda: self._on_context_action("delete")
        )

        # 绑定右键事件
        self.doc_tree.bind("<Button-3>", self._on_tree_right_click)
        self.doc_tree.bind("<Button-2>", self._on_tree_right_click)  # macOS

        # ===== 批量元数据注入按钮（右对齐）=====
        inject_btn_frame = ttk.Frame(self.doc_frame)
        inject_btn_frame.pack(fill="x", padx=10, pady=2)
        self._inject_btn = ttk.Button(
            inject_btn_frame,
            text="📋 批量注入元数据",
            command=self._show_inject_dialog,
        )
        self._inject_btn.pack(side="right", padx=2)

        # ===== 底部按钮区 =====
        btn_frame = ttk.Frame(self.doc_frame)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="清空列表", command=self.clear_doc_list).pack(
            side="left", padx=2
        )

        self.doc_run_btn = ttk.Button(
            btn_frame, text="生成文档", command=self.run_doc_generation
        )
        self.doc_run_btn.pack(side="right", padx=4)

        # 记录"本次文档生成"产生的 md 文件名集合，用于限制转运范围
        self.doc_generated_md_names: set[str] = set()

        # 当前选中的视频索引
        self._current_preview_index: int = 0

    # ------------------------- 表格操作 -------------------------

    def _refresh_tree(self) -> None:
        """刷新表格显示。"""
        # 清空现有内容
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        # 填充数据
        for i, (video_path, video_name) in enumerate(self.doc_video_list):
            # 优先使用记录的模板名，否则重新匹配
            template_name = self._video_state.get(video_name, {}).get("template_name")
            if template_name is None:
                template = self._get_template_for_video(video_name, video_path)
                template_name = template.name
            self.doc_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(video_name, template_name),
            )

        # 更新标签
        if self.doc_video_list:
            self.doc_video_label.config(
                text=f"已载入 {len(self.doc_video_list)} 个视频文件", foreground="black"
            )
        else:
            self.doc_video_label.config(
                text="请拖入一个或多个视频文件", foreground="grey"
            )

        # 更新注入按钮状态
        self._update_inject_button_state()

    def _on_tree_double_click(self, event) -> None:
        """处理表格双击事件 - 打开编辑。"""
        item = self.doc_tree.identify_row(event.y)
        if not item:
            return

        index = int(item)
        if index < 0 or index >= len(self.doc_video_list):
            return

        # 双击打开编辑
        self._open_content_editor(index)

    def _on_tree_right_click(self, event) -> None:
        """处理表格右键事件 - 显示菜单。"""
        item = self.doc_tree.identify_row(event.y)
        if not item:
            return

        index = int(item)
        if index < 0 or index >= len(self.doc_video_list):
            return

        # 选中该项
        self.doc_tree.selection_set(item)
        self._context_menu_index = index

        # 显示右键菜单
        self._context_menu.post(event.x_root, event.y_root)

    def _on_context_action(self, action: str) -> None:
        """右键菜单动作：edit=打开编辑，delete=删除。"""
        if not hasattr(self, "_context_menu_index"):
            return
        if action == "edit":
            self._open_content_editor(self._context_menu_index)
        elif action == "delete":
            self._delete_video_item(self._context_menu_index)

    def _extract_template_placeholders(self, content: str) -> list[str]:
        """从模板内容中提取所有可注入的 ${inject:xxx} 占位符变量名。"""
        # 只匹配 ${inject:var} 格式的可注入占位符
        pattern = r"\$\{inject:(\w+)\}"
        matches = re.findall(pattern, content)
        # 去重并保持顺序
        result = []
        for var_name in matches:
            if var_name not in result:
                result.append(var_name)
        return result

    def _update_inject_button_state(self) -> None:
        """更新批量注入按钮状态：有未注入视频时可用，否则禁用。"""
        if not self.doc_video_list:
            self._inject_btn.config(state="disabled")
            return

        # 检查是否有未注入的视频
        has_uninjected = any(
            not self._video_state.get(video_name, {}).get("injected", False)
            for _, video_name in self.doc_video_list
        )

        if has_uninjected:
            self._inject_btn.config(state="normal")
        else:
            self._inject_btn.config(state="disabled")

    def _show_inject_dialog(self) -> None:
        """显示批量注入弹窗，编辑变量名→值映射，应用到所有视频。"""
        if not self.doc_video_list:
            self.status_label.config(text="请先拖入视频文件", foreground="red")
            return

        # 准备数据：每个视频的模板内容和其占位符
        video_data = []  # [(video_name, content, placeholders_set), ...]
        all_placeholder_names = []  # 所有出现过的占位符名（去重）

        for video_path, video_name in self.doc_video_list:
            # 使用用户实际选择的模板重新生成内容（而不是使用可能过期的缓存）
            template_name = self._video_state.get(video_name, {}).get("template_name")
            template = (
                self._template_manager.get_template(template_name)
                if template_name else None
            )
            content, used_template = self._generate_content_for_video(
                video_path, video_name, template=template
            )
            self._video_state[video_name] = {
                "content": content,
                "template_name": used_template.name,
            }

            # 提取占位符
            placeholders = set(self._extract_template_placeholders(content))
            video_data.append((video_name, content, placeholders))

            # 收集所有占位符名
            for ph in placeholders:
                if ph not in all_placeholder_names:
                    all_placeholder_names.append(ph)

        if not all_placeholder_names:
            self.status_label.config(text="当前视频模板没有可注入的变量", foreground="orange")
            return

        # 筛选出未注入的视频
        uninjected_videos = [
            (vp, vn, phs) for vp, vn, phs in video_data
            if not self._video_state.get(vn, {}).get("injected", False)
        ]

        if not uninjected_videos:
            self.status_label.config(text="所有视频已注入，无需重复操作", foreground="green")
            return

        # 创建弹窗
        dialog = tk.Toplevel(self)
        dialog.title(f"批量注入元数据 ({len(uninjected_videos)}个新视频)")
        dialog.geometry("450x350")
        dialog.transient(self)
        self._safe_grab_set(dialog)

        # 标题
        ttk.Label(
            dialog,
            text="填写元数据值（留空表示不注入该字段）：",
            font=(UI_FONT_FAMILY, 9),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # 表格区域：变量名 → 值
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        tree = ttk.Treeview(
            tree_frame,
            columns=("var_name", "var_value"),
            show="headings",
            height=8,
        )
        tree.heading("var_name", text="变量名")
        tree.heading("var_value", text="值")
        tree.column("var_name", width=150)
        tree.column("var_value", width=250)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 填充数据：每行是一个变量名，值使用上次注入的缓存（如果有）
        for ph in all_placeholder_names:
            default_value = self._last_inject_values.get(ph, "")
            tree.insert("", "end", iid=ph, values=(ph, default_value))

        def on_double_click(event):
            """双击单元格进行编辑（只编辑值列）。"""
            region = tree.identify_region(event.x, event.y)
            if region != "cell":
                return

            column = tree.identify_column(event.x)
            row = tree.identify_row(event.y)
            if not row or column != "#2":  # 只编辑第2列（值列）
                return

            # 获取当前值
            current_values = list(tree.item(row, "values"))

            # 创建编辑框
            bbox = tree.bbox(row, column)
            if not bbox:
                return

            x, y, width, height = bbox

            entry = ttk.Entry(tree)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, current_values[1])
            entry.focus()
            entry.select_range(0, tk.END)

            def save_edit(event=None):
                new_value = entry.get()
                current_values[1] = new_value
                tree.item(row, values=current_values)
                entry.destroy()

            def cancel_edit(event=None):
                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", save_edit)
            entry.bind("<Escape>", cancel_edit)

        tree.bind("<Double-1>", on_double_click)

        # 底部按钮区
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        # 注入按钮
        def do_inject():
            """执行注入：每个视频只注入自己模板中存在的变量。"""
            # 获取用户填入的值映射，并缓存非空值
            value_map = {}
            for ph in all_placeholder_names:
                item = tree.item(ph)
                values = item["values"]
                if len(values) >= 2:
                    value_map[ph] = values[1]
                    # 缓存非空值供下次使用
                    if values[1]:
                        self._last_inject_values[ph] = values[1]

            # 应用到未注入的视频
            count = 0
            for video_name, content, placeholders in uninjected_videos:
                new_content = content
                injected_any = False

                # 只注入该视频模板中存在的变量
                for ph in placeholders:
                    ph_value = str(value_map.get(ph, ""))
                    if ph_value:  # 只注入非空值
                        placeholder = "${inject:" + ph + "}"
                        new_content = new_content.replace(placeholder, ph_value)
                        injected_any = True

                if injected_any:
                    self._video_state[video_name] = {
                        "content": new_content,
                        "template_name": self._video_state.get(video_name, {}).get("template_name", ""),
                        "injected": True,  # 标记为已注入
                    }
                    count += 1

            # 禁用编辑提示
            ttk.Label(
                btn_frame,
                text="✓ 已注入（如需修改请在视频列表中双击编辑）",
                foreground="green",
            ).pack(side="left", padx=5)

            # 禁用注入按钮和表格编辑
            inject_btn.config(state="disabled")
            tree.unbind("<Double-1>")

            self.status_label.config(
                text=f"已注入 {count} 个新视频，现有视频已全部注入完成", foreground="green"
            )

            # 更新主界面注入按钮状态
            self._update_inject_button_state()

            # 自动关闭弹窗
            dialog.destroy()

        inject_btn = ttk.Button(btn_frame, text="💉 执行注入", command=do_inject)
        inject_btn.pack(side="right", padx=5)

        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(
            side="right", padx=5
        )

        # 窗口居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _delete_video_item(self, index: int) -> None:
        """删除指定索引的视频。"""
        if index < 0 or index >= len(self.doc_video_list):
            return

        video_path, video_name = self.doc_video_list[index]
        if messagebox.askyesno("确认删除", f"确定要删除 {video_name} 吗？"):
            # 从列表中移除
            del self.doc_video_list[index]
            # 从缓存中移除
            self._video_state.pop(video_name, None)
            # 更新显示
            self._refresh_tree()
            self.status_label.config(text=f"已删除 {video_name}", foreground="blue")

    # ------------------------- 内容编辑弹窗 -------------------------

    def _safe_grab_set(self, win: tk.Toplevel) -> None:
        """安全抢焦点：X11 上窗口尚未映射时 grab_set 会抛 TclError，等可见后再试。"""
        try:
            win.grab_set()
        except tk.TclError:
            try:
                win.wait_visibility()
                win.grab_set()
            except tk.TclError:
                pass

    def _open_content_editor(self, index: int) -> None:
        """打开内容编辑弹窗。"""
        if not self.doc_video_list or index < 0 or index >= len(self.doc_video_list):
            return

        self._current_preview_index = index
        video_path, video_name = self.doc_video_list[index]

        # 如果没有缓存的内容，先生成
        if video_name not in self._video_state:
            content, template = self._generate_content_for_video(video_path, video_name)
            self._video_state[video_name] = {"content": content, "template_name": template.name}

        # 创建弹窗
        editor = tk.Toplevel(self)
        editor.title(f"编辑 - {video_name}")
        editor.geometry("550x600")
        editor.transient(self)
        self._safe_grab_set(editor)

        # 获取当前视频使用的模板名（从状态或重新匹配）
        state = self._video_state.get(video_name, {})
        current_template_name = state.get("template_name")
        if current_template_name:
            current_template = self._template_manager.get_template(current_template_name)
        else:
            current_template = self._get_template_for_video(video_name, video_path)

        # ===== 模板选择区 =====
        template_frame = ttk.LabelFrame(editor, text="模板选择", padding=(5, 5))
        template_frame.pack(fill="x", padx=10, pady=(10, 5))

        template_row = ttk.Frame(template_frame)
        template_row.pack(fill="x")

        ttk.Label(template_row, text="当前模板:").pack(side="left", padx=2)

        self._editor_template_var = tk.StringVar(value=current_template.name)
        self._editor_template_combo = ttk.Combobox(
            template_row,
            textvariable=self._editor_template_var,
            values=self._template_manager.get_template_names(),
            state="readonly",
            width=18,
        )
        self._editor_template_combo.pack(side="left", padx=5)
        self._editor_template_combo.bind("<<ComboboxSelected>>", lambda e: self._editor_change_template())

        ttk.Button(template_row, text="重新生成", command=self._editor_regenerate).pack(side="right", padx=2)

        # ===== 内容编辑区 =====
        content_frame = ttk.LabelFrame(editor, text="文档内容", padding=(5, 5))
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self._editor_text = scrolledtext.ScrolledText(
            content_frame, width=70, height=15, font=(MONO_FONT_FAMILY, 9), wrap=tk.NONE
        )
        self._editor_text.pack(fill="both", expand=True)

        # 加载当前内容
        self._editor_text.delete("1.0", "end")
        self._editor_text.insert("1.0", self._video_state.get(video_name, {}).get("content", ""))

        # ===== 底部按钮区 =====
        btn_frame = ttk.Frame(editor)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        # 导航按钮
        nav_left = ttk.Frame(btn_frame)
        nav_left.pack(side="left")
        ttk.Button(nav_left, text="◀ 上一个", command=lambda: self._editor_navigate(-1)).pack(side="left", padx=2)
        ttk.Button(nav_left, text="下一个 ▶", command=lambda: self._editor_navigate(1)).pack(side="left", padx=2)

        # 右侧操作按钮
        nav_right = ttk.Frame(btn_frame)
        nav_right.pack(side="right")
        ttk.Button(nav_right, text="💾 保存", command=lambda: self._editor_save(editor)).pack(side="left", padx=2)
        ttk.Button(nav_right, text="取消", command=editor.destroy).pack(side="left", padx=2)

        # 窗口居中
        editor.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - editor.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - editor.winfo_height()) // 2
        editor.geometry(f"+{x}+{y}")

        # 保存编辑器引用
        self._current_editor = editor

    def _editor_change_template(self) -> None:
        """在编辑器中切换模板（仅记录状态，不自动重新生成）。"""
        template_name = self._editor_template_var.get()
        self.status_label.config(text=f"已选择模板: {template_name}，点击重新生成应用", foreground="blue")

    def _editor_regenerate(self) -> None:
        """使用当前选中的模板重新生成内容。"""
        if not self.doc_video_list:
            return

        video_path, video_name = self.doc_video_list[self._current_preview_index]

        # 获取当前选中的模板
        template_name = self._editor_template_var.get()
        template = self._template_manager.get_template(template_name)

        # 使用选中的模板重新生成
        content, used_template = self._generate_content_for_video(
            video_path, video_name, template=template
        )

        # 更新状态
        self._video_state[video_name] = {"content": content, "template_name": used_template.name}

        # 更新文本框
        self._editor_text.delete("1.0", "end")
        self._editor_text.insert("1.0", content)

        self.status_label.config(
            text=f"已使用模板 [{used_template.name}] 重新生成内容", foreground="green"
        )
        self._refresh_tree()

    def _editor_navigate(self, delta: int) -> None:
        """在编辑器中切换到上一个/下一个视频。"""
        new_index = self._current_preview_index + delta
        if new_index < 0 or new_index >= len(self.doc_video_list):
            self.status_label.config(text="没有更多视频了", foreground="orange")
            return

        # 保存当前内容
        self._editor_save_current()

        # 关闭当前编辑器并打开新的
        if self._current_editor:
            self._current_editor.destroy()
        self._open_content_editor(new_index)

    def _editor_save(self, editor: tk.Toplevel) -> None:
        """保存编辑器中的内容并关闭。"""
        self._editor_save_current()
        editor.destroy()
        self.status_label.config(text="内容已保存", foreground="green")

    def _editor_save_current(self) -> None:
        """保存当前编辑器中的内容到缓存。"""
        if not self.doc_video_list or not hasattr(self, '_editor_text'):
            return

        video_path, video_name = self.doc_video_list[self._current_preview_index]
        edited_content = self._editor_text.get("1.0", "end-1c")
        state = self._video_state.get(video_name, {})
        state["content"] = edited_content
        self._video_state[video_name] = state

    # ------------------------- 文件拖入处理 -------------------------

    def _apply_doc_videos_resolved(
        self,
        resolved: List[str] | None,
        original_paths: List[str],
        *,
        overwrite: bool = False,
    ) -> bool:
        if not self._apply_ordered_paths_to_video_list(
            self.doc_video_list, original_paths, resolved, overwrite=overwrite
        ):
            return False
        # 自动生成预览内容
        self._refresh_all_previews()
        self._refresh_tree()
        return True

    def clear_doc_list(self) -> None:
        self.doc_video_list.clear()
        self._video_state.clear()
        self._last_inject_values.clear()
        self._refresh_tree()
        self.status_label.config(
            text="列表已清空", foreground="blue"
        )

    # ------------------------- 文档生成 -------------------------

    def _get_template_for_video(self, video_name: str, video_path: str = "") -> MdTemplate:
        """获取指定视频应该使用的模板（自动匹配；generic 恒匹配，作为兜底）。"""
        # 尝试自动匹配
        template = self._template_manager.match_template(video_name, video_path)
        if template is None:
            # 默认使用 taera 模板
            template = self._template_manager.get_template("taera")
        if template is None:
            # 如果没有 taera，使用第一个可用模板
            all_templates = self._template_manager.get_all_templates()
            if all_templates:
                template = all_templates[0]
            else:
                # 最后 fallback
                template = MdTemplate(name="default", template_dir=Path("."), priority=0)
        return template

    def _generate_content_for_video(
        self, video_path: str, video_name: str, template: Optional[MdTemplate] = None
    ) -> Tuple[str, MdTemplate]:
        """为指定视频生成文档内容。"""
        if template is None:
            template = self._get_template_for_video(video_name, video_path)

        # 提取信息：优先使用模板自定义 extract.py，缺省不提取（仅 filename）
        extracted = template.extract(video_name, video_path)

        # 渲染模板，保留注入占位符
        content = template.render(
            filename=video_name,
            extra_vars=extracted,
            preserve_placeholders=True,
        )

        # 记录使用的模板名和内容
        self._video_state[video_name] = {"content": content, "template_name": template.name}

        return content, template

    def _refresh_all_previews(self) -> None:
        """刷新所有视频的预览内容。"""
        for video_path, video_name in self.doc_video_list:
            if video_name not in self._video_state:
                content, template = self._generate_content_for_video(video_path, video_name)
                self._video_state[video_name] = {"content": content, "template_name": template.name}

    def run_doc_generation(self) -> None:
        if self._batch_in_progress or self._repair_in_progress:
            self.status_label.config(text="已有任务在处理中，请等待完成", foreground="red")
            return
        if not self.doc_video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return

        self._batch_in_progress = True
        original_paths = [p for p, _ in self.doc_video_list]
        self._resolve_paths_for_use_async(
            original_paths, self._start_doc_generation
        )

    def _start_doc_generation(
        self, resolved: List[str] | None, original_paths: List[str]
    ) -> None:
        if not self._apply_doc_videos_resolved(
            resolved, original_paths, overwrite=True
        ):
            self._batch_in_progress = False
            return

        self.doc_run_btn.config(state="disabled", text="生成中")
        self._clear_log()
        # 开始新一轮文档生成前，清空"本次生成"的文档记录
        self.doc_generated_md_names.clear()
        # 文档生成期间禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)
        # 快照文档视频列表，运行期间改列表不影响本次生成
        threading.Thread(
            target=self._doc_generation_thread,
            args=(list(self.doc_video_list),),
            daemon=True,
        ).start()

    def _doc_generation_thread(self, video_list) -> None:
        success: List[str] = []
        fail: List[str] = []

        DOC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for video_path, video_name in video_list:
            try:
                # 输出文件名同样使用模板提取的 stage（缺省用文件名主体）
                template_name = self._video_state.get(video_name, {}).get("template_name")
                template = (
                    self._template_manager.get_template(template_name)
                    if template_name else None
                )
                if template is None:
                    template = self._get_template_for_video(video_name, video_path)
                extracted = template.extract(video_name, video_path)
                stage = extracted.get("stage") or os.path.splitext(video_name)[0]
                md_path = DOC_OUTPUT_DIR / f"{stage}.md"

                # 使用缓存的内容（可能经过编辑）
                if video_name in self._video_state:
                    content = self._video_state[video_name]["content"]
                else:
                    content, _ = self._generate_content_for_video(video_path, video_name)

                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # 记录本次生成的 md 文件名
                try:
                    self.doc_generated_md_names.add(md_path.name)
                except Exception:
                    pass

                success.append(f"{video_name} -> {stage}.md")
                self._post_ui(lambda s=stage: self._append_log_line(f"已生成: {s}.md"))

            except Exception as e:
                fail.append(f"{video_name} ({str(e)})")

        self._post_ui(lambda: self._on_doc_generation_done(success, fail))

    def _on_doc_generation_done(self, success: List[str], fail: List[str]) -> None:
        self._on_batch_done(
            self.doc_run_btn,
            "生成文档",
            "文档生成",
            success,
            fail,
            msg_format="成功生成 {ok} 个文档，失败 {bad} 个",
            log_fail=True,
        )

    # ------------------------- 文档与视频转运 -------------------------

    def run_doc_transfer(self) -> None:
        """将 DOC_OUTPUT_DIR 中的文档及其引用的视频剪切到 config 指定目录。"""
        if self._batch_in_progress or self._repair_in_progress:
            self.status_label.config(text="已有任务在处理中，请等待完成", foreground="red")
            return
        md_files = list(Path(DOC_OUTPUT_DIR).glob("*.md"))
        # 只允许转运"本次文档生成"产生的文档，避免误操作历史文件
        generated_names = getattr(self, "doc_generated_md_names", set())
        if not generated_names:
            self.status_label.config(
                text="本轮没有生成过文档，无法转运", foreground="red"
            )
            return
        md_files = [p for p in md_files if p.name in generated_names]
        # 若记录的文档与实际文件不一致，则报错并终止本次转运
        missing_docs = [
            name for name in generated_names if not (DOC_OUTPUT_DIR / name).is_file()
        ]
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

        self._batch_in_progress = True
        # 转运期间禁用右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(False)
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
                self._post_ui(
                    lambda n=md_path.name, err=e: self._append_log_line(f"{n}  (读取失败: {err})")
                )
                continue

            # 提取所有 ![[...]] 引用，允许多个
            refs = list({m.group(1).strip() for m in re.finditer(r"!\[\[(.+?)\]\]", text)})

            doc_target = DOC_TRANSFER_DOC_DIR / md_path.name

            # 若目标文档目录已存在同名 md，则整组跳过
            if doc_target.exists():
                skipped += 1
                self._post_ui(
                    lambda n=md_path.name: self._append_log_line(
                        f"{n}  (目标文档目录已存在同名文件，已跳过文档及其视频)"
                    )
                )
                continue

            # 没有任何视频引用：仅转运 md
            if not refs:
                try:
                    shutil.move(str(md_path), str(doc_target))
                    moved_docs += 1
                    self._post_ui(lambda n=md_path.name: self._append_log_line(f"已转运文档: {n}"))
                except Exception as e:
                    skipped += 1
                    self._post_ui(
                        lambda n=md_path.name, err=e: self._append_log_line(f"{n}  (转运文档失败: {err})")
                    )
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
                    self._post_ui(
                        lambda n=md_path.name, refs=list(missing_refs): self._append_log_line(
                            f"{n}  (引用视频缺失: {', '.join(refs)})"
                        )
                    )
                if conflict_refs:
                    self._post_ui(
                        lambda n=md_path.name, refs=list(conflict_refs): self._append_log_line(
                            f"{n}  (目标视频目录已存在同名文件: {', '.join(refs)})"
                        )
                    )
                continue

            # 可以安全转运：将同组的文档和所有引用视频作为一个事务处理
            moves_done: List[tuple[Path, Path]] = []
            group_failed = False

            # 先移动 md
            try:
                shutil.move(str(md_path), str(doc_target))
                moves_done.append((doc_target, md_path))
                self._post_ui(lambda n=md_path.name: self._append_log_line(f"已转运文档: {n}"))
            except Exception as e:
                skipped += 1
                self._post_ui(
                    lambda n=md_path.name, err=e: self._append_log_line(f"{n}  (转运文档失败: {err})")
                )
                group_failed = True

            # 再移动所有引用的视频
            if not group_failed:
                for ref, src in ref_src_list:
                    target = DOC_TRANSFER_MEDIA_DIR / ref
                    try:
                        shutil.move(str(src), str(target))
                        moves_done.append((target, src))
                        self._post_ui(lambda r=ref: self._append_log_line(f"已转运视频: {r}"))
                    except Exception as e:
                        self._post_ui(
                            lambda r=ref, err=e: self._append_log_line(f"{r}  (转运视频失败: {err})")
                        )
                        group_failed = True
                        break

            # 如有任何一步失败，回滚本组已移动的所有文件
            if group_failed:
                for current, original in reversed(moves_done):
                    try:
                        if current.exists():
                            shutil.move(str(current), str(original))
                    except Exception as e:
                        self._post_ui(
                            lambda n=current.name, err=e: self._append_log_line(
                                f"{n}  (回滚失败，请手动检查位置: {err})"
                            )
                        )
                skipped += 1
            else:
                moved_docs += 1
                moved_videos += len(ref_src_list)

        self._post_ui(
            lambda: self._on_doc_transfer_done(moved_docs, moved_videos, skipped)
        )

    def _on_doc_transfer_done(
        self, moved_docs: int, moved_videos: int, skipped: int
    ) -> None:
        self._batch_in_progress = False
        self.status_label.config(text="待机中", foreground="blue")
        # 转运结束后恢复右箭头
        if hasattr(self, "_set_jump_enabled"):
            self._set_jump_enabled(True)

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
