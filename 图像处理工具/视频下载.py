#!/usr/bin/env python3
"""视频下载工具入口（兼容脚本方式，实际实现在 video_downloader/ 包内）。

用法:
    python 视频下载.py                 # 交互模式
    python 视频下载.py <链接> [--audio]  # 一次性下载
"""

from video_downloader.cli import main

if __name__ == "__main__":
    main()
