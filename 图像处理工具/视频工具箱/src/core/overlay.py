"""主窗口上半区（页签内容区）内嵌覆盖层通用布局。"""

import tkinter as tk
from tkinter import ttk


class OverlayMixin:
    """在 upper_shell 内 place 覆盖层，不遮挡页签与底部日志。"""

    def _notebook_tab_bar_height(self) -> int:
        try:
            self.notebook.update_idletasks()
            tab_id = self.notebook.select()
            tab_widget = self.notebook.nametowidget(tab_id)
            return max(self.notebook.winfo_height() - tab_widget.winfo_height(), 26)
        except Exception:
            return 28

    def _create_upper_overlay_frame(self, attr_name: str) -> tk.Frame:
        """创建或返回指定名称的覆盖层根 Frame。"""
        overlay = getattr(self, attr_name, None)
        if overlay is not None:
            return overlay

        style = ttk.Style()
        bg = style.lookup("TFrame", "background") or "#f0f0f0"
        overlay = tk.Frame(
            self.upper_shell,
            bg=bg,
            highlightbackground="#a0a0a0",
            highlightthickness=1,
        )
        setattr(self, attr_name, overlay)

        if not getattr(self, "_upper_shell_overlay_bound", False):
            self.upper_shell.bind("<Configure>", self._on_upper_shell_configure)
            self._upper_shell_overlay_bound = True

        return overlay

    def _overlay_geometry(self) -> tuple:
        """计算覆盖层位置与尺寸（位于页签栏下方）。"""
        self.upper_shell.update_idletasks()
        tab_h = self._notebook_tab_bar_height()
        w = max(self.upper_shell.winfo_width(), 200)
        h = max(self.upper_shell.winfo_height(), 200)
        return (0, tab_h, w, max(h - tab_h, 150))

    def _layout_upper_overlay(self, overlay: tk.Frame) -> None:
        if not overlay.winfo_ismapped():
            return
        x, y, w, h = self._overlay_geometry()
        overlay.place(x=x, y=y, width=w, height=h)
        overlay.lift()

    def _on_upper_shell_configure(self, _event=None) -> None:
        for name in ("repair_overlay", "roi_overlay"):
            overlay = getattr(self, name, None)
            if overlay is not None:
                self._layout_upper_overlay(overlay)

    def _show_upper_overlay(self, overlay: tk.Frame) -> None:
        # 如果 overlay 还没被 place，先进行初始布局
        if not overlay.winfo_ismapped():
            x, y, w, h = self._overlay_geometry()
            overlay.place(x=x, y=y, width=w, height=h)
        self._layout_upper_overlay(overlay)
        overlay.lift()

    def _hide_upper_overlay(self, overlay: tk.Frame) -> None:
        overlay.place_forget()
