"""Textual 界面（vim/yazi 风格键位交互）。

普通模式：i 输入链接 / a 设置菜单 / y 导出日志 / t 主题 / h 帮助 / q 退出；Enter 下载。
设置统一在 a 弹出的菜单里调整（j/k 移动、空格切换、回车编辑/确认）。
下载复用 cli.run_download，引擎输出经 console sink 实时进入 RichLog。

视觉：无 Header/Footer 大壳，分区用细线分隔，使用终端自身 ANSI 配色
（ansi-dark/ansi-light），跟随终端背景与窗口大小自动适配；按 t 切换深浅主题。
"""

import threading
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog, Static

from .cli import run_download
from .auth import import_cookie_from_browser, validate_cookie
from .config import load_cookie, load_save_dir, save_cookie, save_dir_to_config
from .console import set_sink
from .engines import resolve_engine
from .options import AUDIO_FORMATS, VIDEO_FORMATS, DownloadOptions, selection_within
from .sites import detect_site

_LEVEL_COLORS = {
    "banner": "purple",
    "info": "blue",
    "ok": "green",
    "warn": "yellow",
    "error": "red",
    "dim": "gray",
}
_THEMES = ("ansi-dark", "ansi-light")


class SettingsModal(ModalScreen[dict | None]):
    """通用设置弹窗：j/k 移动，空格切换/循环，回车确认（text 行进入输入），Esc 取消。"""

    def __init__(
        self,
        title: str,
        fields: list[dict],
        values: dict,
        max_index: int | None = None,
        no_url: bool = False,
        quality_choices: list[str] | None = None,
        cookie_menu: bool = True,
    ):
        super().__init__()
        self._title = title
        self._fields = fields
        self._values = dict(values)
        self._cursor = 0
        self._editing_key: str | None = None
        self._max_index = max_index
        self._no_url = no_url
        self._quality_list = quality_choices
        self._cookie_menu = cookie_menu

    def _quality_choices(self) -> list[str]:
        if self._quality_list:
            return ["默认", *self._quality_list]
        return ["默认", "360P", "480P", "720P", "1080P", "4K"]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static(self._title, id="modal-title")
            yield Static("", id="opt-info")
            for field in self._fields:
                yield Static("", id=f"opt-{field['key']}")
            yield Input(
                placeholder="输入后回车确认，Esc 取消",
                id="modal-input",
                classes="hidden",
                disabled=True,
            )
            yield Static("j/k 移动   h/l 切换   i/回车 编辑   Esc 取消编辑   :wq 保存   :q! 放弃", id="modal-help")

    def on_mount(self) -> None:
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        self._update_info()
        for index, field in enumerate(self._fields):
            marker = "▸" if index == self._cursor else " "
            value = self._values.get(field["key"])
            if field["kind"] == "toggle":
                display = "开" if value else "关"
            elif field["kind"] == "choice":
                display = str(value)
            else:
                if field["key"] == "cookie":
                    display = f"已配置（{len(value)} 字符）" if value else "未配置"
                else:
                    display = str(value) if value else "(空)"
            self.query_one(f"#opt-{field['key']}", Static).update(f"{marker} {field['label']}: {display}")

    def _update_info(self) -> None:
        if self._no_url:
            self.query_one("#opt-info", Static).update("先按 i 输入链接，可查看分P列表")
        elif self._max_index is None:
            self.query_one("#opt-info", Static).update("可用分P/选集: 获取中…")
        else:
            self.query_one("#opt-info", Static).update(f"可用分P/选集: 共 {self._max_index} 个（1-{self._max_index}）")

    def update_items(self, items: list | None) -> None:
        """异步获取分P列表后的回调（UI 线程）。"""
        self._max_index = len(items) if items else None
        self._update_info()
        if items is None:
            self.query_one("#opt-info", Static).update("可用分P/选集: 获取失败（仅格式校验）")

    def update_qualities(self, qualities: list[str] | None) -> None:
        """异步获取清晰度列表后的回调（UI 线程）。"""
        self._quality_list = qualities or None
        if qualities and self._values.get("quality") not in ["默认", *qualities]:
            self._values["quality"] = "默认"
        self._refresh_rows()

    def update_meta(self, items: list | None, qualities: list[str] | None) -> None:
        """分P与清晰度列表合并回调（UI 线程，单次往返）。"""
        self.update_items(items)
        self.update_qualities(qualities)

    def _move(self, delta: int) -> None:
        self._cursor = (self._cursor + delta) % len(self._fields)
        self._refresh_rows()

    def _cycle_or_toggle(self, direction: int = 1) -> None:
        field = self._fields[self._cursor]
        if field["kind"] == "toggle":
            self._values[field["key"]] = direction > 0  # h=关, l=开
            if field["key"] == "audio":
                # 音频/视频语境切换，格式选项随之变化，重置为默认
                self._values["output_format"] = "默认"
        elif field["kind"] == "choice":
            if field["key"] == "output_format":
                choices = self._format_choices()
            elif field["key"] == "quality":
                choices = self._quality_choices()
            else:
                choices = field["choices"]
            current = self._values[field["key"]]
            index = choices.index(current) if current in choices else 0
            self._values[field["key"]] = choices[(index + direction) % len(choices)]
        self._refresh_rows()

    def _format_choices(self) -> list[str]:
        """输出格式选项随"仅下载音频"切换：音频格式 or 视频格式。"""
        if self._values.get("audio"):
            return ["默认", "mp3", "m4a", "flac", "wav"]
        return ["默认", "mp4", "mkv", "webm"]

    def _begin_edit(self) -> None:
        field = self._fields[self._cursor]
        if field["kind"] != "text":
            return
        self._editing_key = field["key"]
        widget = self.query_one("#modal-input", Input)
        widget.value = str(self._values.get(field["key"], ""))
        widget.disabled = False
        widget.remove_class("hidden")
        widget.focus()

    def _end_edit(self, commit: bool) -> None:
        widget = self.query_one("#modal-input", Input)
        if commit and self._editing_key:
            value = widget.value.strip()
            if (
                self._max_index
                and self._editing_key == "selection"
                and value
                and not selection_within(self._max_index, value)
            ):
                self.query_one("#opt-info", Static).update(
                    f"⚠️ 仅 1-{self._max_index} 可用（或 ALL / LAST）"
                )
                return  # 不提交，留在编辑状态
            self._values[self._editing_key] = value
        self._editing_key = None
        widget.add_class("hidden")
        widget.blur()
        widget.disabled = True
        self.focus()  # 焦点留在弹窗，防止按键漏到下层界面
        self._refresh_rows()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "modal-input":
            if self._editing_key == ":cmd":
                command = event.value.strip().lstrip(":")
                if command in ("q!", "quit!"):
                    self._editing_key = None
                    self._hide_input()
                    self.dismiss(None)
                elif command in ("wq", "x"):
                    self._editing_key = None
                    self._hide_input()
                    self.dismiss(self._values)
                else:
                    self._end_edit(commit=False)
            else:
                self._end_edit(commit=True)

    def _hide_input(self) -> None:
        widget = self.query_one("#modal-input", Input)
        widget.add_class("hidden")
        widget.blur()
        widget.disabled = True

    def on_key(self, event: events.Key) -> None:
        if self._editing_key:
            if event.key == "escape":
                event.stop()
                self._end_edit(commit=False)
            return
        if event.key in ("j", "down"):
            self._move(1)
        elif event.key in ("k", "up"):
            self._move(-1)
        elif event.key in ("h", "left"):
            self._cycle_or_toggle(-1)
        elif event.key in ("l", "right"):
            self._cycle_or_toggle(1)
        elif event.key == "space":
            field = self._fields[self._cursor]
            if field["kind"] == "toggle":
                self._values[field["key"]] = not self._values[field["key"]]
                if field["key"] == "audio":
                    self._values["output_format"] = "默认"
                self._refresh_rows()
            else:
                self._cycle_or_toggle(1)
        elif event.key in ("i", "enter"):
            field = self._fields[self._cursor]
            if field["kind"] == "text":
                if field["key"] == "cookie" and self._cookie_menu:
                    self.dismiss({"cookie_menu": True})
                else:
                    self._begin_edit()
        elif event.key in (":", "colon"):
            self._editing_key = ":cmd"
            widget = self.query_one("#modal-input", Input)
            widget.value = ":"
            widget.disabled = False
            widget.remove_class("hidden")
            widget.focus()
        else:
            return
        event.stop()


class CookieMenu(ModalScreen[str]):
    """B站 Cookie 二级菜单。"""

    def __init__(self):
        super().__init__()
        self._cursor = 0
        self._options = [
            ("paste", "手动粘贴 SESSDATA（推荐）"),
            ("import", "从浏览器自动导入"),
            ("clear", "清除已保存的 Cookie"),
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static("B站 Cookie", id="modal-title")
            for key, _label in self._options:
                yield Static("", id=f"opt-{key}")
            yield Static("j/k 移动   Enter 选择   Esc 返回", id="modal-help")

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        for index, (key, label) in enumerate(self._options):
            marker = "▸" if index == self._cursor else " "
            self.query_one(f"#opt-{key}", Static).update(f"{marker} {label}")

    def on_key(self, event: events.Key) -> None:
        if event.key in ("j", "down"):
            self._cursor = (self._cursor + 1) % len(self._options)
        elif event.key in ("k", "up"):
            self._cursor = (self._cursor - 1) % len(self._options)
        elif event.key in ("enter", "i"):
            self.dismiss(self._options[self._cursor][0])
        elif event.key == "escape":
            self.dismiss("cancel")
        else:
            return
        self._refresh()
        event.stop()


class DownloaderApp(App):
    TITLE = "视频下载工具"
    CSS = """
    #status {
        padding: 0 1;
        color: $text-muted;
    }
    #help {
        padding: 0 1;
        color: $text-muted;
        border-top: hkey gray;
    }
    Input {
        margin: 0 1;
        border: none;
    }
    .hidden {
        display: none;
    }
    RichLog {
        height: 1fr;
        border: none;
        border-top: hkey gray;
        padding: 0 1;
    }
    SettingsModal {
        align: center middle;
        background: $boost;
    }
    #modal-box {
        width: 60%;
        min-width: 44;
        height: auto;
        border: round $primary;
        background: $background;
        padding: 1 2;
    }
    #modal-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #modal-help {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, initial_url: str = ""):
        super().__init__()
        self._url = initial_url
        self._audio = False
        self._danmaku = False
        self._selection = ""
        self._quality = "默认"
        self._output_format = "默认"
        self._save_dir = str(load_save_dir())
        self._cookie = load_cookie()
        self._downloading = False
        self._settings_open = False

    # ---- 组装 ----

    def compose(self) -> ComposeResult:
        yield Static(id="status")
        yield Input(
            value=self._url,
            placeholder="粘贴视频链接，Enter 下载，Esc 返回",
            id="url",
            classes="hidden",
            disabled=True,
        )
        yield RichLog(id="log", highlight=True, wrap=True)
        yield Static(
            "i 输入链接   Enter 下载   a 设置   y 导出日志   t 主题   q 退出",
            id="help",
        )

    def on_mount(self) -> None:
        set_sink(self._emit)
        try:
            self.theme = "ansi-dark"
        except Exception:
            pass
        self.query_one("#url", Input).blur()
        self._refresh_status()
        self._write_log("info", "就绪：i 输入链接，a 打开设置菜单，q 退出")

    def on_unmount(self) -> None:
        set_sink(None)

    # ---- 状态与日志 ----

    def _input_mode(self) -> bool:
        widget = self.query_one("#url", Input)
        return not widget.has_class("hidden") and widget.has_focus

    def _refresh_status(self) -> None:
        mode = "输入" if self._input_mode() else "普通"
        link = self._url or "(空)"
        audio = "开" if self._audio else "关"
        danmaku = "开" if self._danmaku else "关"
        selection = self._selection or "-"
        login = "开" if self._cookie else "关"
        self.query_one("#status", Static).update(
            f"[bold]{mode}[/] | 链接: {link}\n"
            f"登录:{login} 音频:{audio} 弹幕:{danmaku} 选集:{selection} 画质:{self._quality} "
            f"格式:{self._output_format} | 目录:{self._save_dir}"
        )

    def _write_log(self, level: str, text: str) -> None:
        color = _LEVEL_COLORS.get(level, "white")
        self.query_one("#log", RichLog).write(Text(text, style=color))

    def _emit(self, level: str, text: str) -> None:
        if threading.current_thread() is threading.main_thread():
            self._write_log(level, text)
        else:
            try:
                self.call_from_thread(self._write_log, level, text)
            except Exception:
                pass

    def _log(self, level: str, text: str) -> None:
        self._emit(level, text)

    # ---- 链接输入 ----

    def _enter_input(self) -> None:
        widget = self.query_one("#url", Input)
        widget.disabled = False
        widget.remove_class("hidden")
        widget.focus()
        self._refresh_status()

    def _leave_input(self) -> None:
        widget = self.query_one("#url", Input)
        widget.add_class("hidden")
        widget.blur()
        widget.disabled = True
        self._refresh_status()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "url":
            self._url = event.value
            self._refresh_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url":
            self._leave_input()
            self._begin_download()

    # ---- 设置弹窗 ----

    def _settings_values(self) -> dict:
        return {
            "audio": self._audio,
            "danmaku": self._danmaku,
            "selection": self._selection,
            "quality": self._quality,
            "output_format": self._output_format,
            "save_dir": self._save_dir,
            "cookie": self._cookie,
        }

    def _settings_fields(self) -> list[dict]:
        return [
            {"key": "audio", "label": "仅下载音频", "kind": "toggle"},
            {"key": "output_format", "label": "输出格式", "kind": "choice", "choices": []},
            {"key": "danmaku", "label": "下载弹幕（XML/ASS）", "kind": "toggle"},
            {"key": "selection", "label": "选集范围", "kind": "text"},
            {"key": "quality", "label": "清晰度", "kind": "choice", "choices": ["默认", "360P", "480P", "720P", "1080P", "4K"]},
            {"key": "save_dir", "label": "保存目录", "kind": "text"},
            {"key": "cookie", "label": "B站 Cookie", "kind": "text"},
        ]

    def _open_settings(self) -> None:
        if self._settings_open:
            return
        self._settings_open = True
        modal = SettingsModal(
            "设置",
            self._settings_fields(),
            self._settings_values(),
            no_url=not bool(self._url.strip()),
        )
        self.push_screen(modal, self._settings_closed)
        if self._url.strip():
            self._fetch_items_worker(self._url.strip(), modal)

    def _settings_closed(self, result: dict | None) -> None:
        self._settings_open = False
        if result and result.get("cookie_menu"):
            self._open_cookie_menu()
            return
        self._apply_settings(result)

    # ---- B站 Cookie 二级菜单 ----

    def _open_cookie_menu(self) -> None:
        if self._settings_open:
            return
        self._settings_open = True
        self.push_screen(CookieMenu(), self._cookie_menu_closed)

    def _cookie_menu_closed(self, choice: str | None) -> None:
        self._settings_open = False
        if choice == "paste":
            self._open_paste_cookie()
        elif choice == "import":
            self._import_cookie_worker()
        elif choice == "clear":
            self._apply_saved_cookie("", "已清除 B 站 Cookie")

    def _open_paste_cookie(self) -> None:
        if self._settings_open:
            return
        self._settings_open = True
        fields = [{"key": "cookie", "label": "SESSDATA", "kind": "text"}]
        modal = SettingsModal(
            "粘贴 B站 Cookie",
            fields,
            {"cookie": self._cookie},
            no_url=True,
            cookie_menu=False,
        )
        self.push_screen(modal, self._paste_cookie_closed)

    def _paste_cookie_closed(self, result: dict | None) -> None:
        self._settings_open = False
        if result and "cookie" in result:
            self._save_cookie_worker(result["cookie"])

    @work(thread=True)
    def _import_cookie_worker(self) -> None:
        cookie, message = import_cookie_from_browser()
        if not cookie:
            self._log("error", f"自动导入失败：{message}")
            return
        valid, vmessage = validate_cookie(cookie)
        if not valid and "校验请求失败" not in vmessage:
            self._log("error", f"浏览器导入的 Cookie {vmessage}")
            return
        self.call_from_thread(self._apply_saved_cookie, cookie, f"{message}，{vmessage}")

    @work(thread=True)
    def _save_cookie_worker(self, value: str) -> None:
        from .config import normalize_cookie

        cookie = normalize_cookie(value)
        if not cookie:
            self.call_from_thread(self._apply_saved_cookie, "", "已清除 B 站 Cookie")
            return
        valid, vmessage = validate_cookie(cookie)
        if not valid and "校验请求失败" not in vmessage:
            self._log("error", f"Cookie {vmessage}，未保存")
            return
        self.call_from_thread(self._apply_saved_cookie, cookie, vmessage)

    def _apply_saved_cookie(self, cookie: str, message: str) -> None:
        try:
            save_cookie(cookie)
            self._cookie = load_cookie()
            self._refresh_status()
            self._log("ok", f"B站 Cookie 已保存（{message}）" if cookie else "B站 Cookie 已清除")
        except OSError as exc:
            self._log("error", f"Cookie 保存失败: {exc}")

    @work(thread=True)
    def _fetch_items_worker(self, url: str, modal: SettingsModal) -> None:
        """后台获取当前链接的分P/选集列表，回填弹窗。"""
        site = detect_site(url)
        engine = resolve_engine(site)
        items = engine.list_items(url) if engine else None
        qualities = engine.list_qualities(url) if engine else None
        self.call_from_thread(modal.update_meta, items, qualities)

    def _apply_settings(self, result: dict | None) -> None:
        if result is None:
            return
        self._audio = bool(result["audio"])
        self._danmaku = bool(result["danmaku"])
        self._selection = result["selection"]
        self._quality = result["quality"]
        self._output_format = result["output_format"]
        if result["save_dir"] != self._save_dir:
            self._save_dir = result["save_dir"]
            if self._save_dir:
                try:
                    save_dir_to_config(Path(self._save_dir).expanduser())
                    self._log("ok", f"保存目录已更新: {self._save_dir}")
                except OSError as exc:
                    self._log("warn", f"保存目录已采用，但写入配置失败: {exc}")
        self._refresh_status()

    # ---- 键位（普通模式）----

    def on_key(self, event: events.Key) -> None:
        if self._settings_open:
            # 弹窗打开期间，主界面不响应任何按键，防止按键泄漏
            return
        if self._input_mode():
            if event.key == "escape":
                event.stop()
                self._leave_input()
            return

        key = event.key
        if key == "i":
            self._enter_input()
        elif key == "enter":
            self._begin_download()
        elif key == "a":
            self._open_settings()
        elif key == "y":
            self._export_log()
        elif key == "t":
            self._toggle_theme()
        elif key == "h":
            self._log(
                "info",
                "i 输入链接，Enter 下载，a 设置（音频/弹幕/选集/画质/格式/目录），y 导出日志，t 主题，q 退出",
            )
        elif key == "q":
            self.exit()
        else:
            return
        self._refresh_status()
        event.stop()

    def _toggle_theme(self) -> None:
        self.theme = _THEMES[1] if self.theme == _THEMES[0] else _THEMES[0]
        self._log("info", f"主题已切换: {self.theme}")

    def _export_log(self) -> None:
        """把日志内容导出到文件（Textual 抓取鼠标，终端无法直接拖选复制）。"""
        log = self.query_one("#log", RichLog)
        lines = getattr(log, "lines", [])
        text = "\n".join(getattr(line, "plain", str(line)) for line in lines)
        dest = Path(self._save_dir) if self._save_dir else Path.home()
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError:
            dest = Path("/tmp")
        path = dest / f"下载日志_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            path.write_text(text, encoding="utf-8")
            self._log("ok", f"日志已导出: {path}")
        except OSError as exc:
            self._log("error", f"日志导出失败: {exc}")

    # ---- 下载流程 ----

    def _collect_options(self) -> DownloadOptions:
        fmt = self._output_format
        return DownloadOptions(
            audio=self._audio,
            danmaku=self._danmaku,
            selection=self._selection,
            audio_format=fmt if self._audio and fmt in AUDIO_FORMATS else "",
            quality="" if self._quality == "默认" else self._quality,
            output_format=fmt if not self._audio and fmt in VIDEO_FORMATS else "",
            save_dir=self._save_dir,
        )

    def _begin_download(self) -> None:
        if self._downloading:
            self._log("warn", "正在下载中，请等待完成")
            return
        url = self._url.strip().strip('"').strip("'")
        if not url:
            self._log("warn", "请先按 i 输入视频链接")
            self._enter_input()
            return

        self._downloading = True
        self._refresh_status()
        self._download_worker(url, self._collect_options())

    @work(exclusive=True, thread=True)
    def _download_worker(self, url: str, options: DownloadOptions) -> None:
        try:
            ok = run_download(url, options)
        except Exception as exc:  # 防止线程异常导致界面卡死
            self._log("error", f"意外错误: {exc}")
            ok = False
        self.call_from_thread(self._finish_download, ok)

    def _finish_download(self, ok: bool) -> None:
        self._downloading = False
        self._refresh_status()
