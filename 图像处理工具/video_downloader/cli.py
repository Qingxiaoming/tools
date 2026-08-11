"""命令行入口：一次性参数、交互菜单、管道模式。"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import find_tool, load_save_dir, save_dir_to_config
from .console import banner, dim, enable_vt_windows, error, info, menu, ok, prompt, warn
from .engines import describe_engines, resolve_engine
from .engines.base import EngineUnavailableError
from .sites import detect_site


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="视频下载",
        description="跨平台视频下载命令行工具（B 站 / 通用网站）",
    )
    parser.add_argument("url", nargs="?", help="视频链接；不带参数时进入交互模式")
    parser.add_argument("-a", "--audio", action="store_true", help="仅下载音频")
    parser.add_argument("-o", "--dir", help="保存目录（默认见设置）")
    parser.add_argument("--status", action="store_true", help="查看工具与保存目录状态")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def run_download(url: str, audio_only: bool = False, save_dir: str | None = None) -> bool:
    url = url.strip().strip('"').strip("'")
    if not url:
        warn("链接为空")
        return False

    dest = Path(save_dir).expanduser() if save_dir else load_save_dir()
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

    try:
        result = engine.download(download_url, dest, audio_only=audio_only)
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
            save_dir_to_config(new_dir)
            ok(f"已更新保存目录: {new_dir}")


def show_help() -> None:
    banner("帮助")
    print(
        """用法
  交互模式      python 视频下载.py            进入菜单/直接粘贴链接
  一次下载      python 视频下载.py <链接> [--audio]
  仅音频        交互内输入 audio <链接> 或 a <链接>；命令行加 --audio
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


def parse_line(line: str) -> tuple[str, bool]:
    """解析交互输入：audio/a 前缀表示仅音频。"""
    audio_only = False
    lowered = line.lower()
    for prefix in ("audio ", "a "):
        if lowered.startswith(prefix):
            audio_only = True
            line = line[len(prefix) :].strip()
            break
    return line, audio_only


def interactive_loop() -> None:
    banner(f"🎬 视频下载工具 v{__version__}")
    ok("直接粘贴链接开始下载；audio <链接> 仅下音频；输入 help 查看帮助")
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
            url, audio_only = parse_line(raw)
            run_download(url, audio_only=audio_only)
    except (KeyboardInterrupt, EOFError):
        print()
        ok("再见！")


def main(argv: list[str] | None = None) -> None:
    enable_vt_windows()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.status:
        show_status()
        return
    if args.url:
        run_download(args.url, audio_only=args.audio, save_dir=args.dir)
        return

    # 管道/重定向模式：逐行处理，便于脚本调用
    if not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            if not line or line.lower() in ("quit", "exit", "q", "退出"):
                continue
            url, audio_only = parse_line(line)
            run_download(url, audio_only=args.audio or audio_only, save_dir=args.dir)
        return

    interactive_loop()
