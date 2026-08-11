"""终端交互辅助：颜色、提示、菜单（Windows/Linux 通用）。

输出走可注入的 sink：Textual 界面 set_sink(...) 后，引擎/CLI 的
console.* 输出全部改道进界面日志；未注入时保持原有终端打印。
"""

import sys
from typing import Callable

try:
    _USE_COLOR = sys.stdout.isatty()
except Exception:
    _USE_COLOR = False


def enable_vt_windows() -> None:
    """Windows 10+ 终端开启 ANSI 颜色支持。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


class _Color:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


Sink = Callable[[str, str], None]  # (level, text)
_sink: Sink | None = None
_COLOR_BY_LEVEL = {
    "banner": _Color.PURPLE,
    "info": _Color.BLUE,
    "ok": _Color.GREEN,
    "warn": _Color.YELLOW,
    "error": _Color.RED,
    "dim": _Color.GRAY,
}


def set_sink(sink: Sink | None) -> None:
    """注入/移除输出汇；sink 签名 (level, text)。"""
    global _sink
    _sink = sink


def _emit(level: str, text: str) -> None:
    if _sink is not None:
        _sink(level, text)
        return
    print(paint(text, _COLOR_BY_LEVEL.get(level, _Color.RESET)))


def paint(text: str, color: str) -> str:
    return f"{color}{text}{_Color.RESET}" if _USE_COLOR else text


def banner(text: str) -> None:
    _emit("banner", f"== {text} ==")


def info(text: str) -> None:
    _emit("info", text)


def ok(text: str) -> None:
    _emit("ok", text)


def warn(text: str) -> None:
    _emit("warn", text)


def error(text: str) -> None:
    _emit("error", text)


def dim(text: str) -> None:
    _emit("dim", text)


def prompt(text: str) -> str:
    return input(paint(text, _Color.CYAN))


def menu(title: str, options: list[tuple[str, str]]) -> str | None:
    """options 为 [(keyword, 说明), ...]；输入编号/关键词，q/0/空 返回 None。"""
    banner(title)
    for index, (_, label) in enumerate(options, 1):
        print(f"  {index}. {label}")
    while True:
        raw = prompt("请选择 (编号/关键词，q 返回): ").strip().lower()
        if raw in ("q", "quit", "0", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for keyword, _ in options:
            if raw == keyword:
                return keyword
        warn("无效选择，请重试")
