"""终端交互辅助：颜色、提示、菜单（Windows/Linux 通用）。"""

import sys

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


def paint(text: str, color: str) -> str:
    return f"{color}{text}{_Color.RESET}" if _USE_COLOR else text


def banner(text: str) -> None:
    print(paint(f"== {text} ==", _Color.PURPLE))


def info(text: str) -> None:
    print(paint(text, _Color.BLUE))


def ok(text: str) -> None:
    print(paint(text, _Color.GREEN))


def warn(text: str) -> None:
    print(paint(text, _Color.YELLOW))


def error(text: str) -> None:
    print(paint(text, _Color.RED))


def dim(text: str) -> None:
    print(paint(text, _Color.GRAY))


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
