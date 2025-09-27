import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import tkinterdnd2 as tkdnd
import threading
import cv2
from PIL import Image, ImageTk

# ---------- 系统通知 ----------
try:
    from plyer import notification
    NOTIFY = True
except Exception:
    NOTIFY = False

# ---------- ROI 选择窗口 ----------
class ROISelector(tk.Toplevel):
    def __init__(self, parent, image_bgr, orig_w, orig_h):
        super().__init__(parent)
        self.title('拖动鼠标选择保留区域,回车确认')
        self.geometry('+100+100')
        self.parent = parent
        self.orig_w, self.orig_h = orig_w, orig_h

        # 统一缩放到预览尺寸
        self.image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        self.resized_w = 960
        self.resized_h = int(orig_h * 960 / orig_w)
        self.scale = orig_w / self.resized_w
        self.image_pil = Image.fromarray(self.image_rgb).resize(
            (self.resized_w, self.resized_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(self.image_pil)

        # Canvas
        self.canvas = tk.Canvas(self, width=self.resized_w, height=self.resized_h,
                                bg='black', cursor='crosshair')
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        self.rect_id = None
        self.start_xy = None
        self.roi = None   # 返回原图坐标 (x,y,w,h)

        self.canvas.bind('<Button-1>', self.on_down)
        self.canvas.bind('<B1-Motion>', self.on_move)
        self.canvas.bind('<Double-Button-1>', self.on_ok)
        self.bind('<Return>', self.on_ok)
        self.protocol('WM_DELETE_WINDOW', self.on_cancel)

    def on_down(self, e):
        self.start_xy = (e.x, e.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def on_move(self, e):
        if not self.start_xy:
            return
        x0, y0 = self.start_xy
        self.rect_id = self.canvas.create_rectangle(
            x0, y0, e.x, e.y, outline='red', width=2)

    def on_ok(self, _evt=None):
        if not self.rect_id:
            self.parent.status_label.config(text="请先框选区域！", foreground="red")
            return
        coords = self.canvas.coords(self.rect_id)   # [x1,y1,x2,y2]
        if not coords or len(coords) != 4:
            return
        # 换算到原始分辨率
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

    def on_cancel(self):
        self.roi = None
        self.destroy()

# ---------- 主程序 ----------
class VideoTools(tkdnd.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频工具箱")
        self.geometry("400x480+2532+880")
        
        # 视频段落截取相关变量
        self.video_path = ""
        self.output_dir = ""
        
        # 视频画幅裁剪相关变量
        self.video_list = []
        self.roi = None
        
        self.create_widgets()
        self.drop_target_register(tkdnd.DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_files)

    def create_widgets(self):
        # 创建选项卡
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(10, 0))
        
        # 视频段落截取选项卡
        self.segment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.segment_frame, text="多段截取")
        self.create_segment_widgets()
        
        # 视频画幅裁剪选项卡
        self.crop_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.crop_frame, text="画幅裁剪")
        self.create_crop_widgets()
        
        # 统一的状态和日志区域
        self.create_common_widgets()

    # ---------- 视频段落截取界面 ----------
    def create_segment_widgets(self):
        self.segment_video_label = ttk.Label(self.segment_frame, text="请拖入一个视频文件", foreground="grey")
        self.segment_video_label.pack(pady=6)

        # 多段输入
        ttk.Label(self.segment_frame, text="批量截取:").pack(anchor="w", padx=10)
        self.segment_text = scrolledtext.ScrolledText(self.segment_frame, width=60, height=10, font=("Consolas", 9))
        self.segment_text.pack(padx=10, pady=4)
        self.segment_text.insert("end", "00:00:01 01:00:02 test1\nclipA 00:00:03 00:00:08\n00:00:11 my clip 00:00:20\n")

        btn_frame = ttk.Frame(self.segment_frame)
        btn_frame.pack(fill='x', padx=10, pady=6)
        self.segment_run_btn = ttk.Button(btn_frame, text="开始截取", command=self.run_segment_batch)
        self.segment_run_btn.pack(side='right', padx=4)

    # ---------- 视频画幅裁剪界面 ----------
    def create_crop_widgets(self):
        self.crop_video_label = ttk.Label(self.crop_frame, text="请拖入一个或多个视频文件", foreground="grey")
        self.crop_video_label.pack(pady=6)

        # 视频文件列表
        ttk.Label(self.crop_frame, text="视频文件列表:").pack(anchor="w", padx=10)
        self.crop_text = scrolledtext.ScrolledText(self.crop_frame, width=60, height=10, font=("Consolas", 9))
        self.crop_text.pack(padx=10, pady=4)
        self.crop_text.config(state="disabled")

        btn_frame = ttk.Frame(self.crop_frame)
        btn_frame.pack(fill='x', padx=10, pady=6)
        ttk.Button(btn_frame, text='选定画幅', command=self.select_roi).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='清空列表', command=self.clear_crop_list).pack(side='left', padx=4)
        self.crop_run_btn = ttk.Button(btn_frame, text='开始裁剪', command=self.run_crop_batch)
        self.crop_run_btn.pack(side='right', padx=4)

    # ---------- 统一的状态和日志区域 ----------
    def create_common_widgets(self):
        # 分隔线
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill='x', padx=10, pady=(5, 0))
        
        # 状态区域
        status_frame = ttk.Frame(self)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="待机中", foreground="blue")
        self.status_label.pack(side='left')
        
        # 日志区域
        ttk.Label(self, text="FFmpeg 实时日志:").pack(anchor='w', padx=10, pady=(5, 0))
        self.log = scrolledtext.ScrolledText(self, width=80, height=6, state='disabled', font=('Consolas', 8))
        self.log.pack(padx=10, pady=(0, 10), fill='both', expand=True)

    # ---------- 拖拽处理 ----------
    def drop_files(self, event):
        files = self.tk.splitlist(event.data)
        if not files: return
        
        # 根据当前选中的选项卡决定处理方式
        current_tab = self.notebook.index(self.notebook.select())
        
        if current_tab == 0:  # 视频段落截取
            self.drop_segment_video(files[0])
        elif current_tab == 1:  # 视频画幅裁剪
            self.drop_crop_videos(files)

    def drop_segment_video(self, path):
        if not os.path.isfile(path): return
        ext = os.path.splitext(path)[-1].lower()
        if ext not in ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.ts'):
            return
        self.video_path = path
        self.output_dir = os.path.join(os.path.dirname(path), "剪辑")
        os.makedirs(self.output_dir, exist_ok=True)
        self.segment_video_label.config(text=f"已载入:  {os.path.basename(path)}", foreground="black")

    def drop_crop_videos(self, files):
        added_files = []
        for f in files:
            if not os.path.isfile(f):
                continue
            ext = os.path.splitext(f)[-1].lower()
            if ext not in ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.ts'):
                continue
            item = (f, os.path.basename(f))
            if item not in self.video_list:
                self.video_list.append(item)
                added_files.append(item[1])
        
        if added_files:
            self.crop_text.config(state="normal")
            for filename in added_files:
                self.crop_text.insert("end", filename + "\n")
            self.crop_text.config(state="disabled")
            self.crop_video_label.config(text=f"已载入 {len(self.video_list)} 个视频文件", foreground="black")

    # ---------- 视频段落截取功能 ----------
    def run_segment_batch(self):
        if not self.video_path:
            self.status_label.config(text="请先拖入视频文件", foreground="red")
            return
        lines = self.segment_text.get("1.0", "end").strip().splitlines()
        tasks = []
        errors = []
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            ok, result = self._parse_line_auto(line)
            if not ok:
                errors.append(f"第{idx}行: {result}")
                continue
            start, end, name = result
            tasks.append((start, end, name))
        if errors:
            self.log.config(state="normal")
            self.log.delete("1.0", "end")
            for msg in errors:
                self.log.insert("end", msg + "\n")
            self.log.config(state="disabled")
            self.status_label.config(text="发现输入错误，请修正后重试", foreground="red")
            return
        if not tasks: return
        self.segment_run_btn.config(state="disabled", text="处理中")
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        threading.Thread(target=self._segment_batch_thread, args=(tasks,), daemon=True).start()

    def _segment_batch_thread(self, tasks):
        success, fail = [], []
        for idx, (start, end, name) in enumerate(tasks, 1):
            base, ext = os.path.splitext(name)
            counter = 1
            while True:
                out_name = f"{base}{'' if counter == 1 else f'({counter})'}{ext}"
                out_path = os.path.join(self.output_dir, out_name)
                if not os.path.exists(out_path): break
                counter += 1

            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-stats",
                   "-i", self.video_path, "-ss", start, "-to", end,
                   "-c", "copy", "-y", out_path]

            self.status_label.config(text=f"正在处理：{out_name}")
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        bufsize=0, universal_newlines=True,
                                        encoding='utf-8', errors='replace')
                for line in iter(proc.stdout.readline, ''):
                    self._log(line.rstrip('\n'))
                proc.wait()
                if proc.returncode == 0:
                    success.append(out_name)
                else:
                    fail.append(f"{out_name}  (返回码 {proc.returncode})")
            except Exception as e:
                fail.append(f"{out_name}  ({e})")

        self.after(0, self._segment_batch_done, success, fail)

    def _log(self, msg):
        if '\r' in msg:
            self.log.config(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("end", msg.split('\r')[-1])
            self.log.config(state="disabled")
        else:
            self.log.config(state="normal")
            self.log.insert("end", msg + '\n')
            self.log.config(state="disabled")
        self.log.see("end")

    def _segment_batch_done(self, success, fail):
        self.segment_run_btn.config(state="normal", text="开始截取")
        self.status_label.config(text="待机中", foreground="blue")
        msg = f"成功 {len(success)} 段，失败 {len(fail)} 段"
        if NOTIFY:
            notification.notify(
                title="视频批量截取",
                message=msg,
                timeout=4,
                app_name="VideoTools"
            )
        else:
            self.status_label.config(text=msg)

    def _parse_line_auto(self, line):
        # 匹配时间：H:MM:SS 或 HH:MM:SS，可带小数秒，如 00:01:02.123
        time_pattern = r"\b\d{1,2}:\d{2}:\d{2}(?:\.\d{1,3})?\b"
        matches = list(re.finditer(time_pattern, line))
        if len(matches) == 0:
            return False, "未检测到时间（格式示例：00:01:02 或 00:01:02.123）"
        if len(matches) == 1:
            return False, "仅检测到一个时间，需提供开始与结束两个时间"
        if len(matches) > 2:
            return False, "检测到超过两个时间，其中一个疑似作为文件名，文件名不能是时间格式"

        # 提取两个时间字符串
        t1 = matches[0].group(0)
        t2 = matches[1].group(0)

        # 解析为秒判断先后
        s1 = self._time_to_seconds(t1)
        s2 = self._time_to_seconds(t2)
        if s1 is None or s2 is None:
            return False, "时间格式不合法（应为 H:MM:SS[.ms]）"
        if s1 == s2:
            return False, "开始与结束时间不能相同"
        start, end = (t1, t2) if s1 < s2 else (t2, t1)

        # 去除行中的两个时间，剩余即为文件名（可在两端或中间，允许包含空格）
        spans = sorted([m.span() for m in matches], key=lambda x: x[0])
        a0, a1 = spans[0]
        b0, b1 = spans[1]
        name = (line[:a0] + line[a1:b0] + line[b1:]).strip()
        if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
            name = name[1:-1].strip()
        if not name:
            return False, "缺少文件名"

        if re.fullmatch(time_pattern, name):
            return False, "文件名不能是时间格式"

        lower = name.lower()
        if not lower.endswith((".mp4", ".mkv", ".mov", ".avi")):
            name += ".mp4"

        return True, (start, end, name)

    def _time_to_seconds(self, t):
        try:
            if "." in t:
                hhmmss, ms = t.split(".", 1)
                ms_val = float("0." + ms)
            else:
                hhmmss, ms_val = t, 0.0
            parts = hhmmss.split(":")
            if len(parts) != 3:
                return None
            h, m, s = [int(parts[0]), int(parts[1]), int(parts[2])]
            if not (0 <= m < 60 and 0 <= s < 60):
                return None
            return h * 3600 + m * 60 + s + ms_val
        except Exception:
            return None

    # ---------- 视频画幅裁剪功能 ----------
    def clear_crop_list(self):
        self.video_list.clear()
        self.crop_text.config(state="normal")
        self.crop_text.delete("1.0", "end")
        self.crop_text.config(state="disabled")
        self.crop_video_label.config(text="请拖入一个或多个视频文件", foreground="grey")

    def select_roi(self):
        if not self.video_list:
            self.status_label.config(text="请先拖入视频文件", foreground="red")
            return
        first_video = self.video_list[0][0]
        cap = cv2.VideoCapture(first_video)
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            self.status_label.config(text="无法读取视频第一帧", foreground="red")
            return
        selector = ROISelector(self, frame, orig_w, orig_h)
        self.wait_window(selector)
        if selector.roi is None:
            return
        self.roi = selector.roi
        self.status_label.config(text=f"已选择区域: x={self.roi[0]}, y={self.roi[1]}, w={self.roi[2]}, h={self.roi[3]}", foreground="blue")

    def run_crop_batch(self):
        if not self.video_list:
            self.status_label.config(text="视频列表为空！", foreground="red")
            return
        if self.roi is None:
            self.status_label.config(text="请先点击'裁剪画幅'选择保留区域！", foreground="red")
            return
        self.crop_run_btn.config(state='disabled', text='处理中')
        self.clear_log()
        threading.Thread(target=self._crop_batch_thread, daemon=True).start()

    def _crop_batch_thread(self):
        success, fail = [], []
        x, y, w, h = self.roi
        for vpath, vname in self.video_list:
            out_dir = os.path.join(os.path.dirname(vpath), '裁剪输出')
            os.makedirs(out_dir, exist_ok=True)
            base, ext = os.path.splitext(vname)
            out_path = os.path.join(out_dir, f'{base}{ext}')

            # 获取原分辨率
            probe = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height', '-of', 'csv=p=0', vpath],
                capture_output=True, text=True)
            try:
                orig_w, orig_h = map(int, probe.stdout.strip().split(','))
            except Exception:
                fail.append(f'{vname}  (无法获取分辨率)')
                continue

            # 滤镜：先裁剪 → 再 pad 回原尺寸居中
            filter_complex = f'crop={w}:{h}:{x}:{y},pad={orig_w}:{orig_h}:' \
                             f'({orig_w}-{w})/2:({orig_h}-{h})/2:black'

            cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'info', '-stats',
                   '-i', vpath, '-vf', filter_complex,
                   '-c:a', 'copy', '-y', out_path]

            self.status_label.config(text=f'正在处理：{vname}',foreground="blue")
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=0, universal_newlines=True,
                    encoding='utf-8', errors='replace')
                for line in iter(proc.stdout.readline, ''):
                    self._log(line.rstrip())
                rc = proc.wait()
                if rc == 0:
                    success.append(vname)
                else:
                    fail.append(f'{vname}  (返回码 {rc})')
            except Exception as e:
                fail.append(f'{vname}  ({e})')

        self.after(0, self._crop_batch_done, success, fail)

    def clear_log(self):
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.config(state='disabled')

    def _crop_batch_done(self, success, fail):
        self.crop_run_btn.config(state='normal', text='开始裁剪')
        self.status_label.config(text='待机中', foreground="blue")
        msg = f'成功 {len(success)} 个，失败 {len(fail)} 个'
        if NOTIFY:
            notification.notify(title='视频批量裁剪', message=msg, timeout=4, app_name='VideoTools')
        else:
            self.status_label.config(text=msg)
        if fail:
            self._log('失败列表：')
            for f in fail:
                self._log('  ' + f)

if __name__ == "__main__":
    VideoTools().mainloop()


