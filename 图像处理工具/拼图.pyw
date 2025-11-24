import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import tkinterdnd2 as tkdnd

class ImageConcatenator(tkdnd.Tk):
    def __init__(self):
        super().__init__()
        self.title("图片拼接工具")
        self.geometry("300x360+2632+1050")   # 窗口大小、位置
        self.image_paths = []
        self.output_path = ""
        self.create_widgets()

    # ---------- 仅保留这一个 create_widgets ----------
    def create_widgets(self):
        ### 新增：置顶按钮 ###
        self.topmost_var = tk.BooleanVar(value=False)
        self.topmost_cb = tk.Checkbutton(
            self, text="置顶", variable=self.topmost_var,
            command=lambda: self.attributes("-topmost", self.topmost_var.get())
        )
        self.topmost_cb.place(relx=1.0, x=-50, y=5, anchor="ne")
        ### 新增结束 ###

        # 选择图片按钮
        self.select_button = tk.Button(self, text="选择图片", command=self.select_images)
        self.select_button.pack(pady=10)

        # 已选图片列表
        self.image_listbox = tk.Listbox(self, width=50, height=7)
        self.image_listbox.pack(pady=10)

        # 清空列表按钮
        self.clear_button = tk.Button(self, text="清空列表", command=self.clear_images)
        self.clear_button.pack(pady=5)

        # 输出文件名
        self.output_label = tk.Label(self, text="输出文件名:")
        self.output_label.pack()
        self.output_entry = tk.Entry(self, width=50)
        self.output_entry.insert(0, "拼图")
        self.output_entry.pack()

        # 拼接按钮
        self.concat_button = tk.Button(self, text="拼接图片", command=self.concatenate_images)
        self.concat_button.pack(pady=10)

        # 拖拽支持
        self.drop_target_register(tkdnd.DND_FILES)
        self.dnd_bind('<<Drop>>', self.files_dropped)
    # ---------- create_widgets 结束 ----------

    # 以下为原有功能函数，无改动
    def select_images(self):
        new_paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        for path in new_paths:
            self.image_paths.append(path)
            self.image_listbox.insert(tk.END, os.path.basename(path))

    def clear_images(self):
        self.image_paths = []
        self.image_listbox.delete(0, tk.END)

    def files_dropped(self, event):
        new_paths = self.tk.splitlist(event.data)
        for path in new_paths:
            self.image_paths.append(path)
            self.image_listbox.insert(tk.END, os.path.basename(path))

    def concatenate_images(self):
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片！")
            return

        output_name = self.output_entry.get().strip()
        if not output_name:
            messagebox.showwarning("警告", "请输入输出文件名！")
            return

        if not output_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            output_name += '.png'

        output_dir = os.path.join(os.path.dirname(self.image_paths[0]), "拼接图")
        os.makedirs(output_dir, exist_ok=True)

        base_name, ext = os.path.splitext(output_name)
        counter = 1
        while True:
            candidate = f"{base_name}{'' if counter == 1 else f'({counter})'}{ext}"
            output_path = os.path.join(output_dir, candidate)
            if not os.path.exists(output_path):
                break
            counter += 1

        try:
            images = [Image.open(p) for p in self.image_paths]
            widths, heights = zip(*(i.size for i in images))
            max_width = max(widths)

            resized = []
            for img in images:
                if img.width < max_width:
                    new_h = int(img.height * (max_width / img.width))
                    img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
                resized.append(img)

            total_h = sum(img.height for img in resized)
            new_img = Image.new('RGB', (max_width, total_h))
            y = 0
            for img in resized:
                new_img.paste(img, (0, y))
                y += img.height
            new_img.save(output_path)
            messagebox.showinfo("成功", f"图片已成功拼接并保存为\n{output_path}")
        except Exception as e:
            messagebox.showerror("错误", f"发生错误: {e}")

if __name__ == "__main__":
    app = ImageConcatenator()
    app.mainloop()
