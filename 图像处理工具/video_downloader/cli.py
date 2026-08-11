"""命令行入口：一次性参数、交互菜单、管道模式。"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .auth import validate_cookie
from .config import find_tool, load_cookie, load_save_dir, save_cookie, save_dir_to_config
from .console import banner, dim, enable_vt_windows, error, info, menu, ok, prompt, warn
from .engines import describe_engines, resolve_engine
from .engines.base import EngineUnavailableError
from .options import (
    VIDEO_FORMATS,
    FORM_FIELDS,
    DownloadOptions,
    options_from_args,
    normalize_output,
    selection_within,
    validate_selection,
)
from .sites import detect_site


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="视频下载",
        description="跨平台视频下载命令行工具（B 站 / 通用网站）",
    )
    parser.add_argument("url", nargs="?", help="视频链接；不带参数时进入交互模式")
    # 下载选项由 FORM_FIELDS 生成：新增选项只需改 options.py
    for dest, _label, kind, flags, help_text, placeholder in FORM_FIELDS:
        if kind == "bool":
            parser.add_argument(*flags, dest=dest, action="store_true", help=help_text)
        else:
            parser.add_argument(*flags, dest=dest, metavar=placeholder or dest.upper(), help=help_text)
    parser.add_argument("--ui", choices=("cli", "textual"), default="cli", help="界面：cli（默认）或 textual")
    parser.add_argument("--status", action="store_true", help="查看工具与保存目录状态")
    parser.add_argument("--set-cookie", metavar="SESSDATA", help="设置并保存 B 站登录 cookie（传空串清除）")
    parser.add_argument("--clear-cookie", action="store_true", help="清除已保存的 B 站 cookie")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def run_download(url: str, options: DownloadOptions | None = None) -> bool:
    """解析并下载；CLI 与 TUI 共用的唯一下载入口。"""
    options = options or DownloadOptions()
    url = url.strip().strip('"').strip("'")
    if not url:
        warn("链接为空")
        return False
    if options.audio and (options.output_format or "").strip().lower() in VIDEO_FORMATS:
        warn("已开启仅音频，但输出格式为视频格式，输出格式将被忽略")
    normalize_output(options)

    dest = Path(options.save_dir).expanduser() if options.save_dir else load_save_dir()
    site = detect_site(url)
    entity = site["parse"](url)
    info(f"识别站点: {entity.display}")
    if entity.type != "unknown":
        detail = entity.type + (f" ({entity.id})" if entity.id else "")
        info(f"内容类型: {detail}")
    if entity.p:
        info(f"分P: {entity.p}")
    if entity.note:
        dim(entity.note)
    download_url = entity.clean_url or url

    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        error(f"无法创建保存目录: {dest}（{e.strerror or e}）")
        error("可用 -o <目录> 指定其他位置，或输入 settings 修改保存目录")
        return False

    engine = resolve_engine(site)
    if engine is None:
        error("没有可用的下载引擎，请安装缺失工具：")
        for name, display_name, available in describe_engines():
            print(f"  - {display_name}: {'✅ 可用' if available else '❌ 缺失'}")
        error("yt-dlp: pip install -U yt-dlp；BBDown: dotnet tool install --global BBDown")
        return False

    if options.selection and not validate_selection(options.selection):
        error(f"无效的选集范围: {options.selection!r}（支持 1,2 / 3-5 / ALL / LAST）")
        return False
    if options.audio_format and not options.audio:
        warn(f"已设置音频格式 {options.audio_format}，但未开启仅音频，音频格式将不生效（本次下载视频）")
    if options.selection:
        info("正在获取可用分P/选集…")
        items = engine.list_items(download_url)
        if items is not None:
            count = len(items)
            if not selection_within(count, options.selection):
                error(f"选集超出范围：该内容共 {count} 个分P/选集（可用 1-{count}，或 ALL）")
                return False
            info(f"共 {count} 个分P/选集，将下载: {options.selection}")
    if options.quality:
        info("正在获取可用清晰度…")
        qualities = engine.list_qualities(download_url)
        if qualities and options.quality not in qualities:
            warn(f"可用清晰度: {'/'.join(qualities)}；请求的 {options.quality} 可能不可用（将尝试）")

    try:
        if options.danmaku and engine.name == "yt-dlp":
            warn("弹幕下载仅 BBDown 支持；当前回退引擎为 yt-dlp，本次跳过弹幕")
            options.danmaku = False
        result = engine.download(
            download_url,
            dest,
            audio_only=options.audio,
            danmaku=options.danmaku,
            selection=options.selection,
            quality=options.quality,
            output_format=options.output_format,
            audio_format=options.audio_format,
        )
    except EngineUnavailableError as e:
        error(str(e))
        return False

    if result.success:
        ok(f"已保存到: {dest}")
        return True
    return False


def show_status() -> None:
    banner("当前状态")
    info(f"保存目录: {load_save_dir()}")
    for name in ("yt-dlp", "ffmpeg", "BBDown"):
        status = "✅ 可用" if find_tool(name) else "❌ 缺失"
        print(f"  {name}: {status}")


def settings_menu() -> None:
    while True:
        choice = menu(
            "设置",
            [
                ("dir", "修改保存目录"),
                ("cookie", "设置 B 站 Cookie"),
                ("status", "查看工具状态"),
                ("back", "返回"),
            ],
        )
        if choice is None or choice == "back":
            return
        if choice == "status":
            show_status()
        elif choice == "dir":
            info(f"当前保存目录: {load_save_dir()}")
            raw = prompt("输入新保存目录（留空保持不变，支持 ~ 展开）: ").strip()
            if not raw:
                continue
            new_dir = Path(raw).expanduser()
            try:
                save_dir_to_config(new_dir)
                ok(f"已更新保存目录: {new_dir}")
            except OSError as exc:
                warn(f"写入配置文件失败（目录仍可用）: {exc}")
        elif choice == "cookie":
            current = load_cookie()
            info(f"当前 Cookie: {'已配置（' + str(len(current)) + ' 字符）' if current else '未配置'}")
            raw = prompt("粘贴 SESSDATA（留空清除）: ").strip()
            try:
                save_cookie(raw)
                ok("已保存 B 站 Cookie" if raw else "已清除 B 站 Cookie")
            except OSError as exc:
                warn(f"保存失败: {exc}")


def show_help() -> None:
    banner("帮助")
    print(
        """用法
  交互模式      python 视频下载.py            进入菜单/直接粘贴链接
  一次下载      python 视频下载.py <链接> [--audio]
  仅音频        交互内输入 audio <链接> 或 a <链接>；命令行加 --audio
  弹幕         交互内输入 danmaku <链接> 或 d <链接>；命令行加 --danmaku
  选集         番剧/合集/多P 用 --items 1,2 或 3-5 或 ALL 指定范围
  快捷键        settings=设置  status=状态  help=帮助  quit=退出

站点支持
  B 站          解析层自动清洗追踪参数、识别 BV/av/分P/番剧/合集、展开 b23.tv 短链；
                优先 BBDown（多P/合集，可 BBDown login 扫码登录高画质），失败回退 yt-dlp
  其他网站      yt-dlp（YouTube 等 1000+ 站点）
  新增站点      在 video_downloader/sites/ 加模块（match/parse/engines）并注册，无需改 UI

工具依赖
  yt-dlp       通用引擎: pip install -U yt-dlp
  ffmpeg       音视频合并/转码必需
  BBDown       B 站专用: dotnet tool install --global BBDown（或 GitHub releases）"""
    )


_COMMAND_PREFIXES = (
    (("audio", "a"), "audio_only"),
    (("danmaku", "d"), "danmaku"),
)


def parse_line(line: str) -> tuple[str, bool, bool]:
    """解析交互前缀（可组合，如 a d <链接>）：返回 (url, audio_only, danmaku)。"""
    flags = {"audio_only": False, "danmaku": False}
    lowered = line.lower()
    changed = True
    while changed:
        changed = False
        for keys, flag in _COMMAND_PREFIXES:
            for key in keys:
                prefix = key + " "
                if lowered.startswith(prefix):
                    flags[flag] = True
                    line = line[len(prefix) :].strip()
                    lowered = line.lower()
                    changed = True
                    break
            if changed:
                break
    return line, flags["audio_only"], flags["danmaku"]


def interactive_loop() -> None:
    banner(f"🎬 视频下载工具 v{__version__}")
    ok("直接粘贴链接开始下载；audio/a 仅下音频，danmaku/d 带弹幕；输入 help 查看帮助")
    try:
        while True:
            raw = prompt("-> ").strip()
            if not raw:
                continue
            lowered = raw.lower()
            if lowered in ("quit", "exit", "q", "退出"):
                ok("再见！")
                break
            if lowered in ("help", "h", "帮助", "?"):
                show_help()
                continue
            if lowered in ("settings", "设置", "s"):
                settings_menu()
                continue
            if lowered == "status":
                show_status()
                continue
            url, audio_only, danmaku = parse_line(raw)
            run_download(url, DownloadOptions(audio=audio_only, danmaku=danmaku))
    except (KeyboardInterrupt, EOFError):
        print()
        ok("再见！")


def main(argv: list[str] | None = None) -> None:
    enable_vt_windows()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.clear_cookie:
        try:
            save_cookie("")
            ok("已清除 B 站 Cookie")
        except OSError as exc:
            error(f"清除失败: {exc}")
        return
    if args.set_cookie is not None:
        raw = args.set_cookie
        if raw.strip():
            from .config import normalize_cookie

            valid, message = validate_cookie(normalize_cookie(raw))
            if not valid and "校验请求失败" not in message:
                error(f"Cookie {message}，未保存")
                return
        try:
            save_cookie(raw)
            ok(
                f"已保存 B 站 Cookie（{message}），后续下载自动带上"
                if raw.strip() and "校验请求失败" not in message
                else ("已保存 B 站 Cookie（未能在线校验，将直接使用）" if raw.strip() else "已清除 B 站 Cookie")
            )
        except OSError as exc:
            error(f"保存失败: {exc}")
        return

    if args.ui == "textual":
        try:
            from .tui import DownloaderApp
        except ImportError:
            error("Textual 未安装：pip install textual（建议在项目 .venv 内安装）")
            return
        DownloaderApp(initial_url=args.url or "").run()
        return

    if args.status:
        show_status()
        return
    if args.url:
        run_download(args.url, options_from_args(args))
        return

    # 管道/重定向模式：逐行处理，便于脚本调用
    if not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            if not line or line.lower() in ("quit", "exit", "q", "退出"):
                continue
            url, audio_only, danmaku = parse_line(line)
            options = options_from_args(args)
            options.audio = options.audio or audio_only
            options.danmaku = options.danmaku or danmaku
            run_download(url, options)
        return

    interactive_loop()
