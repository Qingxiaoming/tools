import tkinter as tk

import cv2
from PIL import Image, ImageTk


class ROISelector(tk.Toplevel):
    """简单的 ROI 选择窗口，返回原始图像坐标 (x, y, w, h)。"""

    def __init__(self, parent: tk.Tk, image_bgr, orig_w: int, orig_h: int) -> None:
        super().__init__(parent)
        self.title("拖动鼠标选择保留区域, 回车确认")
        self.geometry("+100+100")
        self.parent = parent
        self.orig_w, self.orig_h = orig_w, orig_h

        # 统一缩放到预览尺寸，便于拖动选择
        self.image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        self.resized_w = 960
        self.resized_h = int(orig_h * 960 / orig_w)
        self.scale = orig_w / self.resized_w
        self.image_pil = Image.fromarray(self.image_rgb).resize(
            (self.resized_w, self.resized_h), Image.Resampling.LANCZOS
        )
        self.photo = ImageTk.PhotoImage(self.image_pil)

        # Canvas 显示画面
        self.canvas = tk.Canvas(
            self, width=self.resized_w, height=self.resized_h, bg="black", cursor="crosshair"
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        self.rect_id = None
        self.start_xy = None
        self.roi = None  # 返回原图坐标 (x, y, w, h)

        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_confirm)
        self.bind("<Return>", self.on_confirm)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    # -------------------- 事件处理 --------------------
    def on_mouse_down(self, event) -> None:
        """按下鼠标左键开始框选。"""
        self.start_xy = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def on_mouse_move(self, event) -> None:
        """拖动时更新矩形区域。"""
        if not self.start_xy:
            return
        x0, y0 = self.start_xy
        # 每次重画新的矩形
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x0, y0, event.x, event.y, outline="red", width=2
        )

    def on_confirm(self, _event=None) -> None:
        """确认选择，计算并保存 ROI。"""
        if not self.rect_id:
            # 主窗口如果需要，可在外部根据 roi 是否为 None 决定是否给出提示
            self.roi = None
            self.destroy()
            return

        coords = self.canvas.coords(self.rect_id)  # [x1, y1, x2, y2]
        if not coords or len(coords) != 4:
            self.roi = None
            self.destroy()
            return

        x1, y1, x2, y2 = coords
        x = int(min(x1, x2) * self.scale)
        y = int(min(y1, y2) * self.scale)
        w = int(abs(x2 - x1) * self.scale)
        h = int(abs(y2 - y1) * self.scale)

        # 边界保护
        x = max(0, min(x, self.orig_w - 1))
        y = max(0, min(y, self.orig_h - 1))
        w = max(1, min(w, self.orig_w - x))
        h = max(1, min(h, self.orig_h - y))

        self.roi = (x, y, w, h)
        self.destroy()

    def on_cancel(self) -> None:
        """取消选择。"""
        self.roi = None
        self.destroy()
