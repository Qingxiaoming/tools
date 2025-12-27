# obsidian_trans.py  —— 全局热键：Ctrl+Alt+1 置顶/取消置顶，0/2~9 透明度
# 依赖：pip install pywin32 pystray pillow
import ctypes
import ctypes.wintypes as wt
import threading
import time
import PIL.Image
import pystray

# ---------------- 常量 ----------------
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x2
WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE

# 十档透明度（0-9）
ALPHA_MAP = [255, 102, 117, 132, 147, 162, 178, 193, 208, 223, 238]

# ---------------- API ----------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def print_last_error(fn):
    errno = kernel32.GetLastError()
    if errno:
        print(f'[ERR] {fn}  GetLastError={errno}')

user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.COLORREF, ctypes.c_byte, wt.DWORD]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]

# ---------------- 逻辑 ----------------
hwnd_last = None
# 记录每个 hwnd 是否已置顶  {hwnd: bool}
topmost_state = {}

def set_trans(hwnd, alpha: int):
    """设置透明度（保持原样）"""
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not (ex & WS_EX_LAYERED):
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
        print(f'[LAY] Set WS_EX_LAYERED for hwnd={hwnd:x}')
    ret = user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
    if ret == 0:
        print_last_error('SetLayeredWindowAttributes')
    else:
        print(f'[SET] hwnd={hwnd:x}  alpha={alpha}')

def toggle_topmost(hwnd):
    """置顶/取消置顶切换"""
    if hwnd in topmost_state and topmost_state[hwnd]:
        # 当前已置顶，取消
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        topmost_state[hwnd] = False
        print(f'[TOP] hwnd={hwnd:x} 取消置顶')
    else:
        # 设为置顶
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        topmost_state[hwnd] = True
        print(f'[TOP] hwnd={hwnd:x} 置顶')

def update(level: int):
    """热键回调：0/2~9 透明度，1 置顶切换"""
    if not hwnd_last:
        print('[HOT] no active window')
        return
    if level == 1:
        toggle_topmost(hwnd_last)
    else:
        alpha = ALPHA_MAP[level]
        print(f'[HOT] level={level}  alpha={alpha}  hwnd={hwnd_last:x}')
        set_trans(hwnd_last, alpha)

# 后台不断记录“前台窗口”
def poll_active():
    global hwnd_last
    while True:
        hwnd = user32.GetForegroundWindow()
        if hwnd and hwnd != hwnd_last:
            hwnd_last = hwnd
            print(f'[CAP] new active hwnd={hwnd:x}')
        time.sleep(0.2)

# ---------------- 热键线程（NULL 窗口）----------------
def hotkey_thread():
    # 注册
    for i in range(10):
        ok = user32.RegisterHotKey(0, i, MOD_CONTROL | MOD_ALT, 0x30 + i)
        print(f'[REG] Ctrl+Alt+{i}  -> {ok}')
    ok = user32.RegisterHotKey(0, 99, MOD_CONTROL | MOD_ALT, 0x51)
    print(f'[REG] Ctrl+Alt+Q(quit) -> {ok}')

    # 64 位兼容 MSG
    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT),
                    ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                    ("time", wt.DWORD), ("pt", wt.POINT)]

    msg = MSG()
    while True:
        bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if bRet == 0:  # WM_QUIT
            print('[MSG] WM_QUIT, exit hotkey thread')
            break
        if bRet == -1:
            print_last_error('GetMessageW')
            break
        if msg.message == WM_HOTKEY:
            wp = msg.wParam
            print(f'[MSG] WM_HOTKEY wParam={wp}')
            if wp == 99:
                break
            if 0 <= wp <= 9:
                update(wp)
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    # 清理
    for i in range(10):
        user32.UnregisterHotKey(0, i)
    user32.UnregisterHotKey(0, 99)
    print('[END] hotkey thread exit')

# ---------------- 托盘 ----------------
def make_icon():
    img = PIL.Image.new('RGB', (32, 32), 'black')
    img.putpixel((15, 15), (255, 255, 255))
    return img

def quit_app(icon, item):
    print('[EXIT] tray exit')
    icon.stop()

def setup_tray():
    menu = pystray.Menu(pystray.MenuItem('Exit', quit_app))
    icon = pystray.Icon('ObsTrans', make_icon(), menu=menu,
                        title='ObsidianTrans – Ctrl+Alt+1 置顶')
    icon.run()

# ---------------- main ----------------
if __name__ == '__main__':
    print('[START] script started')
    threading.Thread(target=poll_active, daemon=True).start()
    threading.Thread(target=hotkey_thread, daemon=True).start()
    setup_tray()