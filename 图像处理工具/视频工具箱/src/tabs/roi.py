"""画幅裁剪：在主窗口上半区内嵌 ROI 框选。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

import cv2
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import ttk

from ..core.config import UI_FONT_FAMILY

if TYPE_CHECKING:
    from ..core.app import VideoTools


RoiTuple = Tuple[int, int, int, int]


class ROISelector:
    """在 upper_shell 覆盖层内拖动框选保留区域，返回原图坐标 (x, y, w, h)。"""

    def __init__(self, app: VideoTools, image_bgr, orig_w: int, orig_h: int) -> None:
        self.app = app
        self.orig_w = orig_w
        self.orig_h = orig_h
        self.image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        self.roi: Optional[RoiTuple] = None
        self.overlay: tk.Frame | None = None
        self.canvas: tk.Canvas | None = None
        self.canvas_host: ttk.Frame | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.rect_id: str | None = None
        self.start_xy: tuple[int, int] | None = None
        self.resized_w = 960
        self.resized_h = 540
        self.scale = 1.0
        self._done_var: tk.IntVar | None = None
        self._return_bind: str | None = None

    def run(self) -> Optional[RoiTuple]:
        """模态显示覆盖层，完成后返回 ROI 或 None。"""
        self.app._active_roi_selector = self
        try:
            self.overlay = self.app._create_upper_overlay_frame("roi_overlay")
            self._build_shell()
            self.app._show_upper_overlay(self.overlay)
            self.app.update_idletasks()
            self._layout_preview()

            self._done_var = tk.IntVar(self.app, 0)
            self._return_bind = self.app.bind(
                "<Return>", self._on_confirm_key, add="+"
            )
            self.app.wait_variable(self._done_var)

            if self._return_bind:
                self.app.unbind("<Return>", self._return_bind)
                self._return_bind = None

            self.app._hide_upper_overlay(self.overlay)
            return self.roi
        finally:
            self.app._active_roi_selector = None

    def _build_shell(self) -> None:
        assert self.overlay is not None
        for child in self.overlay.winfo_children():
            child.destroy()

        header = ttk.Frame(self.overlay)
        header.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(
            header,
            text="选定画幅",
            font=(UI_FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="拖动鼠标框选保留区域；双击画面或按回车确认，取消则放弃。",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.canvas_host = ttk.Frame(self.overlay)
        self.canvas_host.pack(fill="both", expand=True, padx=12, pady=6)
        self.canvas_host.bind("<Configure>", lambda _e: self._layout_preview())

        footer = ttk.Frame(self.overlay)
        footer.pack(fill="x", padx=12, pady=(0, 10))
        btn_row = ttk.Frame(footer)
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="确认", command=self._on_confirm).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(btn_row, text="取消", command=self._on_cancel).pack(side="right")

    def _layout_preview(self) -> None:
        if self.canvas_host is None:
            return
        self.canvas_host.update_idletasks()
        max_w = max(self.canvas_host.winfo_width(), 320)
        max_h = max(self.canvas_host.winfo_height(), 200)

        aspect = self.orig_w / self.orig_h
        if max_w / max_h > aspect:
            self.resized_h = max_h
            self.resized_w = max(1, int(max_h * aspect))
        else:
            self.resized_w = max_w
            self.resized_h = max(1, int(max_w / aspect))

        self.scale = self.orig_w / self.resized_w

        image_pil = Image.fromarray(self.image_rgb).resize(
            (self.resized_w, self.resized_h), Image.Resampling.LANCZOS
        )
        self.photo = ImageTk.PhotoImage(image_pil)

        if self.canvas is not None:
            self.canvas.destroy()

        self.canvas = tk.Canvas(
            self.canvas_host,
            width=self.resized_w,
            height=self.resized_h,
            bg="black",
            cursor="crosshair",
            highlightthickness=0,
        )
        self.canvas.pack(anchor="center")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        self.rect_id = None
        self.start_xy = None
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self._on_confirm)

    def _on_mouse_down(self, event) -> None:
        if not self.canvas:
            return
        self.start_xy = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def _on_mouse_move(self, event) -> None:
        if not self.canvas or not self.start_xy:
            return
        x0, y0 = self.start_xy
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x0, y0, event.x, event.y, outline="red", width=2
        )

    def _on_confirm_key(self, event=None) -> None:
        self._on_confirm(event)

    def _on_confirm(self, _event=None) -> None:
        if not self.canvas or not self.rect_id:
            self.roi = None
            self._finish()
            return

        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            self.roi = None
            self._finish()
            return

        x1, y1, x2, y2 = coords
        x = int(min(x1, x2) * self.scale)
        y = int(min(y1, y2) * self.scale)
        w = int(abs(x2 - x1) * self.scale)
        h = int(abs(y2 - y1) * self.scale)

        x = max(0, min(x, self.orig_w - 1))
        y = max(0, min(y, self.orig_h - 1))
        w = max(1, min(w, self.orig_w - x))
        h = max(1, min(h, self.orig_h - y))

        self.roi = (x, y, w, h)
        self._finish()

    def _on_cancel(self) -> None:
        self.roi = None
        self._finish()

    def _finish(self) -> None:
        if self._done_var is not None:
            self._done_var.set(1)


__all__ = ["ROISelector", "RoiTuple"]
